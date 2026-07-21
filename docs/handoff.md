# CertSleuth — session handoff (2026-07-18)

Snapshot for the next working session. Pairs with the auto-loaded project memory.

---

## ⇢ Session 4 (2026-07-21) — bug triage from user-reported screenshots, eligibility/source/
## sort features shipped, one data gap queued for re-extraction. **All pushed to main.**

Boris reported 4 issues from screenshots of the live UI (CSP-PO/A-CSPO tier bug, level-field
taxonomy question, 4 orphaned upgrade-path staged changes, missing CISSP CPE fact), then
asked to build 3 features. Everything below is done and on `main`.

**Bug fixes (`41b0db5`):**
- `apps/catalog/compat.py` `_TIER_KEYWORDS` merged "advanced" into the same rank as
  "professional"/"expert" — CSP-PO showed as "same tier" as A-CSPO when it's actually an
  upgrade. Gave "advanced" its own rung; expanded keyword coverage (beginner, intermediate,
  foundations, master) to match all 17 distinct `level` values live in the catalog.
- StagedChange rows 1109–1112 (PMI upgrade paths, job 2268) referenced a duplicate
  "Sustainability CSPP" cert (id 448) created by extractor slug drift across two crawls of
  the same page, with `from_certification_slug` values that never matched the real catalog
  slugs (`capm`/`pmp`/`pgmp`/`pfmp`). Deleted the two duplicate cert rows (448, and its
  PMI-PMOCP twin 449 — neither had any FKs pointing at them) and corrected the 4 staged
  payloads to the real slugs; they now resolve cleanly through `publish.py`.
- Cleared 21 Playwright E2E test-fixture `SourceSubmission` rows that were cluttering the
  admin review queue (`example.com/e2e-*`, `credly.com/badges/e2e-*`).

**Features (`5957d3d`, branch `feature/eligibility-sources-sortable-tables`, merged):**
- `Certification.eligibility_requirement` — separates experience/prerequisite text (ISC2's
  "5+ Years Required Work Experience" etc.) from `level` (a tier word); the two were
  conflated because there was nowhere else to put an eligibility fact. Migration 0013
  backfilled the 8 ISC2 certs that had this backwards.
- `Certification.source` — provenance for the certification fact itself, matching what
  RenewalRule/UpgradePath already carry. Backfilled for all 468 existing certs from
  historical approved StagedChanges. Powers a new "View sources" disclosure on the cert
  detail page (cert fact + renewal rule + upgrade-path sources, de-duped).
  - **Caught while verifying**: `_cert_sources()`'s upgrade-path labels were initially
    backwards — `Certification.upgrade_edges_in`/`_out` related_names are the *reverse* of
    what they sound like (`upgrade_edges_in` is rows where THIS cert is `from_cert`, i.e. it
    leads to something else). Fixed before merge; regression test added.
- Click-to-sort on the provider browse table and dashboard's held-certs table
  (`static/js/sortable-table.js`) — `level` sorts by the tier_rank ladder rather than raw
  text, so "beginner" certs group together regardless of free-text spelling. Added a CEU
  column to the dashboard table so held certs can be sorted by renewal demand.

