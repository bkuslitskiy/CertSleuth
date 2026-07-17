# CertSleuth — Product & Technical Spec (v0.3)

v0.3: named, stack chosen, testing strategy set (D19–D21). Kickoff questions in §8.

**Branding:** wordmark rendered in three colors segmented as **Cert** / **Sle** / **uth**. (Palette TBD — kickoff Q; segmentation is fixed.)

## 1. Problem & Goals

Professionals hold certifications across multiple bodies (ISC2, Atlassian, Scrum Alliance, Google, CompTIA, ISACA, …). Each body has its own renewal cycle, CEU/CPE/SEU currency, fees, upgrade paths, and intermittent free offerings. No existing product unifies these, and none automates the three hard parts:

1. **Cross-crediting** — one activity counting toward multiple bodies' CEU requirements.
2. **Upgrade-renews logic** — earning cert B renewing cert A (e.g., CompTIA pyramid, Scrum Alliance A-CSM→CSM).
3. **Living rules** — providers change requirements; free offers appear and expire.

**Goals:** single dashboard per user; canonical, versioned, provenance-tracked rules catalog; automated research pipeline with human review; minimal manual entry; security-conscious throughout.

**Non-goals (v1):** system of record (provider portals stay authoritative); evidence-document storage; study planning; team/org compliance; mobile apps. See `post-mvp-backlog.md`.

**Launch provider set (D2):** ISC2, Atlassian, Scrum Alliance, Google (Career Certificates + GCP), AWS, Microsoft/Azure, CompTIA, ISACA, GIAC, PMI. Cloud + security + tech management: personally relevant and the largest cert populations.

---

## 2. Domain Model (core entities)

| Entity | Purpose | Key fields |
|---|---|---|
| `User` | Account | auth identity, role, notification prefs |
| `Provider` | Cert body | name, portal URL, CEU currency name, fee structure |
| `Certification` (catalog) | Canonical cert definition | provider, name, level, exam cost, validity period, CEU requirement, rule_version |
| `RenewalRule` (versioned) | How a cert renews | CEU count, categories, fees, grace period, effective_date, source_ref, **confidence** |
| `UpgradePath` | Cert→cert edges | from_cert, to_cert, effect (`renews`/`waives_fee`/`supersedes`), source_ref, **confidence** |
| `UserCertification` | A user's held cert | cert ref, earned/expiry dates, **cert number**, **external evidence URL**, import_source |
| `UserGoal` | Cert a user wants | target cert, target date |
| `Activity` | A CEU-earning event | user, title, date, hours, external evidence URL |
| `CreditMapping` | Cross-crediting ledger | activity → (provider, category, credits, per-portal submission status), **confidence** |
| `FreeOffer` | Intermittent freebies | what's free, eligibility, start/end, source_ref, submitted_by, status |
| `Source` | Provenance | URL, fetch timestamp, content hash, cadence, submitted_by |
| `SourceSubmission` | Community-suggested source | URL + short description, submitter, status (queued/crawled/rejected) |
| `ChangeReport` | "This is outdated" feedback | entity ref, note, status |

**Identity convention (D26):** every entity carries a numeric surrogate primary key (Django `BigAutoField`) — never names. Names are mutable display fields (providers rebrand, certs get renamed — "Google Auth platform" was "OAuth consent screen" until 2024-style renames are routine). URLs use stable slugs (separate column, changeable with redirect history); external identifiers (Credly badge-template IDs, provider SKUs) live in their own unique-indexed columns for import matching. Rule versions reference cert PKs, so a rename never orphans history.

