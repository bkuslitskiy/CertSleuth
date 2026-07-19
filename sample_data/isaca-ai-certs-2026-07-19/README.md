# ISACA per-cert maintain-* extraction (2026-07-19, pass 3)

4 renewal rules from each certification's own maintain page, correcting the blanket
assumption from the general CPE page: the AI credentials (AAIA / AAIR / AAISM) require
**30 CPE over 3 years** (min 10/yr), not 120/3; CET is 120/3 (min 20/yr). All confirmed,
re-verified against the snapshot at emit time (the generator asserts the numbers are
still on the page before writing each line).

Omission: the pages state tiered annual maintenance fees ($45 member / $85 non-member);
schema v1 has a single `annual_fee_usd`, so fees stay null rather than picking a tier.
Schema-gap candidates recorded: tiered fees, and per-cycle credit caps for CreditRule.
