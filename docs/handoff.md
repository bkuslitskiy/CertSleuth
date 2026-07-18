# CertSleuth — session handoff (2026-07-18)

Snapshot for the next working session. Pairs with the auto-loaded project memory.

## TL;DR

The project went from "authored but never executed" to **booted, tested, CI-green, and
substantially built out**: it runs locally, the research pipeline works end to end, five
credential importers exist, and a full **crawl-discovery engine** (fetch → classify →
enqueue) is merged. The local staging DB is **filled with 76 real facts pending review**
from a full crawl of the seeded providers. No blocking bugs. Development is paused here.

## Repo / branch state

| Branch | Head | Status |
|---|---|---|
| `main` | `3e8e72d` | Crawl engine merged (PR #1). CI green. Canonical. |
| `provider-extraction-tuning` | `d89fc8d` | **1 commit, pushed, CI green, NO PR yet.** Per-provider cert-name extractor. |
| `crawl-procedure` | `c909e5d` | Merged into main via PR #1; branch can be deleted. |

Working tree clean. Currently checked out on `provider-extraction-tuning`.
GitHub: https://github.com/bkuslitskiy/CertSleuth (repo was renamed from CredSleuth).
`gh` is authenticated as bkuslitskiy.

**First open action:** open a PR for `provider-extraction-tuning` (or merge it), then it
can be deleted along with `crawl-procedure`.

## Local environment (how to resume)

- `.venv` exists. Run Python as `.venv/Scripts/python.exe`.
- `.env` present (sqlite, DEBUG=true, generated keys). DB is `db.sqlite3` (gitignored).
- Dev server: `.claude/launch.json` → preview "certsleuth-dev" (runserver 8000 `--noreload`
  — **restart it to pick up code changes**).
- Superuser: boris.kuslitskiy@gmail.com / `certsleuth-local-dev` (role=admin).
  E2E users: e2e@ / rev@example.com / `a-long-test-password`.
- **Before any push:** `ruff check .` (CI hard-fails on it) and `pytest -q`.
  Suite is hermetic (no .env needed); RLS test runs only with `DATABASE_URL` → Postgres.
- CI status without gh auth: the public API works —
  `curl -s "https://api.github.com/repos/bkuslitskiy/CertSleuth/actions/runs?per_page=1"`.

## Local DB state (NOT in git — lives in db.sqlite3)

This is the output of the crawl/extraction runs, left in place for review:
- **76 staged facts pending** at `/admin/research/stagedchange/?status__exact=pending`
  (9 SA renewal rules + 67 certifications). Providers: Scrum Alliance, ISC2, Google Cloud,
  Google Career, and the recovered GIAC / CompTIA / ISACA / AWS catalogs (`extractor` tag
  `per-provider-og`). **These are unreviewed — Boris should approve/reject.**
- 17 approved staged changes (the original Scrum Alliance sample, already in catalog).
- **93 crawl-discovered submissions still queued (inert)** at
  `/admin/research/sourcesubmission/?origin__exact=crawl` — deeper cert pages, depth 2,
  awaiting approver promotion.
- 320 sources: 107 active, 201 hub, 9 dead, 2 barren, 1 needs_render.

## What was built this session (by theme)

**Boot & infra**
- First boot: pyproject package-discovery fix, generated all `0001_initial` migrations,
  seeded 21 provider sources.
- **CI was red on every push until fixed** (ruff + a hermetic-settings gap). Now green.
  `.gitattributes` normalizes line endings.
- Docker deploy validated locally on Postgres; fixed **`.dockerignore`** (was baking `.env`
  into image layers — SEC-014) and build-time `collectstatic`.

**Access control & security ledger** (see `security.md`)
- SEC-012: approver/admin role → admin review surfaces; superusers count as approvers.
- SEC-013: LLM/fetcher spend is approver-gated; users only queue, never trigger crawls.
- SEC-014: secrets excluded from Docker image.
- SEC-015: importer fetches stay in the SEC-013 carve-out.
- SEC-016: RLS mechanism **proven on Postgres** under a non-owner role (tests/test_rls.py).
- SEC-017: crawl-discovery boundary — app adds to queue, humans process; **same-domain
  links only, cross-domain dropped entirely**.

**Features**
- Credential importers (spec 5.2–5.5): Credly (writes rows + queues unmatched), Microsoft
  Learn (live-verified), Accredible, Open Badges (`.json/.png/.svg`, SSRF-guarded),
  LinkedIn CSV (built to documented columns — verify against a real export).
- Offer submissions queue a verification crawl.
- Gmail scan **approval gate** (`GmailScanRequest`) + `gmail.py` run-scan scaffold
  (state machine + config gate; OAuth/Gmail body needs creds).
- **Crawl-discovery engine** (`worker/crawl.py`, `apps/research/discovery.py`,
  `fetch-report` endpoint, status-tiered scheduler cadence). Docs: `docs/crawl-procedure.md`.
- **Per-provider cert-name extractor** (`worker/extractors.py`, this branch) — og:title
  with per-provider rules; recovered the ISACA/AWS/CompTIA/GIAC catalogs the generic h1
  couldn't.

## Open work

**Autonomous (no Boris needed):**
- Open PR for `provider-extraction-tuning`; delete merged branches.
- Wire `worker/extractors.py` into the worker submit flow so normal crawls stage these
  providers' certs automatically (currently a one-off recovery script did it).
- Promote + crawl the 93 queued depth-2 pages (another frontier round).
- Tune the `needs_render` visible-text threshold (500) — one JS-shell page
  (`learn.microsoft.com/credentials/browse/`) fell into `barren`.
- RLS enforcement code-readiness done; still needs the deploy-side non-owner role.
- Extract **renewal rules** (CEU/CPE/PDU + fees) from provider policy pages — only Scrum
  Alliance has a clean one so far; most seed URLs are overview pages (many were stale/404).

**Needs Boris (credentials/accounts/decisions):**
- Review & approve the 76 staged facts.
- Google OAuth creds (`GOOGLE_OAUTH_*`) → unblocks Gmail scan execution (docs/gcp-setup.md §2).
- Email provider SMTP (`EMAIL_URL`) → invites/reminders.
- Anthropic API key → steady-state server extraction (preload doesn't need it — that's Claude Code).
- GCP e2-micro provisioning (use **Standard, not Spot** — docs/gcp-setup.md).
- Fresh LinkedIn `Certifications.csv` export → pin the importer's column headers.
- RLS enforcement decision (provision non-owner web role + workers-as-owner).

## Gotchas / operational notes

- **Worker fetch needs a browser User-Agent** (added) — providers 403 a bare UA.
- **Seed URLs are mostly stale** (authored offline); 4 of 21 were 404/403. Verify before relying.
- **Provider pages: og:title, not h1** for cert names (h1 is often a promo banner).
- **Fact extraction is Claude Code (the operator), not server API** — no API credits needed
  for preload (D17).
- Snapshots stay worker-side (SEC-006); only distilled links/canonical reach the server.
- Two schema validators must stay in sync: `apps/research/schemas.py` + `worker/schema.py`.
