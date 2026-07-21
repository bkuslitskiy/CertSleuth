# CertSleuth — session handoff (2026-07-18)

Snapshot for the next working session. Pairs with the auto-loaded project memory.

---

## ⇢ Session 3, part 4 (2026-07-21) — Microsoft driven to barren; new gap found (missing snapshots).

Continuation of part 3, per "go further in extraction through to barren on all providers."
**288 total facts staged pending this session** (up from 189 at the last handoff): 98
certification, 127 renewal_rule, 63 upgrade_path. All still `pending` StagedChange rows —
**needs Boris's admin review pass**, nothing auto-published (SEC-005).

**Microsoft is now genuinely barren.** Read and extracted every remaining cert-detail page
in the crawled frontier:
- Closed the M365/GitHub family: Teams/Endpoint/Collaboration Comms admin associates,
  Copilot & Agent Admin fundamentals, M365 Administrator Expert (+ 4 `requires` prerequisite
  edges), GitHub Copilot/Agentic AI Developer/Advanced Security/Actions.
- Filled `level` for ~30 previously-uncaptured cert pages (Security Ops Analyst, Identity &
  Access Admin, Information Security Admin, Azure Administrator/Developer/Security
  Engineer/Database Admin/Virtual Desktop/Network Engineer/Cosmos DB/Solutions Architect
  Expert/DevOps Engineer Expert, Power Platform, Dynamics 365 ×6, MOS ×7, MCE, and more) plus
  2 new `requires` edges (DevOps Engineer Expert, Azure Solutions Architect ← Administrator).
- **Lifecycle sweep**: 9 more certs confirmed `retired` via explicit page text (Dynamics 365
  Fundamentals CRM/ERP, M365 Fundamentals, Azure Data Scientist/AI Engineer, D365 Finance
  Solution Architect/Supply Chain Expert, Power Platform Solution Architect Expert, D365
  Field Service, Power Automate RPA Developer) — 3 of these had explicit `retired_date`.
  Certs stated as retiring on a *future* date (Azure Developer, D365 CX Analyst, Azure
  Security Engineer, Power Platform Functional Consultant — all "retire on" a 2026-07/08
  date) were deliberately left **without** `status=retired`: per `worker/CLAUDE.md`, that
  field means "no longer attainable," which isn't true yet.
- **Discovered and fetched 7 pages the crawler never found**: Azure Network Engineer
  Associate, Azure Cosmos DB Developer Specialty, Fabric Analytics/Data Engineer Associate,
  Azure Data Fundamentals, D365 Customer Service Functional Consultant, and Agentic AI
  Business Solutions Architect (new `level` value seen: `"Advanced"`, distinct from the
  Beginner/Intermediate/Expert set used elsewhere). Found via sibling `/practice/assessment`
  sub-pages that existed with no matching main page — direct single-page fetches (7 URLs,
  same `CertSleuthBot` UA the worker uses), not a broad crawl. Local-only, per the standing
  local-crawl approval.
- **MOS/MCE renewal cadence resolved**: `credential-expiration-policy` (job 869) states
  "MOS and MCE Certifications expire every 5 years" — applied `cycle_years=5` (fee not
  stated, left null) to all 7 MOS certs + Microsoft Certified Educator.

**New gap found (not pursued this session): ~111 done-but-unmined jobs across CompTIA (25),
ISC2 (15), ISACA (54), Google (17)** — these cert-detail pages were fetched in an earlier
crawl and reached `status=done`, but **no snapshot HTML was ever persisted to
`worker/jobs/`** (empty `snapshot_hash`, no file on disk), so they can't be re-extracted
without a fresh fetch. Spot-checked: the underlying certs (CISSP, CCSP, CGRC, CSSLP, SSCP,
Security+, Network+, CISA, AAIA, …) are **already published** with correct name/slug — this
is a `level`/metadata backfill gap, not a missing-cert gap. Re-fetching is the same shape of
action as the 7-page Microsoft pickup above, just ~15x the volume — flagging for a decision
rather than launching it silently. `worker/jobs/` retention for pages fetched before this
session is worth checking (why did these never get a snapshot file?) before just re-fetching.

