# GCP setup guide — hosting (D9) + Google OAuth (D13/D25)

Two independent tracks in one GCP project: the Always Free e2-micro that hosts the app,
and the OAuth consent screen + client that powers Gmail on-demand scanning. Nothing here
costs money except the domain (and egress if you get popular).

---

## Part 1 — Hosting: e2-micro + Docker Compose

### 1.1 Project + VM

1. https://console.cloud.google.com → create project `certsleuth` (this same project hosts
   the OAuth consent screen in Part 2 — one project keeps admin surface small).
2. Compute Engine → Enable API → Create instance:
   - **Name** `certsleuth-vm`
   - **Region**: `us-west1`, `us-central1`, or `us-east1` — **only these qualify for
     Always Free**. Machine type **e2-micro**.
   - **Provisioning model: Standard, NOT Spot.** Under Machine configuration → Advanced,
     leave the VM provisioning model on **Standard**. Spot is cheaper per-hour but is
     preemptible — Google can shut it down at any time (killing the app + Postgres +
     worker on the box), and Spot is billed at spot rates rather than covered by Always
     Free. The free e2-micro must be a standard, non-preemptible instance.
   - **Boot disk**: 30 GB **standard persistent disk** (the free allowance; balanced/SSD
     is not free). Debian 12 or 13 (current) — both fine.
   - **Firewall**: check *Allow HTTP* and *Allow HTTPS*.

   Cost note: a standard e2-micro in a free region is $0 under Always Free (one instance/
   month). The console's monthly estimate may still show the ~$6/mo list price — the free
   tier is applied at billing, not always in the estimator. A ~$3.53 estimate with a
   "Discount" line means Spot is selected — switch it to Standard.
3. Reserve the external IP: VPC network → IP addresses → the VM's ephemeral IP →
   *Reserve* (a static IP attached to a running instance is free; detached, it bills).
4. DNS (at SiteGround, which keeps the landing page per D9): `A` records for
   `certsleuth.com` and `www` → the reserved IP. Caddy needs DNS resolving before it can
   issue TLS certificates.

### 1.2 Prepare the box

SSH in (Console → SSH button, or `gcloud compute ssh certsleuth-vm`):

```bash
# Swap first — 1 GB RAM will OOM during image builds without it (D9 accepted trade-off)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # re-login after this

git clone https://github.com/bkuslitskiy/CertSleuth.git certsleuth && cd certsleuth
```

### 1.3 Production .env

`cp .env.example .env`, then set:

| Var | Value |
|---|---|
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `certsleuth.com,www.certsleuth.com` |
| `DATABASE_URL` | `postgres://certsleuth:<db-pass>@db:5432/certsleuth` |
| `POSTGRES_PASSWORD` | same `<db-pass>` (compose passes it to the db container) |
| `EMAIL_URL` | your Resend/Postmark SMTP string |
| `FIELD_ENCRYPTION_KEY` | `python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |
| `ANTHROPIC_API_KEY` | prepaid API credits key (steady-state extraction only, D17) |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET` | from Part 2 — blank disables the Gmail feature cleanly |

SEC-009 note: `.env` on the VM is the v1 stopgap; the target is GCP Secret Manager.
Keep the file `chmod 600`, never commit it.

### 1.4 Launch

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Caddy (bundled `Caddyfile`) terminates TLS for `certsleuth.com`, redirects `www`, and
proxies to gunicorn on `web:8000`. If certificates don't appear within a minute, check
`docker compose logs caddy` — it's almost always DNS not yet propagated.

Smoke test: `https://certsleuth.com/admin/` loads over valid TLS; the qcluster container
shows heartbeats in `docker compose logs qcluster`.

### 1.5 Backups (D27) + upkeep

```bash
# One-time: bucket + VM access to it
gsutil mb -l us-central1 gs://certsleuth-backups
# VM's service account needs Storage Object Admin on the bucket (IAM → grant on bucket)

# Nightly pg_dump at 03:15, 30-day retention (scripts/backup.sh)
crontab -e
15 3 * * * cd /home/$USER/certsleuth && ./scripts/backup.sh >> /var/log/certsleuth-backup.log 2>&1
```

