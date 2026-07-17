# security.md — Security Decisions, Considerations & Trade-offs

Append-only log. Every security-relevant decision gets an entry at decision time, never retroactively. Format: ID | date | decision | rationale | trade-off accepted. Verification bookkeeping lives in `security-audit.md`; this file is the *why*.

---

## SEC-001 | 2026-07-16 | No evidence-document storage
**Decision:** Store cert numbers, expiration dates, and user-provided links to externally hosted evidence only. Never ingest or retain evidence documents (PDFs, certificates, transcripts beyond transient parsing).
**Rationale:** Removes the highest-sensitivity data class from custody entirely; shrinks breach blast radius, backup sensitivity, deletion obligations, and future CASA evidence scope.
**Trade-off:** Users must keep evidence elsewhere; audit-export bundles contain links, not files. Accepted — provider portals are the system of record anyway.

## SEC-002 | 2026-07-16 | Trust user-entered certifications
**Decision:** No verification of cert authenticity; all user-entered certs treated as genuine.
**Rationale:** Users have no incentive to deceive their own tracker. Verification would require handling verification identifiers and third-party checks for zero product value.
**Trade-off:** Public-profile features (post-MVP) must NOT imply verification; revisit this entry before shipping anything that displays certs to third parties.

## SEC-003 | 2026-07-16 | Gmail: on-demand one-shot scan, no persisted tokens
**Decision:** `gmail.readonly` only; user-initiated scan; token used for a single pass and discarded; extract-and-discard (message-ID + extracted fields persisted, never raw bodies); sender-scoped search queries only.
**Rationale:** Eliminates stored-token theft class entirely; minimizes restricted-scope data custody; keeps unverified-app posture viable (Testing-status ~7-day refresh expiry is irrelevant when nothing persists).
**Trade-off:** No background sync; users re-consent per scan. Accepted per D13.

## SEC-004 | 2026-07-16 | Pull-only extraction worker
**Decision:** Local Claude Code worker pulls jobs from and pushes results to the app's worker API. The server never initiates connections toward the operator's network. Worker credentials are per-worker tokens scoped to claim/submit on the staging queue only.
**Rationale:** Home network never exposed; worker compromise ≠ app compromise; token theft grants only the ability to submit staged (human-reviewed) proposals.
**Trade-off:** Worker availability is best-effort; server-side API fallback exists for steady-state.

## SEC-005 | 2026-07-16 | All extractor output is untrusted
**Decision:** Server-side JSON Schema validation on every extraction result regardless of extractor (Claude API, local Claude Code, any future local model), plus mandatory human review before publication. Provenance records extractor identity.
**Rationale:** LLM output over web-fetched content is prompt-injection-exposed by construction; validation + review bounds impact to wasted reviewer time, never corrupted canonical data.
**Trade-off:** Review queue is a labor cost; accepted as core to product trust anyway.

## SEC-006 | 2026-07-16 | Fetched/uploaded/scanned content is hostile LLM input
**Decision:** Extraction contexts get schema-constrained output, no tool access, and no access to user PII tables. Provenance metadata stored separately from content. Raw source snapshots isolated from the app DB.
**Rationale:** Prompt injection via a provider page or a crafted "certificate" upload must not be able to exfiltrate user data or trigger actions.
**Trade-off:** Extraction can't enrich against user data (fine — it shouldn't).

## SEC-007 | 2026-07-16 | Community sources are inert until Approver-triggered
**Decision:** Any user may submit URL + description; nothing is fetched or sent to an LLM until an Approver+ triggers the crawl.
**Rationale:** Prevents queue-spam from draining token budget and prevents untrusted users from steering the fetcher at arbitrary targets (SSRF-adjacent abuse, malicious pages aimed at the extractor).
**Trade-off:** Slower community-source turnaround. Accepted per D16.

## SEC-008 | 2026-07-16 | Postgres RLS beneath app-level scoping
**Decision:** Row-level security policies on all user-owned tables as a second enforcement layer under application query scoping.
**Rationale:** A single missed WHERE clause must not become a cross-tenant leak.
**Trade-off:** Policy maintenance overhead and some query-planning friction; accepted.

## SEC-009 | 2026-07-16 | Secrets & token handling baseline
**Decision:** All provider credentials and OAuth tokens envelope-encrypted at the app layer with keys in a secret manager (GCP Secret Manager per D9); nothing secret in repo, images, or plain env files; short-lived signed URLs for any object access.
**Rationale:** DB dump or backup theft must not yield usable credentials.
**Trade-off:** Key-management ceremony on a solo project; accepted as CASA-critical anyway.

## SEC-010 | 2026-07-16 | ASVS L2 alignment as build-time posture
**Decision:** Build against ASVS Level 2 chapters (authentication, session, access control, validation, crypto as the primary checklist) with continuous bookkeeping in `security-audit.md`; formal full-catalog audit is a pre-CASA milestone, but readiness is maintained continuously, not reconstructed later.
**Rationale:** Retrofitting verification evidence is the expensive part of CASA; contemporaneous records make assessment a formality. Pin the ASVS version (4.0.3 vs 5.0) at repo kickoff and record it here as SEC-011.
**Trade-off:** Ongoing bookkeeping discipline; accepted per D18 ("do things right the first time").

## SEC-011 | (reserved) | ASVS version pin — record at repo kickoff

## SEC-012 | 2026-07-17 | Approver role confers admin review permissions in code
**Decision:** `User.has_perm`/`has_module_perms` grant approvers (role approver/admin) access to the review surfaces only — research, catalog, offers apps plus accounts.EnrollmentTask. No per-user permission rows or groups; role is the single authorization source of truth. User management stays superuser-only. Unmatched Credly badges enqueue as inert SourceSubmissions (same SEC-007 posture: user input causes no fetch or spend until an Approver triggers the crawl), deduplicated on (url, description) to bound queue-spam.
**Rationale:** Staff flag alone left approvers with zero model permissions (admin 403s, masked by a URL-only e2e assertion); scattering permission rows per user invites drift from the role field.
**Trade-off:** Permission granularity is app-level for approvers, not per-model; acceptable while the approver surface is exactly the review queue. Revisit if roles multiply.

## SEC-013 | 2026-07-17 | LLM/fetcher spend is approver-gated, categorically
**Decision:** Only approver/admin (and superuser) actions may trigger token or fetch spend — confirmed as a standing rule, not just the SEC-007 submission case. Audit at decision time: no server-side LLM call exists in the app (ANTHROPIC_API_KEY is read but unused); the only job-creating paths are the admin Trigger-crawl action (perm-gated per SEC-012) and the scheduler's re-crawl of sources that were themselves approver-promoted; the sole user-triggered server-side fetch is the Credly badges.json lookup — regex-pinned to credly.com profile URLs, no LLM involved (D6). Applies forward: the D13 Gmail "Scan my inbox" click and 5.4 upload parsing are user-facing LLM spend and MUST NOT execute directly on user action — they queue for approver-triggered or approver-batched execution unless this entry is explicitly superseded at build time.
**Rationale:** Token budget and fetcher targeting are attack surface (queue-spam, SSRF-adjacent steering, cost exhaustion); a single authorization class keeps the invariant auditable.
**Trade-off:** On-demand features become queued features (latency for users); accepted — the product's trust model already centers on human review.