**Housekeeping this pass**: the local dev server (`--noreload`) had stopped between sessions
and needed a restart; a stray `WorkerToken` (`claude-code-local-session4`) was minted because
the original session's token value wasn't recoverable (only its hash is stored, per
SEC-004) — harmless, local-only. `ruff check .` and `pytest -q` (202 passed, 1 skipped) both
green; no source files changed this pass (pure extraction — StagedChange data, not commits),
so nothing new to push.

## ⇢ Session 3, part 3 (2026-07-21) — second extraction pass, deeper per-provider mining.

Continued the extraction pass over the same background crawl (700-job frontier), this time
reading previously-unread banked snapshots per provider instead of just the highest-value
pages. **189 total facts staged pending this session** (up from 140): 44 certification, 89
renewal_rule, 56 upgrade_path. By provider: CompTIA 86, ISC2 18, Google Cloud 21, ISACA 27,
Microsoft 37. Frontier crawl queue is now down to ~36 jobs (from 700) and draining on its
own — effectively barren for the ~700-job scope this session queued.

**New this pass:**
- **CompTIA**: expanded every cert's `ceu_categories` to include teach/mentor, create
  materials, SME workshop, and publish article/blog/book caps (jobs 1028-1030) — the
  richest single-provider dataset in the catalog now.
- **ISC2**: confirmed `cycle_years=3` applies to all 9 real certs (job 1196) — the CPE
  *total* per cert is still genuinely unconfirmed (canonical policy URL still 404s).
- **Google Cloud**: found the live pages for Data Engineer + Cloud Database Engineer (the
  `/certification/<slug>` path 404s for these two; live content is under
  `/learn/certification/<slug>`) — filled in real fee/validity data.
- **ISACA**: confirmed the `$45/$85` annual maintenance fee directly on CISA/CISM/CCOA/CCA's
  own pages, applied the same figure to CRISC/CGEIT/CDPSE as `commonly_accepted` (same
  program, same tier, not individually re-confirmed); found LCCA's flat `$500` annual fee
  (no CPE requirement at all — a genuinely different renewal shape).
- **Microsoft — the big one**: `docs/credentials/support/credential-retirement` lists
  certifications already retired with specific dates. Cross-referenced against today's date
  (2026-07-21): **9 already-retired certs** (8 existing catalog rows + 1 new
  `microsoft-365-fundamentals`) now correctly marked `status=retired` with `retired_date`.
  This is exactly the retired-lifecycle feature (commit `300e3e8`) doing its job on real data.
  Also confirmed a **new, unexplored cert family**: GitHub certs (Foundations/Administration/
  Copilot/Actions/Advanced Security), MOS certs (Word/Excel/PowerPoint × 2019 and M365-Apps
  variants, on a **5-year** cycle per `credential-expiration-policy` — distinct from the
  standard 1-year role-based cycle), and Fabric certs (Analytics/Data Engineer Associate) —
  added 3 as a sample (github-foundations, github-administration,
  mos-word-associate-m365-apps) but this is a genuinely large new surface, not yet mined.

**Where "barren" was NOT reached (honest accounting, not a guess):**
- **Microsoft's long tail is the biggest gap** — ~230 pages still unread at last check,
  dominated by three whole new cert families (GitHub, MOS, Fabric/Applied-Skills) that
  weren't in the catalog when this session started. Applied Skills are a *different*
  credential type from Certifications per Microsoft's own framing (lab-based, don't expire)
  — would need a schema/product decision on whether to track them at all before extracting.
- **ISACA's "fundamentals certificates"** tier (badge-level, ~11 of them under
  `/credentialing/*-fundamentals-certificate`) is still unexplored — lower priority, more
  badge than certification.
