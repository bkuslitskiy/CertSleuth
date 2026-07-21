# CertSleuth

Multi-provider certification tracker: renewals, CEUs with cross-crediting, upgrade paths,
free offers — with a human-reviewed research pipeline that keeps provider rules current.
Spec: `docs/spec.md` (v0.3, decisions D1–D27). Security: `security.md` + `security-audit.md`.

## Status: booted and verified (2026-07-17)
First boot is done: migrations are committed, both test suites are green (pytest +
Playwright), and the full ingest → staging → review → publish → dashboard loop has been
exercised end-to-end with the Scrum Alliance sample and a live Credly import.
Remaining work is listed at the bottom.

## Local dev setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv/Scripts/python.exe
pip install -e .[dev]
cp .env.example .env            # set DJANGO_SECRET_KEY + FIELD_ENCRYPTION_KEY; leave DATABASE_URL unset for sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Admin at /admin is the Approver review queue (StagedChange), source registry, offer review,
enrollment queue, and worker-token minting. Users with role approver/admin get these
surfaces automatically (SEC-012); the "Review queue" nav link appears for them after login.

## Preload (the priority path)
1. Seed sources + jobs: `python manage.py shell -c "exec(open('scripts/seed_sources.py').read())"`
   (piping via `shell <` breaks on blank lines; verify seed URLs in
   `scripts/seeds/sources.json` first — authored offline).
2. Mint a worker token: admin → Worker tokens → add (token shown once).
3. On your machine: `export CERTSLEUTH_WORKER_TOKEN=...` then
   `python worker/claude_worker.py fetch --api https://certsleuth.com --n 25`
4. Run Claude Code in `worker/` — `CLAUDE.md` there is the extraction instruction set;
   it produces `results.jsonl` and validates it with `worker/schema.py`.
5. `python worker/claude_worker.py submit results.jsonl --api https://certsleuth.com`
   — or upload the file at `/research/ingest/` (batch mode, same validation).
6. Review queue: bulk approve/reject by source. Nothing publishes without approval.

## Tests
`pytest` (sqlite fast pass; RLS tests auto-skip off Postgres).
Playwright: `cd tests/e2e && npm i && npx playwright test` against a running dev server
(seeds two users: e2e@example.com and rev@example.com — see CI job or tests/e2e specs).

## Deploy (GCP e2-micro, D9)
Full walkthrough — VM, DNS/TLS, backups, and the Google OAuth console setup — in
`docs/gcp-setup.md`. Short version: `docker compose up -d --build` behind the bundled
Caddyfile, `manage.py migrate` + `setup_schedules` in the web container, nightly
`scripts/backup.sh` via VM cron.

## Known TODOs (in priority order)
- RLS enforcement flip: the policy mechanism is verified on Postgres (tests/test_rls.py,
  SEC-016); remaining is deploy-side — provision a non-owner web role + point its
  DATABASE_URL at it, and run django-q workers as the owner role (cross-user tasks). App
  code is RLS-ready (middleware + ICS feed scoped).
- Gmail scan execution: enrollment queue, approval queue (GmailScanRequest, SEC-013),
  gating, and the gmail.py run_scan state machine + config gate are built and tested. The
  OAuth consent → Gmail fetch → extract-and-discard → StagedChange body is the one marked
  remaining step; needs GOOGLE_OAUTH_* creds (docs/gcp-setup.md §2). Runs approved only.
- Deploy: image + app stack validated locally on Postgres (build, migrate, gunicorn,
  django-q, DEBUG=false static — via docker-compose.smoke.yml). Remaining: provision the
  GCP e2-micro and exercise the real docker-compose.yml with Caddy TLS (needs the VM +
  public DNS) — see docs/gcp-setup.md.
- ~~LinkedIn CSV importer: verify exact headers~~ — verified against a real full-profile
  export 2026-07-18; headers match exactly. Open enhancement: the importer drops
  `Authority` (issuer — could aid provider matching) and `License Number` (could fill the
  encrypted cert_number field, SEC-009).
- Run the preload: extraction worker sessions over the 21 seeded sources.

Done since first boot (cont'd, 2026-07-21): tier-rank fix (advanced no longer reads as
same tier as professional — CSP-PO bug); `level` keyword coverage expanded to match all
live provider data; `Certification.eligibility_requirement` field added and the 8 ISC2
facts that had experience-requirement text stuck in `level` were split out and backfilled;
`Certification.source` added and backfilled from historical approved StagedChanges so cert
pages can link back to their source.

Done since first boot: initial migrations; cert-number encryption (SEC-009); django-q
schedules; approver role → admin surfaces (SEC-012); approver-gated spend (SEC-013);
credential importers — Credly, Microsoft Learn, Accredible, Open Badges, LinkedIn
(spec 5.2-5.5, SEC-015); Docker image hardening (.dockerignore/collectstatic, SEC-014);
RLS mechanism proven on Postgres (SEC-016); CI green.