Restore drill (do it once now, not during an incident):
`gunzip -c backup.sql.gz | docker compose exec -T db psql -U certsleuth certsleuth`.

Patching is yours (D9): `sudo apt upgrade` + `docker compose pull && docker compose up -d`
on a calendar reminder.

---

## Part 2 — Google OAuth for Gmail scanning (D13, D25)

The design keeps this cheap: **one-shot on-demand scan** with `gmail.readonly`, fresh
consent each scan, token discarded after the pass. No stored Gmail tokens, no background
sync — so the "Testing" status 7-day refresh-token expiry is irrelevant, and the ~100
test-user cap is the only real ceiling (CASA Tier 2 is the accepted cost if we outgrow
it, spec §5.1).

### 2.1 Consent screen

Same `certsleuth` project → **APIs & Services**:

1. *Enabled APIs* → enable **Gmail API**.
2. *OAuth consent screen* (Google Auth Platform → Branding/Audience):
   - User type **External**; publishing status stays **Testing** (do NOT publish —
     publishing with a restricted scope triggers verification/CASA).
   - App name `CertSleuth`, support email, domain `certsleuth.com`, developer contact.
3. *Data access / Scopes* → add `https://www.googleapis.com/auth/gmail.readonly`
   (listed under restricted scopes — fine in Testing).

### 2.2 Test users — the D25 manual step

Google has no API for the test-user list (spec §4: the adjacent programmatic surfaces
were retired), so enrollment is semi-automated:

- Users request scanning at `/accounts/gmail-enrollment/` → creates an `EnrollmentTask`.
- Admin queue: `/admin/accounts/enrollmenttask/` — copy the pending Gmail addresses.
- Console → *Audience* → **Test users** → *Add users* → paste the batch.
- Back in the admin, mark the tasks done / set `gmail_scan_enabled` on those users.
  Only then does "Scan my inbox" unlock (the "Pending console add" status you see on
  the enrollment page is this gate working).

### 2.3 OAuth client

*Credentials* → **Create credentials → OAuth client ID**:

- Type **Web application**, name `certsleuth-web`.
- Authorized JavaScript origins: `https://certsleuth.com`
- Authorized redirect URIs:
  - `https://certsleuth.com/track/gmail/callback/`
  - `http://localhost:8000/track/gmail/callback/` (local dev)

The callback view lands in `apps/tracker/gmail.py` (README TODO) — keep the route name
`/track/gmail/callback/` in sync with this URI when implementing.

Copy the client ID + secret into `.env` (`GOOGLE_OAUTH_CLIENT_ID`,
`GOOGLE_OAUTH_CLIENT_SECRET`), then `docker compose up -d` to restart with them (locally:
restart runserver). Blank values keep the feature disabled with no other effect.

### 2.4 Scan behavior contract (already specced, for the implementer)

- SEC-013: the user's "Scan my inbox" click creates a `GmailScanRequest`; the scan
  itself runs only after an Approver approves it at `/admin/research/gmailscanrequest/`.
- Fresh OAuth consent per scan; access token used for one pass, then discarded.
- Query only known issuer senders (`from:credly.com OR from:isc2.org OR …`), never the
  whole mailbox.
- Persist message-ID + extracted fields + confidence only — never raw bodies (D7).
- Extraction output goes to `StagedChange` like every other extractor (SEC-005).

---

## Checklist

- [ ] e2-micro in a free-tier US region, 30 GB standard disk, static IP reserved
- [ ] DNS A records live; Caddy issued TLS
- [ ] `.env` populated; `migrate` + `createsuperuser` run; admin loads over HTTPS
- [ ] Backup bucket + cron installed; restore drill performed once
- [ ] Gmail API enabled; consent screen External/Testing with `gmail.readonly`
- [ ] OAuth client created; redirect URIs registered; creds in `.env`
- [ ] First test user (you) added under Audience → Test users