**Two orthogonal quality signals on every rule-ish fact (D3, D8):**
- **Staleness** (when did we last verify the source): 🟢 verified < 1 week · 🟡 < 1 month · 🔴 > 1 month. Rendered as a color-coded chip with `last_verified` tooltip on every rule, path, mapping, and offer.
- **Confidence** (how sure are we it's true at all): `confirmed` (cited to provider handbook/policy section) · `commonly_accepted` (widely reported, not found verbatim in provider docs — most cross-crediting lives here) · `inferred` (our extrapolation, flagged prominently). Cross-crediting rules default to `commonly_accepted` until a handbook citation upgrades them.

**Evidence policy (D7):** store cert numbers, expiration dates, and links to evidence hosted elsewhere (Credly URL, drive link). Never store evidence documents. All user-entered certs are trusted as genuine — users have no incentive to deceive their own tracker, and dropping verification removes an entire compliance/storage burden.

**Rules are versioned, never overwritten** — a user renewing under 2025 rules while 2026 rules exist is a real scenario.

---

## 3. Feature Modules

### 3.1 Dashboard
Per-user: held certs with expiry countdown, CEU progress per requirement bucket, fees due, "cheapest path to renewal" hints from the upgrade graph. Goals shown with prerequisite/upgrade edges. Staleness + confidence chips on every displayed rule.

### 3.2 Activity Ledger & Cross-Crediting
Log an activity once (or import, §5); system proposes eligible `CreditMapping`s per provider category rules; user confirms. Tracks per-portal submission status (submitted/approved/rejected). Audit-export bundles per provider (metadata + evidence links).

### 3.3 Upgrade Graph
Directed graph over the catalog. Queries: "what next earns the most renewals," "total cost of ownership of my stack under intent-level rules."

### 3.4 Free Offers Feed (D12)
Filterable feed matched to held certs + goals; auto-hide past end date; notify matching users. **All tiers may submit offers**; submissions from Approver+ users are prioritized in the review queue and can be fast-tracked. Offers carry staleness chips like everything else.

### 3.5 Research Pipeline (D3, D16)
```
Source registry  ←  seeded sources
                 ←  Approver+ queue URLs directly
                 ←  SourceSubmissions (any user: URL + description)
       │
Scheduler (per-source cadence: weekly rules pages, daily offer pages)
  → Fetcher (plain HTTP; snapshot + hash)          [no headless browser at v1 — D11]
  → Change detector (hash diff; skip if unchanged)
  → **Extraction job queue** (`extraction_jobs`: queued → leased → done/failed)
      ├─ Local worker (Claude Code on Boris's rig, operator-driven; D17) — preload & bulk
      └─ Server API worker (prepaid credits) — steady-state trickle, fallback
  → Structured JSON (server-side schema validation regardless of extractor)
  → Diff vs canonical → Staging queue
  → Approver/Admin review UI (approve / edit / reject)
  → Publish as new rule_version → notify affected users
```
**Worker protocol (D17):** the app exposes an authenticated worker API — `claim` (lease jobs with TTL; expired leases return to queue) and `submit-result` (schema-validated JSON only, write-scoped to the staging queue). Workers **pull**; the server never connects inward, so the home network is never exposed. Provenance records the extractor identity (`claude-code-local`, `api-haiku`, `local-<model>`), and locally-extracted facts can carry an extractor tag visible at review time. Server-side JSON Schema validation + mandatory human review make extractor output untrusted-by-default, so a flaky local model can waste review time but can't corrupt canonical data.

**Ingest modes (both MVP — preload priority):**
1. **Live worker API** — as above; suits ongoing operation.
2. **Batch JSONL upload** — Admin exports queued jobs as a job manifest (`jobs.jsonl`: job_id, source URL, snapshot ref); any offline process (plain Claude Code today, anything later) produces `results.jsonl` against the published extraction schema; Admin uploads it and every record passes the same schema validation into the same staging queue. Fully decoupled from app availability and from how/where the processing ran. This is the initial-preload path: hundreds of provider pages processed offline under the Pro subscription, then loaded in one review pass.
- **Community sources are crawl-on-demand only**: a `SourceSubmission` sits inert until an Approver+ user triggers its crawl. Untrusted users cannot cause fetches or LLM calls, so the queue can't be spammed to drain the token budget (D16). Scheduled crawling applies only to Approver-promoted sources.
- Nothing auto-publishes; LLM proposes, human approves.
- A `ChangeReport` ("report outdated" button on every fact) auto-flags the fact, bumps its source in the review queue, and notifies the reporter on resolution. N reports → "disputed" badge until resolved.

### 3.6 Notifications (D5)
Purpose: reminders and change alerts. Channels:
- **Email**: approaching expirations (90/30/7-day), CEU pacing shortfalls, rule changes affecting held certs, matching new free offers, review-queue items (Approver+).
- **Calendar (ICS)**: per-user tokenized read-only feed containing expiration events and reminder alarms; subscribable from any calendar app. Covers "reminders + expiration" without building push infrastructure.

---

## 4. Users, Roles & Registration (D1, D3)

- **Roles:** `User` → `Approver` (review queue, direct URL queueing, fast-track submissions) → `Admin` (Approver powers + user management, registration toggle, config).
- **Registration:** invite-only at launch. Admin toggle enables open registration; when active-user count reaches **90**, new signups divert to a waitlist (headroom under Google's 100-test-user OAuth cap, which requires individually enrolling accounts in the console — invite-only pairs naturally with that list).
- Auth: email/password + Sign-in-with-Google (basic scopes only — no CASA implication); optional TOTP 2FA.
- **Gmail test-user enrollment (D25), semi-automated:** Google provides no API for managing consent-screen test users — the list is maintained in the console UI (Audience → Test users), and adjacent programmatic surfaces have been retired (the IAP OAuth admin APIs were shut down in March 2026), so full automation isn't on the table. Design: the invite/signup flow captures the user's Gmail address and creates an admin task; the admin panel shows a "pending console enrollment" queue with copy-paste-ready address batches; admin pastes into the console, marks done; only then does the user's "Scan my inbox" button unlock. Automation to the ceiling Google allows, manual for the one step it doesn't.
- Data isolation: single-DB multi-tenant, app-level scoping + Postgres RLS.

---

## 5. Minimizing Manual Entry (import strategies, ranked)

### 5.1 Gmail scanning — in scope (D13: on-demand only)
`gmail.readonly` (restricted scope). Unverified external apps: ~100 test users, and "Testing" publishing status expires refresh tokens after ~7 days — acceptable because the design is a **one-shot on-demand scan**: user clicks "Scan my inbox" → fresh OAuth consent → single pass → token discarded. No stored Gmail tokens, no background sync. Re-verify current Google token policy before build.
- Query known issuer senders (`from:credly.com OR from:isc2.org OR …`), never crawl the whole mailbox.
- Extract-and-discard: persist message-ID + extracted fields + confidence, never raw bodies.
- If the user base ever exceeds the cap, CASA Tier 2 is the accepted cost (D-context: ~$500–few $k/yr).

### 5.2 Credly import — do first (D6)
Atlassian, GCP, and ISC2 issue Credly badges. Official API is org-only, but public profiles expose `https://www.credly.com/users/{username}/badges.json` (unauthenticated, undocumented). User pastes profile URL → parse → match against catalog → prefill (user confirms). **Accepted with backups in place** — 5.3/5.4 cover breakage.

### 5.3 Open Badges file upload (backup to 5.2)
Earned badges download as OpenBadge 2.0/3.0 .png/.svg/.json with baked, verifiable assertion metadata. Upload → parse. Works for private profiles.

### 5.4 Certificate/transcript upload + LLM extraction
Any cert PDF, wallet-card photo, or CPE transcript → LLM extracts issuer/name/dates/number into a prefilled form. Catch-all for badge-less providers. Uploaded file is parsed then discarded (D7 — we keep extracted fields + the user's own hosted link if provided).

### 5.5 Provider profile URL scraping (D6: public pages OK)
Scrum Alliance public member profiles (certs + expiry); Coursera public accomplishments (Google Career Certs); Microsoft Learn public transcript share links. ISC2 has no public directory — Credly/upload covers it. LinkedIn: closed API + hostile ToS → accept the user's own LinkedIn data export (Certifications.csv) instead.

### 5.6 CSV import + manual entry — always-available floor.

**Onboarding:** Connect Credly → upload badges/certs → Gmail scan → LinkedIn export → manual.

---

## 6. Architecture & Hosting (D9, D10)

**Shape:** server-rendered app (not SPA) + Postgres + job worker + scheduler + transactional email (Resend/Postmark — also provides inbound parsing for the forwarding-inbox in the backlog).

**Stack (D19): Python.** Recommendation within Python: **Django** over FastAPI+HTMX — the deciding factor is Django admin, which gives the Approver review queue, staging-diff inspection, source registry, and user management as near-free scaffolding (customized admin views beat hand-building that UI), plus mature auth, ORM migrations, and `django-rls`-style policy patterns. FastAPI is the better pure-API framework, but this app is mostly server-rendered CRUD + a small worker API. Celery or Django-Q for jobs; httpx for fetching; Pydantic for the extraction schemas shared with the JSONL contract.

**Testing (D21):** written as-you-go, per feature, not batched at the end:
- **Playwright E2E** — one spec file per feature module as it lands (auth/invite flow, cert entry, Credly import, ledger mapping, review queue approve/reject, offers feed, ingest upload). Runs headless in CI against a seeded test DB; smoke subset on every PR, full suite nightly.
- **pytest** — unit + integration beneath: extraction-schema round-trip fixtures (every `results.jsonl` sample must validate), RLS policy tests (cross-tenant access attempts must fail at the DB layer), worker-API lease/idempotency tests.
- Fixtures double as documentation: seeded catalog + rules for two providers gives Playwright a realistic world.

### Hosting analysis (constraint: existing SiteGround shared hosting, or AWS/GCP/Azure free tiers)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **SiteGround shared** | Already paid; zero new accounts; trivial TLS/DNS | PHP/MySQL-centric; no Postgres; no long-running worker processes or queues; cron is limited; can't run the research pipeline or Docker | ❌ for the app. ✔️ for marketing page/DNS only |
| **GCP e2-micro (Always Free)** | Genuinely permanent free VM (US regions); full root: Docker Compose runs app+Postgres+worker+Caddy on one box; no expiry cliff | 1 GB RAM is tight (fine at this scale if Postgres is tuned down); Cloud SQL NOT free — DB must live on the VM; egress limits; you own patching/backups | ✅ **best fit** |
| **AWS free tier** | 12-mo EC2 t-class + RDS free; biggest ecosystem | Free tier **expires at 12 months** → migration or surprise bills; RDS-free also temporary; billing foot-guns are real | ⚠️ fine, but plan the month-13 exit |
| **Azure free tier** | 12-mo B1s VM; $200 initial credit; pairs with Microsoft cert interest | Same 12-month cliff; free-service maze | ⚠️ same caveat |

**Recommendation:** one GCP e2-micro running Docker Compose (app, Postgres, worker, Caddy), nightly `pg_dump` to object storage, SiteGround keeps the landing page. Cost: ~$0/mo + domain. Upgrade path: bump the VM or lift the compose file to a $10–20/mo VPS when 1 GB hurts — nothing about the architecture changes.

### LLM strategy — hybrid extraction plane (D17)
A Claude **Pro subscription does not cover a hosted app's API calls** (Console/API billing is separate). But the subscription *can* do the heavy lifting through Claude Code running locally, because extraction is queue-based and asynchronous:

- **Preload / bulk (subscription-funded):** seed the source registry with hundreds of provider pages → jobs pile up in `extraction_jobs` → Claude Code on the existing WSL2 rig claims batches via the worker API, fetches + extracts, submits schema-validated results. Operator-driven sessions (kick off a batch, let it churn within plan usage windows) — this is your own curation tooling under your own login, which is the right side of the subscription-vs-API line. Keep it operator-initiated rather than a 24/7 headless daemon; automated always-on service traffic is what API billing is for, and Anthropic's routing/policy here has been a moving target — re-verify at build time.
- **Local models (optional, later):** no gateway required — if ever wanted, the worker can point at Ollama's or vLLM's OpenAI-compatible endpoint directly for $0 extraction. Structured-output quality from ~14B-class models will vary; mitigations if pursued: JSON Schema retry loops, escalate validation failures to Claude, and let review-time extractor tags reveal which models earn trust. Not assumed for v1 — Claude Code alone covers preload.
- **Steady-state / user-facing (API credits):** synchronous, always-available paths — Gmail on-demand scans, certificate upload parsing, and the trickle of scheduled re-crawls when the local worker is offline — run on prepaid API credits. With preload offloaded, this shrinks to **single-digit $/mo** at launch scale.

Direction of your "can the API call my local models" question inverted: the hosted app never reaches into your LAN. The local worker *pulls* jobs and *pushes* results — your gateway and models stay unexposed.

### Headless browser (D11: not v1) — when it would ever be needed
Only if a source renders its content client-side in JavaScript (React/SPA pages where raw HTML is an empty shell) or sits behind bot-mitigation requiring a real browser. Launch sources — provider policy/handbook/pricing pages — are static HTML. Revisit per-source if a fetch returns skeleton HTML.

---

## 7. Security Posture

Target: **OWASP ASVS Level 2-aligned from day one** so a future CASA is a formality. Two living documents in the repo (D18): **`security.md`** — every security-relevant decision with rationale and trade-off, appended at decision time, never retroactively; **`security-audit.md`** — the ASVS L2 verification ledger (control → status → evidence), kept assessment-ready continuously.

**Identity & access** — hardened auth library (no hand-rolled passwords); optional TOTP; httpOnly+SameSite sessions; rate-limited login; Postgres RLS under app scoping; role checks server-side per route; Approver/Admin actions audit-logged.

**Secrets & tokens** — provider creds and any OAuth tokens envelope-encrypted, keys in a secret manager; Gmail scan tokens never persisted (§5.1); no secrets in repo/env-committed files.

**Data handling** — D7 shrinks the classification: no evidence documents, no raw email bodies; sensitive-ish residue is cert numbers → encrypt at rest at the app layer. External evidence links are user-provided pointers, not our custody. Full account deletion (certs, activities, derived data). TLS/HSTS/strict CSP; no third-party analytics on authed pages.

**Pipeline** — all fetched pages, uploaded docs, and scanned emails are untrusted LLM input: schema-constrained extraction, no tool access from extraction contexts, provenance stored separately from content; extraction workers cannot read user PII tables. Community `SourceSubmission` URLs are crawled only on Approver action (D16) — spam cannot trigger fetches or spend.

**Process** — dependency/container scanning in CI; commit secret-scanning; least-privilege infra IAM; periodic ZAP self-DAST against staging.

**Is ASVS L2 a hardship? (D14)** — answered in accompanying discussion; short version: no, at this scale. ~90% of L2 controls are framework defaults plus discipline you'd apply anyway; the real cost is verification bookkeeping. Approach: adopt the L2 chapters for auth, session, access control, validation, and crypto as the build checklist; keep a lightweight controls log as you go; defer a formal full-catalog audit to a pre-CASA milestone.

---

## 8. Decisions Log & Remaining Questions

| # | Decision |
|---|---|
| D1 | Invite-only at launch; admin toggle for open registration; waitlist at 90 active users |
| D2 | Broad launch catalog: ISC2, Atlassian, Scrum Alliance, Google/GCP, AWS, Azure, CompTIA, ISACA, GIAC, PMI |
| D3 | Review queue: Boris + Approver/Admin roles; Approver+ can queue URLs; staleness chips 🟢<1wk 🟡<1mo 🔴>1mo |
| D4 | No study planning in v1; post-MVP backlog file started |
| D5 | Email = reminders; ICS calendar feed = reminders + expirations |
| D6 | Public provider pages scrapeable; undocumented Credly endpoint OK given backups (Open Badges upload, doc parsing) |
| D7 | Store cert numbers, expirations, external evidence links; no evidence docs; trust user-entered certs |
| D8 | Confidence levels (`confirmed`/`commonly_accepted`/`inferred`) on rules, distinct from staleness |
| D9 | Hosting: **GCP confirmed** — e2-micro + Docker Compose; SiteGround for static landing only |
| D10 | LLM: hybrid plane (see D17); API prepaid credits only for user-facing/steady-state — single-digit $/mo |
| D11 | No headless browser at v1 |
| D12 | User-submitted offers from all tiers; Approver+ submissions prioritized |
| D13 | Gmail = on-demand one-shot scan only |
| D14 | ASVS L2-aligned checklist during build; formal audit deferred to pre-CASA milestone |
| D15 | Free now; paid tier later (backlog) |
| D16 | Community sources = submit URL+description → inert until Approver+ triggers crawl (token-drain protection) |
| D17 | Hybrid extraction: preload/bulk via local Claude Code worker (subscription, operator-driven, pull-only); API credits for user-facing + steady-state; local models optional later (no LiteLLM setup exists — direct Ollama/vLLM endpoint if ever pursued) |
| D18 | "Do it right the first time": maintain ASVS L2 assessment readiness continuously; security decisions/trade-offs logged in `security.md`, verification bookkeeping in `security-audit.md` |
| D19 | Stack: Python (Django recommended — see §6) |
| D20 | Name: **CertSleuth**; tri-color wordmark segmented Cert/Sle/uth |
| D21 | Playwright E2E written as-you-go per feature; pytest beneath (see §6 Testing) |
| D22 | Django confirmed |
| D23 | certsleuth.com purchased; DNS/landing at SiteGround; hosted privacy policy page is a pre-Gmail-feature dependency |
| D24 | Full catalog depth — hundreds of certs across the 10 providers; richer test data outweighs preload cost; review UI gets bulk approve/reject by provider/source for the preload pass |
| D25 | Test-user enrollment folded into invite flow, semi-automated (no Google API exists — see §4) |
| D26 | Numeric surrogate PKs for all entities; names are mutable display fields; slugs + external-ID columns separate (see §2) |
| D27 | Defaults locked: GitHub private + Actions CI; nightly `pg_dump` to GCS, 30-day retention, restore tested at milestone 1; Sentry free tier + UptimeRobot; per-user timezone stored, fees USD-only v1; ASVS version pinned at repo kickoff per CASA's current mapping |

**Still open (non-gating):**
1. Wordmark palette — the three colors + dark-mode variants for Cert/Sle/uth.
2. Privacy policy + ToS text — needed before the Google consent screen; draft on request.

**Next spec-phase artifacts (pre-build, on request):** extraction schema v1 (Pydantic + JSONL contract), seed source list (~3–8 URLs × 10 providers), privacy policy draft.

**Sequencing (rev. 2026-07-16):** multi-AI dev environment is parked in the global backlog — **not a blocker**. Preload runs on plain Claude Code as it exists today. **Prioritized for MVP: the async-data ingest path** — build ingest + staging + review early (either §3.5 mode) so preload can begin while the rest of the app is still under construction.
- 2026-07-16: schema v1 gained renewal_fee_usd (per-cycle) — surfaced by the Scrum Alliance sample set.
