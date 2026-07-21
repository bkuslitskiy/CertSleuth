# CertSleuth — session handoff (2026-07-18)

Snapshot for the next working session. Pairs with the auto-loaded project memory.

---

## ⇢ Session 3 (2026-07-20) — CURRENT. Read this block first; everything below is historical (sessions 1–2).

**Repo / deploy state**
- `main` @ `6c735a6`, **+5 ahead of `origin/main` — NOT pushed.** Working tree clean. Only
  `main` exists locally (+ stale `origin/design-dark-luxury`, unused).
- **PRODUCTION IS LIVE** at https://certsleuth.com (GCP e2-micro **Standard**, Caddy TLS,
  Postgres). **Deploy = Boris clones/pulls from git on the VM**, then
  `docker compose up -d --build` + `manage.py migrate`; no CI/CD, **Claude never deploys**.
- **To ship this session's work:** push `main`; on the VM pull + **`docker compose build`**
  (new dep `django-axes`) + **`manage.py migrate axes`** + restart. A plain code pull will
  NOT activate SEC-021 (needs the build + migration).

**What landed this session (all on `main`; green: `ruff` + 198 `pytest`)**
- `8ab6834` — worker accepts any 2xx render response (scrum.org's 202) + test.
- `6d6439e` — provider-metadata migration `0010` (pre-seeds 23 providers) + fix for the test
  slug collision it introduced (`test_publish_credit_rule.py` → `get_or_create`).
- `18e0c40` — **SEC-021**: `django-axes` IP-based login lockout (5 failures / 1h cool-off, DB
  handler, 429 + `registration/lockout.html`). Gotcha fixed: `AXES_USERNAME_FORM_FIELD="username"`
  (axes defaulted to `USERNAME_FIELD=email`, so it recorded `username=None` and never matched).
- `4618e4f` — **SEC-022**: open-redirect guard on `next` (`plan_toggle`), RFC-5545 ICS
  escaping (`ics_feed`), bounded worker `?n` (`claim`). Tests in `test_input_hardening.py`.
- `6c735a6` — **SEC-023**: public landing at `/` for anon (dashboard for auth, via
  `apps.core.views.home`), descriptive metadata (desc/OG/canonical/favicon in `base.html`),
  a11y (skip link, landmarks, `prefers-color-scheme`), responsive (375px breakpoint + table
  scroll-wrappers), SEO (`robots.txt` + `sitemap.xml`). Reuses `WaitlistEntry`/`WaitlistForm`.
  Verified in-browser (desktop + mobile, no CSP errors); `test_landing.py`.

**Prod gaps — Boris-side, before prod is fully right/safe:**
1. **Prod catalog is EMPTY.** The 118 certs / 16 renewal rules are LOCAL sqlite only, so the
   public landing shows **no providers** in prod until the catalog is loaded in — export local
   → `loaddata`/fixture or a data migration. **NOT a crawl** (local-crawl-only rule stands).
2. **Backups NOT set up** — nightly `pg_dump` cron + one restore drill (gcp-setup §1.5). Do
   before relying on prod. (SEC-021's `migrate axes` is additive/safe even without them.)
3. **`EMAIL_URL` unset** → the waitlist "we'll email you" and invites store/queue but send
   nothing until SMTP is configured.
4. RLS enforcement flip — deploy-side non-owner web role (README TODO).

**Open work queue (mostly local / needs-Boris):**
- Review **369 pending `StagedChange`s** (local admin) — approve/reject.
- Promote 38 inert `SourceSubmission`s (local, optional next frontier round).
- Renewal-rule extraction gaps: CompTIA per-cert CEU, ISC2, Google, ISACA AI certs, Microsoft
  (needs a catalog provider first).
- Gmail OAuth execution (needs `GOOGLE_OAUTH_*`).

**Gotchas carried forward:**
- `ruff check .` + `pytest -q` before any push (CI hard-fails on ruff).
- **Local-crawl-only:** never crawl / spend LLM against prod.
- Dev serves the **unhashed** `static/css/certsleuth.css` → the browser caches it; after
  editing `input.css` run `npm run css` and hard-reload. Prod's `ManifestStaticFilesStorage`
  hashes the filename, so no stale-CSS there.
- Two schema validators stay in sync: `apps/research/schemas.py` + `worker/schema.py`.
- Local superuser: `boris.kuslitskiy@gmail.com` / `certsleuth-local-dev`. E2E users:
  `e2e@` / `rev@example.com` / `a-long-test-password`.
- Full session plan/notes: `C:\Users\Boris\.claude\plans\first-review-the-project-mutable-cocoa.md`.

---

> **Update 2026-07-18 (session 2).** Wired the deterministic extractor into the worker
> (SEC-018); made the worker render JS-built pages by default (SEC-019), replacing the
> failed `needs_render` heuristic with `main_text_len` + real rendering; re-crawled the
> renewal-policy pages with rendering on and extracted the **first non-Scrum renewal rules**
> (AWS/GIAC/ISACA, 22 facts now pending review). Two numbers below were already stale when
> written — corrected inline and marked ✎.

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

This is the output of the crawl/extraction runs:
- **All 93 staged changes approved & published** (Boris approved the pending batch
  2026-07-18). They are now the canonical catalog: **68 certifications** at
  `/admin/catalog/certification/` and **16 renewal rules** at `/admin/catalog/renewalrule/`
  — Scrum Alliance, ISC2, Google Cloud/Career, and the recovered GIAC / CompTIA / ISACA /
  AWS catalogs. The approval records (audit trail) are at
  `/admin/research/stagedchange/?status__exact=approved`. The pending review queue is empty.
- **✎ 444 crawl-discovered submissions queued (inert)** at
  `/admin/research/sourcesubmission/?origin__exact=crawl` — the handoff first said "~94";
  it was 387 at session-2 start and 444 after the render recrawl added 57. Deeper cert/policy
  pages awaiting approver promotion. (The long URL queue, distinct from the facts above.)
- **22 renewal-rule/upgrade facts pending review** (session 2) at
  `/admin/research/stagedchange/?status__exact=pending` — AWS/GIAC/ISACA, extractor
  `claude-code-local`. First non-Scrum renewal rules. Mirror in
  `sample_data/renewal-rules-2026-07-18/`.
- **✎ Full rendered recrawl of all 320 sources (session 2, later):** every source re-fetched
  with rendering + busted etags and reclassified on real evidence. Now **26 active / 256 hub /
  31 dead / 7 barren / 0 needs_render**. Notable: 72 seeds that had defaulted to `active`
  without ever yielding got their first true classification (hub); 21 AWS/CompTIA/ISACA cert
  pages went hub→active via live auto-extraction (SEC-018's first production run — 21 facts);
  11 ISACA `verify-application-fee` endpoints (auth-walled, 40x on GET) correctly moved to
  dead. Two proven yielders (isc2/certifications, aws/recertification) were restored to
  active after the no-new-facts-this-round demotion.
- **Pending review is now 43**: 22 renewal/upgrade facts (`claude-code-local`) + 21
  auto-extracted certification facts (`worker-deterministic-v1`, dupes of existing catalog
  rows — approve to refresh names, or reject; harmless either way).
- **~279 leased extraction jobs** will expire back to queued (30-min lease) — they're the
  no-facts-this-round pages; next operator extraction session claims them. Not an error.

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
- ~~Wire `worker/extractors.py` into the worker flow~~ — **done** session 2 (SEC-018).
- ~~Tune the `needs_render` threshold~~ — **superseded** session 2 by rendering + `main_text_len`
  (SEC-019). The MS Learn browse page is now `hub`, not `barren`.
- ~~Extract renewal rules from provider policy pages~~ — **AWS/GIAC/ISACA done** session 2
  (22 facts pending review). Still open: **CompTIA** (per-cert CEU page not yet crawled —
  `why-renew` is motivational only), **ISC2** and **Google** (no policy page crawled yet),
  and ISACA's newer AI credentials. Microsoft renewal is cleanly extractable but has no
  catalog provider — add one first if desired.
- Promote + crawl the queued depth-2 pages (444 now) — another frontier round, **now with
  rendering**, so JS-built provider catalogs (e.g. MS Learn browse, 34 links) come through.
- RLS enforcement code-readiness done; still needs the deploy-side non-owner role.
- The 29 leased renewal jobs from the session-2 recrawl (401-walled ISACA quizzes, etc.)
  will expire back to `queued` and requeue on cadence — no action needed.

**Needs Boris (credentials/accounts/decisions):**
- (Done 2026-07-18: reviewed & approved the staged facts — now in the catalog.)
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
