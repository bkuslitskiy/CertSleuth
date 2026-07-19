# CompTIA CE + AWS extraction set (2026-07-18, extraction pass 2)

38 facts (17 renewal rules + 21 upgrade paths) extracted by Claude Code
(`claude-code-local`) from rendered snapshots of provider-official pages, after the
promoted-queue crawl captured the CompTIA CE cluster for the first time.

## Sources and what each page stated

| Provider | Page | Confirmed facts |
|---|---|---|
| CompTIA | CE "Training courses" (job 733) | "Total CEUs required for renewal" table + three-year cycle → 8 renewal rules: Security+/Linux+/Cloud+ 50, CySA+/PenTest+ 60, Network+/Project+ 30, Data+ 20 — all `cycle_years=3`. |
| CompTIA | "Earn a Higher-Level CompTIA Certification" (job 736) | Renewal matrix → 7 renews edges among catalog certs: CySA+ ⇄ PenTest+ (each also renews Security+ and Network+), Security+ renews Network+. |
| AWS | "Recertification" (job 396) | 3-year cycle rules for the 9 newly-staged certs + 14 renews edges from the per-cert options tables (Cloud Practitioner renewable by any Associate/Professional exam → 8 edges; AI Practitioner by ML-Engineer-Assoc or GenAI-Pro; each Associate by its stated Professional). |

All `confidence: confirmed` — provider-official pages.

## Deliberate omissions (nulls over guesses)

- **CompTIA Tech+** — absent from the CEU requirements table.
- **Cloud+ upgrade edges** — the matrix splits V3/V4; the current cert (V4) "does not
  fully renew another CompTIA certification".
- **Edges with out-of-catalog endpoints** (A+, Server+, SecurityX, CloudNetX, DataSys+…) —
  emit when those certs enter the catalog.
- **`requires` edges** — neither page states eligibility prerequisites; CompTIA certs
  have none and AWS's "must be active to renew" is not a prerequisite.
- **CE fees** — the fee waiver on full renewal is implied by the `renews` effect; no
  standalone fee figures are stated on these pages.

## Review note

The AWS upgrade paths reference the 9 AWS certifications staged by the deterministic
extractor in the same crawl. Approve certifications and upgrade paths **in the same
batch** (or certs first) — publish orders kinds correctly within one approval batch.

Status: submitted to StagedChange (pending), NOT published (SEC-005).
