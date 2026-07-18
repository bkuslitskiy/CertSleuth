# Renewal-rule extraction set — AWS / GIAC / ISACA (2026-07-18)

22 facts (21 renewal rules + 1 upgrade path) extracted by Claude Code (`claude-code-local`)
from three provider-official renewal-policy pages, after those pages were re-crawled **with
headless rendering** (SEC-019). Before this, all 16 catalog renewal rules were Scrum Alliance
only; the other 58 certifications had none. These fill AWS, GIAC, and ISACA.

Page snapshots are NOT included (site content, SEC-006). `job_id`s are the local recrawl
jobs for each policy page; remap to real IDs on another host (batch ingest reports unknown
job_ids per line).

## Sources and what each page stated

| Provider | Page | Confirmed facts |
|---|---|---|
| AWS | `/certification/recertification/` | "Renew for 3 more years of validity." Exam/assessment based → `cycle_years=3`, no CEU. Passing Gen AI Developer – Professional renews ML Engineer – Associate → one `upgrade_path` (`renews`). |
| GIAC | `/renewal/cpe-information` | "Combine categories to earn 36 CPEs over four years." → `ceu_required=36, cycle_years=4`. Applied to all 12 GIAC catalog certs. |
| ISACA | `/credentialing/cpe-2027` | "120 CPEs over three years requirement remains the same." → `ceu_required=120, cycle_years=3`. Applied to the 6 established CPE-governed certs (cisa, cism, cgeit, crisc, cdpse, ccoa). |

All `confidence: confirmed` — each is the provider's own policy page.

## Deliberate omissions (nulls over guesses)

- **Fees** — none stated on these pages. AWS shows a 50%-voucher but no renewal-fee figure;
  GIAC's ~$479 renewal fee and ISACA's annual maintenance fee live on other pages. All left null.
- **CompTIA** — `why-renew` is motivational and carries no CEU numbers; the per-cert CEU
  requirements page was not in this crawl. No CompTIA rules emitted.
- **Microsoft** — cleanly extractable (free, annual, assessment-based) but there is no
  Microsoft provider in the catalog, so the rules would be orphaned. Skipped.
- **ISACA newer AI credentials** (aaia/aair/aaism/cet) — the CPE page does not state their
  requirements; left for targeted extraction.
- **ISACA 2027 category split** (90 domain-aligned + 30 professional, effective 2027-01-01) —
  real and confirmed, but omitted from the payload to keep the stable `120/3yr` fact
  unambiguous. A candidate enrichment for `ceu_categories` + `effective_date`.

## Status

Submitted to StagedChange (pending), NOT published — awaiting approver review (SEC-005).

Load: `python worker/claude_worker.py submit sample_data/renewal-rules-2026-07-18/results.jsonl --api <host>`
