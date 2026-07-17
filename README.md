# CertSleuth

Multi-provider certification tracker: renewals, CEUs with cross-crediting, upgrade paths,
free offers — with a human-reviewed research pipeline that keeps provider rules current.
Spec: `docs/spec.md` (v0.3, decisions D1–D27). Security: `security.md` + `security-audit.md`.

## Status: generated codebase, NOT yet executed
Authored offline — Django was not installed in the authoring environment, so nothing here
has been run. Expect first-boot fixes. Known TODOs are listed at the bottom.

## First boot (local dev)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env            # set DJANGO_SECRET_KEY; leave DATABASE_URL unset for sqlite
python manage.py makemigrations accounts catalog tracker offers research
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Admin at /admin is the Approver review queue (StagedChange), source registry, offer review,
enrollment queue, and worker-token minting.

## Preload (the priority path)
1. Seed sources + jobs: `python manage.py shell < scripts/seed_sources.py`
   (verify seed URLs in `scripts/seeds/sources.json` first — authored offline).
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
Playwright: `cd tests/e2e && npx playwright test` (see CI for the seeded users it expects).

## Deploy (GCP e2-micro, D9)
`docker compose up -d` behind the bundled Caddyfile; nightly `scripts/backup.sh` via VM cron.

## Known TODOs (first-boot list)
- `makemigrations` generates every 0001_initial; tracker/0002_rls then applies (Postgres).
- RLS full enforcement needs the per-request `SET certsleuth.user_id` middleware and a
  non-owner DB role — policies ship, wiring is stubbed (see migration README + SEC-008).
- Gmail scan: enrollment queue + gating are built; the OAuth dance itself awaits console
  credentials (GOOGLE_OAUTH_* in .env) — implement in apps/tracker/gmail.py when creds exist.
- Cert-number app-layer encryption (SEC-009): field is plain until FIELD_ENCRYPTION_KEY
  wiring lands in a core.crypto helper.
- Credly import shows matches but doesn't yet write UserCertification rows on confirm.
- Scheduler task (django-q) for re-crawling `scheduled` sources on cadence: stub.
