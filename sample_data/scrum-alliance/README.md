# Scrum Alliance sample extraction set

Facts extracted 2026-07-16 from the official renewals page
(https://www.scrumalliance.org/get-certified/renewing-certifications) via chat-assisted
research — extractor tag `claude-chat-sample`. Purpose: seed the ingest→staging→review
loop with real data before the first automated preload, and serve as the reference
example for worker/CLAUDE.md output.

Page snapshot is NOT included (site content). job_id values assume the first three
seeded Scrum Alliance jobs; remap to real IDs after `seed_sources.py` (or ingest via
the batch upload, which reports any unknown job_id per line).

Noted while extracting — a real-world data conflict, kept out of the sample:
the page's renewal table lists Certified Agile Leader at 10 SEUs / $50, while the FAQ
on the SAME page says the CAL renewal fee is $100. Exactly the situation the
confidence + report-outdated machinery exists for. CAL rows are therefore omitted here;
CAL 1 appears only under its Foundational-tier listing per the table.

Load: /research/ingest/ (admin) or `python worker/claude_worker.py submit sample_data/scrum-alliance/results.jsonl --api <host>`

Schema note: building this sample surfaced that fees are per-CYCLE here, not annual —
`renewal_fee_usd` was added to schema v1 alongside `annual_fee_usd` as a result.