- **CompTIA's cross-provider partial-CEU grants** (e.g., "earning an AWS cert grants 20 CEUs
  toward CompTIA A+") — real data (job 1005) but requires exact slug-matching against 10+
  other providers' catalogs; a substantially larger and more error-prone task than
  same-provider extraction. Flagged, not attempted.

**Resume point:** snapshots are cumulative in `worker/jobs/*.html`; find unread ones per
provider with the "already extracted" job_id diff pattern used throughout this session
(`StagedChange.objects.filter(extractor='claude-code-local').values_list('job_id')` vs
`os.path.exists(f'jobs/{job_id}.html')`). The crawl loop's remaining ~36 jobs will finish
draining on their own if the background process is still alive; if not, the queue is stable
and can be resumed with `worker/claude_worker.py fetch` in a loop.

---

## ⇢ Session 3, part 2 (2026-07-21) — extraction pass. Read this block first.

Reviewed all 369 previously-pending StagedChanges (published; see below), then ran a live
operator extraction pass (Sonnet 5, not the API — D17) over CompTIA/ISC2/Google/ISACA/
Microsoft, in that priority order, reading rendered snapshots directly and staging results
through the normal `worker submit` path (SEC-005: nothing auto-published).

**Schema change:** added `UpgradePath.Effect.PARTIAL_CREDIT` + a nullable `ceu_amount`
column (migration `0011`) — CompTIA policy pages state fixed cross-cert CEU grants
("SecurityX grants 25 CEUs toward Cloud+") that don't fit `renews` (overstates it) or
`CreditRule` (that's activity-rate, not cert-specific). Threaded through both schema
mirrors, `publish.py`, `compat.py` (two new keys), `worker/CLAUDE.md`, and tests. Committed
on `main` @ `44dfabe`. **Needs a VM rebuild + migrate to reach prod**, same as SEC-021.

**140 new facts staged pending** (`extractor=claude-code-local`, un-reviewed —
`/admin/research/stagedchange/?status__exact=pending`): 29 certification, 55 renewal_rule,
56 upgrade_path. By provider: CompTIA 70 (incl. the new `partial_credit` edges + the
previously-missing A+ cert), ISC2 9 (experience-level text only — CPE cycle/fee remains
unconfirmed, see gap below), Google Cloud 18 (official Foundational/Associate/Professional
tiers + fees/validity + the previously-missing Cloud Developer cert), ISACA 19 (CPE category
breakdown for 9 certs from the master policy PDF + 5 new CMMC-family/retired certs +
prerequisite chain), Microsoft 24 (confirmed free renewal, `renewal_fee_usd=0`, on all
24 role-based certs).

**Frontier is NOT yet barren.** The background crawl from earlier in this session (~700
jobs queued across the 5 providers) is still running and had ~672 jobs queued/leased with
382 done at last check — more snapshots keep landing. This pass mined the highest-value
pages found at each check-in (hub pages, official policy PDFs, per-cert overview pages);
deeper/later-arriving snapshots are unmined. To resume: the crawl loop may still be running
(`ps` for `claude_worker.py fetch`); if not, re-run `worker/claude_worker.py fetch --api
http://localhost:8000 --n 8` in a loop. Snapshots are cumulative in `worker/jobs/*.html`
across the whole project history — map `job_id → url` via the DB, not the manifest (the
worker overwrites `jobs.jsonl` every batch).

**Known gaps flagged, not guessed:**
- **ISC2 CPE cycle/fee/annual-minimum is unconfirmed** — the canonical policy URL
  (`isc2.org/policies-procedures/cpe`) 404s and no alternate crawled page states the actual
  numbers (only per-activity credit caps, not the total required). Needs either a working
  URL or a different source.
- **CompTIA Tech+** deliberately excluded from the CEU-table batch — it runs a separate,
  ambiguous scheme (one exam variant with no expiration, another valid 5 years) that
  doesn't fit a single ceu_required/cycle_years pair without guessing which applies.
- **Microsoft expert-tier prerequisites** — the renewal FAQ confirms expert certs require
  an associate prerequisite generically, but doesn't name the specific pairs; needs
  individual cert prerequisite pages.
- **CompTIA's partial-CEU-grant table (job 737 gap check) is now fully captured** via the
  new `partial_credit` effect — no longer a gap.
- ISACA's "fundamentals certificates" tier (badge-level, distinct from full certifications)
  is unexplored — lower priority, noted for a future pass.

**369-item review (done earlier this session, superseded by nothing):** all published via
`publish.py` (certs-first order, 0 errors); local catalog grew 118 → 398 certifications.

---

## ⇢ Session 3, part 1 (2026-07-20)

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
1. **Prod catalog is EMPTY.** The LOCAL sqlite catalog is now **398 certifications / 177
   renewal rules / 30 upgrade paths across 15 providers** (see "Review done" below), but prod
   has none — the public landing shows **no providers** in prod until the catalog is loaded in
   → export local (`dumpdata catalog`) → `loaddata`/fixture or a data migration. **NOT a
   crawl** (local-crawl-only rule stands). This is now the top item for a good prod landing.
2. **Backups NOT set up** — nightly `pg_dump` cron + one restore drill (gcp-setup §1.5). Do
   before relying on prod. (SEC-021's `migrate axes` is additive/safe even without them.)
3. **`EMAIL_URL` unset** → the waitlist "we'll email you" and invites store/queue but send
   nothing until SMTP is configured.
4. RLS enforcement flip — deploy-side non-owner web role (README TODO).

**Review done (2026-07-20):** the **369 pending `StagedChange`s** (all `claude-code-local`:
280 new certs + 84 confirmed renewal rules + 5 upgrade paths, for oracle/adobe/icagile/iapp/
pmi/scrum-org) were reviewed and **published via `publish.py`** (certs-first order; 0 errors,
integrity pre-verified: 0 dupes, 0 dangling refs). Local pending queue is now **empty**;
approver = boris superuser. This is LOCAL sqlite only — see prod gap #1 to get it into prod.

**Crawl in flight (2026-07-20, LOCAL):** a background deterministic fetch worker is draining
~700 queued jobs for CompTIA / ISC2 / Google / ISACA / Microsoft renewal + CE + cert pages
(etag-busted so they re-fetch **rendered**), banking snapshots to `worker/jobs/<job_id>.html`.
Launched **detached** so it survives a Claude Code quota pause (the fetch is deterministic
Python — no LLM). `worker/CLAUDE.md` now carries an expanded per-page capture checklist
(complete renewal fields, `credit_rule`, upgrade/prereq/supersedes edges, cert metadata +
`external_ids`, full cert lists, free offers).
- **Resume extraction from the snapshots** (they are the source of truth — the worker
  OVERWRITES `jobs/jobs.jsonl` + `jobs/auto_results.jsonl` each batch, so don't trust them
  across a multi-batch crawl; map `job_id → url` via the DB `ExtractionJob`, snapshot file is
  `jobs/<job_id>.html`). Dump readable text with `worker/crawl.py`'s
  `_CHROME_RE`/`_SCRIPT_STYLE_RE`/`_TAG_RE` (raw HTML is ~650KB rendered — never read it whole).
- **Extract the GAPS, not the basics** — CompTIA A+/Net+/Sec+ cadence is already in the
  catalog; re-emitting cadence-only rules would create inferior duplicate versions. Chase
  fees, grace periods, CEU category caps, credit rules, and the uncovered providers.
- **Order:** CompTIA, ISC2, Google, then ISACA, then **Microsoft (create the catalog provider
  + certs first)**. Submit via `worker/claude_worker.py submit` (needs the server + a fresh
  worker token — mint stores only a hash) or `/research/ingest/`; then review → publish.
- Regenerate deterministic cert facts across ALL snapshots by running `extractors.py` over
  `worker/jobs/*.html` if the per-batch `auto_results.jsonl` clobbering lost any.

**Open work queue (mostly local / needs-Boris):**
- Promote the crawl-discovered `SourceSubmission`s (this crawl added many more) — next round.
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
