# security-audit.md — ASVS L2 Verification Ledger

Bookkeeping counterpart to `security.md` (which holds the *why*; this holds the *proof*). One row per control area; expand rows into per-control entries as implementation lands. Statuses: `planned` → `implemented` → `verified` (evidence linked) | `n/a` (justification required).

**ASVS version: TBD at repo kickoff (4.0.3 vs 5.0) — record the pin as SEC-011 in security.md and restructure chapter numbers here if 5.0.** CASA alignment is the driver.

Review cadence: touch this file in every PR that lands security-relevant code; full pass at each milestone; formal audit at pre-CASA milestone.

| Ch. | Area | Status | Evidence / Notes | Related SEC | Last reviewed |
|---|---|---|---|---|---|
| V1 | Architecture, threat modeling | planned | Spec §7; threat notes in security.md; data-flow diagram TODO at repo kickoff | SEC-001..010 | 2026-07-16 |
| V2 | Authentication | planned | Hardened auth library (no hand-rolled); TOTP optional; rate-limited login | SEC-009 | 2026-07-16 |
| V3 | Session management | planned | httpOnly + SameSite cookies; server-side session invalidation on logout/role change | — | 2026-07-16 |
| V4 | Access control | partial | Server-side role checks per route (User/Approver/Admin); role-based admin perms implemented + tested; Postgres RLS mechanism verified on PG under a non-owner role (tests/test_rls.py, SEC-016) — enforcement flip needs the deploy-side non-owner role; worker tokens scoped claim/submit-to-staging only | SEC-004, SEC-008, SEC-012, SEC-016 | 2026-07-17 |
| V5 | Validation, sanitization, encoding | partial | JSON Schema on ALL extractor ingest (both modes); the in-flow deterministic extractor's output is asserted schema-valid against the shared v1 contract in tests (tests/test_worker_autoextract.py, SEC-018) and routed to staging, never the catalog; parameterized queries only; output encoding via framework templates | SEC-005, SEC-018 | 2026-07-18 |
| V6 | Stored cryptography | planned | Envelope encryption for tokens + cert numbers; keys in GCP Secret Manager; no custom crypto | SEC-009 | 2026-07-16 |
| V7 | Error handling & logging | planned | Audit log for Approver/Admin actions; no secrets/PII in logs; structured logs off-box | — | 2026-07-16 |
| V8 | Data protection | partial | No evidence docs (SEC-001); Gmail scan implemented stronger than extract-and-discard — metadata-only fetch (bodies never leave Google), per-scan online token confined to one request frame, signed user-bound state (tests/test_gmail_execution.py, SEC-020); full account deletion; data classification table in spec §7 | SEC-001, SEC-003, SEC-020 | 2026-07-19 |
| V9 | Communication | planned | TLS everywhere; HSTS; Caddy auto-TLS on the VM | — | 2026-07-16 |
| V10 | Malicious code | partial | CI dependency + container scanning; commit secret-scanning; pinned dependencies. Worker renders untrusted provider pages in sandboxed headless Chromium (SEC-019) — operator-side only, never imported by the server; no page-supplied script is evaluated by our code, non-document subresources aborted, 20s cap | SEC-006, SEC-019 | 2026-07-18 |
| V11 | Business logic | partial | Crawl-on-demand gate for community sources (SEC-007) verified in code + tests (offer/badge/source submissions all inert; spend triggers approver-only per SEC-013 audit); waitlist cap logic; lease TTL on job claims | SEC-007, SEC-013 | 2026-07-17 |
| V12 | Files & resources | planned | Transient-only upload parsing (SEC-001); signed short-lived URLs if any object access; upload size/type limits | SEC-001 | 2026-07-16 |
| V13 | API & web service | planned | Worker API: per-worker tokens, least scope, rate limits; ingest schema-validated; no server-initiated outbound to operator network (SEC-004) | SEC-004, SEC-005 | 2026-07-16 |
| V14 | Configuration | partial | No secrets in repo (gitignore) or images (.dockerignore excludes .env, verified via smoke test — SEC-014); least-privilege GCP IAM and ZAP self-DAST still planned | SEC-009, SEC-014 | 2026-07-17 |

## Assessment-readiness checklist (maintain continuously — D18)
- [ ] Every `implemented` row has linked evidence (PR, config, test)
- [ ] Data-flow diagram current (update on any new ingest/egress path)
- [ ] security.md entry exists for every accepted risk / trade-off
- [ ] Dependency scan green at last release
- [ ] Last ZAP self-DAST date within 90 days: ____
- [ ] ASVS version pinned (SEC-011): ____