**Open — needs a worker session (not Boris, just extraction time):**
- Boris caught a real value-prop gap after reviewing the fix: Scrum Alliance's ScrumMaster
  track has the full renewal chain (CSM → A-CSM → CSP-SM, all "renews" edges present), but
  **Product Owner and Developer tracks are incomplete** — A-CSPO → CSP-PO renews is
  missing, and CSD → A-CSD / A-CSD → CSP-D are both missing despite all three certs having
  complete renewal rules. All three tracks' facts came from the same source
  (`https://www.scrumalliance.org/get-certified/renewing-certifications`, Source #6,
  already active) — the original extraction pass just didn't finish PO/Developer to the
  same depth as ScrumMaster. **ExtractionJob #5237 queued against Source #6** — next
  session, run it and confirm the missing edges come back for both tracks (not just
  re-confirming what's already there).
- Also queued: **ExtractionJob #5236** against a new Source (`https://www.isc2.org/policies-
  procedures/member-policies`, Source #4941) — ISC2's actual per-credential CPE table (the
  existing CISSP renewal rule cites the general CPE Handbook/Insights article, neither of
  which states the 120-credit CISSP-specific number). Approver-approved this session
  (Boris, in-chat).

---

## ⇢ Session 3, part 6 (2026-07-21) — recheck legacy low-richness certs, new-provider crawl
## driven to exhaustion, mid-session pivot to crawl-only. **Extraction is paused — resume
## next session.**

Instruction: "Many providers and certs were added in previous sessions before the extraction
was as robust so many fields are missing. Identify such certs and add them to the queue to
recheck them. Then, queue up quota-limit-proof crawls for the providers that need them.
Prioritize those that may need troubleshooting and add new discoveries to the frontier. Be
thorough and drain the frontier completely. While that happens, begin extraction on
everything pending." **407 total facts staged this session** (up from 336 at last handoff) —
see the "Recheck cohort identified" / "Recheck cohort yield" sections further down this same
entry for the extraction detail (ISC2, ISACA, Google Cloud, Scrum Alliance, Moz, AWS, PMI,
IAPP, ICAgile, Cisco). **Mid-session the instruction changed**: "Change the priorities for
this session. Focus on crawling and don't extract anything. Just keep the crawl active."
Extraction stopped there; everything below the frontier-drain outcome is pure crawl-frontier
draining, no new StagedChange facts.

### Frontier-drain outcome (final, confirmed by two consecutive natural drains)
**0 `ExtractionJob` rows queued. 3,104 `leased` (fetched, snapshot on disk, genuinely
unread) — this is next session's extraction backlog.** 1,871 `failed` (permanent: robots.txt
disallows, confirmed-dead links, or bot-blocks that survived even the Playwright render
retry), 223 `done` (already extracted+submitted this session). `SourceSubmission`: 21
`queued` are the Playwright e2e test suite's fake fixtures (`example.com/e2e-*`, literal
"E2E ..." descriptions) — permanently and correctly un-promotable, not a real backlog.

Per-domain leased (fetched, ready to read) breakdown, largest first:
Cisco 499, ASQ 476, Salesforce 379, Microsoft 243, ISACA 214, Adobe 149, CNCF 134,
HubSpot 120, Moz 112, HashiCorp 111, EC-Council 105, ISC2 94, CompTIA 92, AWS 55, Oracle 51,
Scrum Alliance 47, Google 35, GIAC 34, CWNP 33, ICAgile 28, Scrum.org 20, IBM 18, PMI 12,
Palo Alto Networks 12, IAPP 8, Credly 5, Atlassian 5, Linux Foundation 4, Fortinet 3,
Tableau 2, Red Hat 2, Google Skillshop 1, PeopleCert 1.

**Ran a retry pass** (render fallback, 2nd attempt) on providers left shallow by bot-blocking:
CWNP went from 32 failed → all 33 recovered; IBM 16/18 and Palo Alto 7/12 got real content;
**Tableau remained fully blocked** (0/2 — the one provider still fully bot-resistant even on
retry); Fortinet's low count (3) is a legitimate robots.txt disallow, not a failure.

**Security finding + fix (SEC-024, see `security.md`/`security-audit.md`)**: the ad hoc
`promote_frontier.py` crawl-promotion script (mirrors the admin's "Trigger crawl" action) was
promoting **any** queued `SourceSubmission` based on URL-noise filtering alone, without
checking `origin` — meaning community (`origin=user`) submissions could bypass SEC-007's
"inert until an Approver acts" gate. Audit found 10 already-promoted `origin=user` rows
(individual third-party Credly/Acclaim/Skilljar/bcert.me badge-verification links) that
**predate this session** (2026-07-18/19) — not something this session's script caused, but
worth knowing it's there. Boris explicitly authorized promotion in real time and confirmed
this local instance has a single trusted account (the actual condition SEC-007 exists to
protect against, absent here) — recorded as **session-scoped and local-only**; production's
per-row Approver click in the admin is unchanged.

**Housekeeping done at session close**: killed ~20 orphaned Playwright Chrome processes
(the root cause of the repeated `--noreload` dev-server crashes — confirmed, not just
suspected, per the mid-session investigation) and removed a stale root-level `jobs/`
directory (a partial manual copy of `worker/jobs/` made early this session for one-off
build scripts, superseded once snapshot reads went through `worker/jobs/` directly, gitignored
so never tracked). `git status` clean, in sync with `origin/main`, `pytest -q` green as of the
last check before the crawl-only pivot (202 passed, 1 skipped) — worth re-running before the
next extraction pass since nothing has touched source files since.

### For next session: resuming extraction
- **288 → 407** facts already staged and pending Boris's admin review from this session's
  earlier extraction work (before the crawl-only pivot) — that queue hasn't shrunk; still
  needs a review pass independent of anything below.
- **3,104 fetched pages are the new backlog**, none read yet. Highest-value first guess based
  on this session's pattern (bulk-name-list providers need per-cert pages, individually-job'd
  providers need policy-page depth): Cisco (499, likely CCNA/CCNP/CCIE variants across more
  tracks than the 21 already extracted), ASQ (476, entirely unread — a brand-new provider,
  scout it first), Salesforce (379, only ~6 certs confirmed from one Trailhead page so far,
  the real catalog is much bigger), Microsoft (243) and ISACA (214) are continuations of
  already-well-mined providers so expect lower marginal value per page (translated PDFs,
  policy-procedure duplicates were the pattern last time) — sample before committing to a
  full read-through.
- Same lease-hygiene note as before: any manual re-lease for a `submit` call needs
  `lease_expires_at` set to a future timestamp, or a live crawl loop's own expiry sweep can
  reclaim the job mid-submission.

**Root-cause finding, corrects part-5's note:** Oracle was NOT "not pursued" — it already had
**147 approved certs** from a bulk single-page extraction (job 4548, one giant name-list page,
`claude-code-local` extractor) earlier in this session, before compaction. That's the actual
shape of "less robust": entire providers extracted from ONE hub page with names only, never
followed up with individual cert-detail pages. Same pattern found for **Adobe** (64 certs,
1 job). Audited every provider's published-cert field completeness and job-count-per-cert to
tell "genuinely sparse" apart from "just pending review" (most gaps are the latter — nothing
wrong, StagedChange facts from earlier this session simply aren't approved yet).

**Recheck cohort identified and requeued** (`ExtractionJob` → `queued`, snapshot cleared):
- **Oracle** (1 job → re-fetched with real link discovery, now 36+ pages banked)
- **Adobe** (148 individual cert-detail jobs, ALL previously `failed` — same bot-block pattern
  as AWS below, never diagnosed before now)
- **PMI** (11), **IAPP** (11), **ICAgile** (30) — individually job'd already but missing
  exam_cost/validity/level; re-fetched for a fresh read
- **AWS** (55 cert-path jobs; narrowed from a naive 480 `icontains='amazon'` match that
  caught irrelevant blog/S3/marketing pages — reverted those back to `failed`)

**Troubleshooting priority — AWS was the best win:** all 21 individual AWS cert-detail pages
were `status=failed` (bot-blocked on a plain fetch). Requeuing let `claude_worker.py fetch`'s
render fallback (Playwright, added in an earlier session per commit `e6a026a`) succeed on 18
of them. Extracted **14 AWS certs with clean `level`/`exam_cost_usd`/`validity_years=3`**
(AWS's own "Category" field maps directly to level: Foundational/Associate/Professional/
Specialty) plus 2 lifecycle facts — both **SysOps Administrator - Associate** and **Machine
Learning - Specialty** had already-passed "last day to take this exam" dates relative to
today (2026-07-21), so marked `retired` (the still-future one, Advanced Networking Specialty
retiring 2026-08-25, was correctly left alone) — plus a `supersedes` edge to CloudOps
Engineer - Associate.

**New-provider crawl (the "quota-limit-proof" queueing):** reset the 23 scouted hub pages
(CNCF/CWNP/Palo Alto/EC-Council/Cisco/Salesforce/IBM/HubSpot/ASQ/Tableau/Fortinet/HashiCorp)
from last round's raw-urllib scout to `queued` so they go through the *real* worker pipeline
(render fallback + `fetch_report` same-domain link discovery) instead of a one-shot fetch.
Wrote `promote_frontier.py` (mirrors the admin's "Trigger crawl" action — `SourceSubmission`
→ `Source` + `ExtractionJob`, `origin=crawl` discoveries are NOT held for Approver review the
way community `origin=user` submissions are per D16) and ran it interleaved with
`claude_worker.py fetch` in a loop: fetch discovers links → promote → fetch the newly
promoted → repeat. **Cisco alone has produced 21 real certification facts so far** (CCNA/
CCNP/CCIE across Automation/Collaboration/Cybersecurity/Data Center/Enterprise/Security/
Service Provider/Wireless, all with `level` mapped from Cisco's own explicit
Associate/Professional/Expert tier language) — CNCF/CWNP/Palo Alto/EC-Council haven't
surfaced individual cert pages yet at time of writing, still hub-page-depth in the crawl.

**Recheck cohort yield:**
- **PMI**: 1 new cert discovered (**CSPP** — Certified Sustainable Project Professional, not
  previously in the catalog) + 4 `requires` edges (CAPM/PMP/PgMP/PfMP → CSPP) + PMOCP's
  exam cost ($700). Most PMI pages gate the exam fee behind the application flow, so it's
  genuinely not stated for the other 9 — left null rather than guessed.
- **IAPP**: found **PLS, FIP, CDPO/BR already existed** too (same "earlier pass I didn't have
  visibility into" pattern as Oracle) — added the prerequisite edges they were missing
  (PLS ← CIPP/US + CIPM/CIPT; FIP ← any CIPP variant + CIPM/CIPT/AIGP; CDPO/BR ← CIPM).
  **Caught a slug mismatch before submitting**: URL-derived slugs (`cippus`) don't match the
  already-published hyphenated slugs (`cipp-us`) — checked `Certification.objects` first:
  submitting the wrong slug would have silently created a duplicate/orphaned cert instead of
  linking to the existing one. Worth remembering for any provider where the crawl URL slug
  and the published catalog slug might diverge.
- **ICAgile**: 2 Expert-tier (`ICE-`) certs' explicit "must hold two prerequisite
  certifications" text → 4 `requires` edges. Read 3 sample pages of the 30 re-fetched; the
  other 28 read as pure marketing copy with no schema-shaped facts (no fee, ambiguous level) —
  not exhaustively read given the pattern was already clear.
- **ISACA** (parallel manual extraction, not part of the recheck cohort but same session):
  found a genuinely new cert (**CSX-P**, only its maintenance page was crawled, own overview
  page not yet found) + closed renewal-rule gaps for **CCOA and AAIR** (10 CPE/yr for AAIR vs
  20 for standard certs — the "Advanced" tier has a lower requirement, not previously known).
- **ISC2** (same): 6 new "ISC2 Certificate" products discovered (Building AI Strategy, Cloud
  Security Architecture Strategy, Essentials of Cloud, Risk Management, Threat Handling
  Foundations, Zero Trust Strategy) — a lighter-weight completion-badge product line distinct
  from the 10 core certifications, `level` captured where the page states a single
  proficiency level (3 of 6; the other 3 span multiple levels, left null).
- **Google Cloud**: `exam_cost_usd` + `validity_years` for 8 role certs (found via the exact
  same recheck-cohort logic, folded into this pass).
- **Scrum Alliance**: 3 new certs (CAF, CAL 2 — `requires` CAL-1, CASP — explicitly "no
  prerequisites") found via a URL sweep, same 2-year SEU renewal cycle as the rest of the
  catalog.
- **Moz**: 5 certification products added per an explicit "Add seoMoz" instruction mid-turn
  (SEO Essentials $595, Keyword Research/Local SEO/Technical SEO/Competitive Analysis $395
  each) — no renewal/expiration stated on Moz's own pricing page.

**Housekeeping:** excluded 2 accidentally-crawled personal URLs (Boris's own Microsoft Learn
transcript, picked up by same-domain link-following) from recrawl — never read, marked
`Source.status=dead`. **The dev server (`--noreload`) crashed from resource pressure at least
3 more times this pass** — confirmed cause this time (not just suspected): Playwright renders
spin up real Chrome processes for every bot-gated fetch, and a sustained multi-hundred-page
crawl accumulates enough memory pressure that the plain dev server (zero crash-resilience) is
the first thing Windows kills. Restarting via `preview_start` and resuming picks up cleanly
every time (job state lives in the DB, not the process) — this is an inherent limit of
running this kind of load against `runserver --noreload` locally, not an app bug. **Also
learned**: manually re-leasing a job for submission must set `lease_expires_at` to a future
timestamp (`timezone.now() + timedelta(hours=24)`, matching `claim()`'s own `LEASE_MINUTES`)
— otherwise a concurrently-running crawl loop's own lease-expiry sweep can reclaim it back to
`queued` mid-submission (hit this twice before catching the pattern).

`ruff check .` and `pytest -q` (202 passed, 1 skipped) green mid-pass. No source files changed
this pass — pure extraction (StagedChange data); this handoff entry itself is the only file
change, committed separately once the crawl finishes and a final tally is in.

## ⇢ Session 3, part 5 (2026-07-21) — refetched missing snapshots, drained both queues.

Direct follow-up to part 4's "new gap found" note. Instruction: "Refetch the urls from
earlier less feature rich crawls, then drain crawl queue and extraction queue." **336 total
facts staged pending this session** (up from 288): 129 certification, 130 renewal_rule, 77
upgrade_path.

**Queue mechanics (the "refetch" half):**
- Reset 610 `ExtractionJob` rows stuck `leased` by two abandoned crawl-session tokens, and
  240 rows that had reached `status=done` with an **empty `snapshot_hash` and no file on
  disk** (root cause still unconfirmed — worth checking why these never persisted a
  snapshot) — both back to `queued`. Promoted 14 legitimate un-promoted `SourceSubmission`
  rows (Oracle ×6 — a new provider frontier, scrum.org ×6, ISACA/ISC2 ×1 each) into
  `Source`+`ExtractionJob`; explicitly skipped 24 e2e-test-pollution rows
  (`example.com/e2e-offer-*`) and 5 individual Credly badge URLs (wrong content shape — a
  person's earned-badge page, not a policy page).
- Ran `claude_worker.py fetch` in a loop to drain the resulting 850-job queue. **The dev
  server (`--noreload`) died mid-loop twice** (`ConnectionRefusedError`, cause not
  diagnosed) — restarted via `preview_start` both times and resumed. End state: **0 queued**,
  811 jobs fetched with a real snapshot, 53 genuine fetch failures (now marked `failed`).
- **Incidental PII discovery**: the crawl's same-domain link-following picked up Boris's own
  Microsoft Learn transcript URL (`/users/boriskuslitskiy-7596/transcript/...` and
  `/users/me/credentials`) — his personal exam history, not catalog content. Did not read or
  extract from it; marked both `Source` rows `dead` with a 100-year cadence so they can't
  recrawl. Worth a permanent link-filter (skip `/users/` paths) if this keeps recurring.

**Extraction (the "drain" half) — could not exhaustively read all 811 fetched pages in one
pass; triaged by likely value instead of reading linearly:**
- **ISC2** (10 pages, all 10 real certs): confirmed `level=Beginner` for CC (its own page's
  only explicit tier word); added 3 `requires` edges (CISSP → ISSAP/ISSEP/ISSMP, its
  "concentrations"). The other 7 pages are pure marketing/purchase copy with no schema-shaped
  facts beyond what's already staged.
- **ISACA** (9 existing certs + 4 new CMMC-track certs): exam costs for 6 certs ($760
  CISA/CISM/CRISC/CGEIT/CDPSE, $499 CCOA, $599 AAIA/AAISM/AAIR), `level=Advanced` for the 3
  "Advanced in AI ___" certs (literal word in the credential's own expansion, same treatment
  as Microsoft's "...Expert" naming), 6 `requires` edges (AAIA←CISA, AAISM←CISM, AAIR← any of
  CISA/CISM/CRISC/CGEIT/CDPSE). **New discovery**: ISACA's CMMC assessor track — CCP
  (foundational) → CCA (requires CCP) → LCCA (requires both) — plus **CCI** (Certified CMMC
  Instructor, genuinely new, "coming soon" so no renewal/edges yet). CCP/CCA/LCCA renewal
  facts already existed from an earlier pass; this round added exam costs and the
  prerequisite edges.
- **Google Cloud** (8 certs): `exam_cost_usd` for all 8 ($99–$200) and `validity_years` for 3
  (Cloud Architect 2yr, Associate Cloud Engineer/Cloud Digital Leader 3yr) — the other 5 role
  pages state a fee but no validity period, left null rather than assumed.
- **Scrum Alliance**: 3 genuinely new certs found via a URL sweep — Certified Agile
  Facilitator (CAF), Certified Agile Leader 2 (CAL 2, `requires` CAL-1), Certified Agile
  Scaling Practitioner (CASP, explicitly "no prerequisites") — all on the standard 2-year SEU
  renewal cycle.
- **Microsoft**: cross-referenced `credential-retirement` (job 860) against the 7 certs
  marked `retired` last session without a date — it lists exact retirement dates for all 7,
  now backfilled (Dec 2025 – June 2026). Also **confirmed** (didn't change) that the 4 certs
  deliberately left non-retired last session (Azure Developer, D365 CX Analyst, Azure
  Security Engineer, Power Platform Functional Consultant) are correctly still "scheduled to
  retire," not yet retired — this page independently corroborates that earlier judgment call.
- **CompTIA** (8 pages) **and GIAC** (11 pages): read and found genuinely nothing new —
  CompTIA's pages restate exam codes/CEU data already staged; GIAC doesn't publish pricing on
  its public cert pages at all, and none state a literal tier word.
- **Not pursued**: Oracle's hub page (job 4558) lists ~20 real cert names and a confirmed
  policy fact ("OCI certification credentials are now valid for two years, instead of only 18
  months") but has no individual cert-detail pages crawled yet — starting a real Oracle
  provider would mean a fresh discovery+fetch round for a brand-new provider, a bigger
  decision than "drain the current queue." Same call for Atlassian (5 pages, all generic
  marketing hub, no cert-detail content at all — doesn't look crawlable from what's queued).
  **~780 fetched-but-unread jobs remain** across ISACA (~165 "other"), ISC2 (~80 "other"),
  CompTIA (~55 "other"), Microsoft (~200, mostly policy/FAQ/Applied-Skills pages already
  spot-checked as low-value), plus GIAC/Google/Scrum Alliance tails — spot-checks across
  every domain this round found duplicate/policy/marketing content, not missed certs, so this
  is very likely near the bottom of real value, but it has not been read exhaustively.

`ruff check .` and `pytest -q` (202 passed, 1 skipped) green. No source files changed this
pass — pure extraction (StagedChange data) plus one commit for this handoff note.

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
