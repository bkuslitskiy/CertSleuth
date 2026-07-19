# Provider candidates — investigation list (2026-07-19)

Ranked by **renewal relevance**: CertSleuth's value is tracking renewal obligations, so
providers whose certs expire and demand CEUs/fees/re-exams outrank ones issuing lifetime
certificates. Seeded ≠ done — a row leaves this list when its policy page is crawled and
rules are staged.

Status key: **seeded** (source exists), **investigate** (find the policy URL first),
**low** (park unless users ask).

## Tier 1 — expiring certs + CEU/fee machinery (highest renewal-tracking value)

| Provider | Renewal shape (to verify on-page) | Status |
|---|---|---|
| Cisco | 3-yr cycle, CE credits or re-exam; large installed base | **seeded** — bot-walled (403), needs render-first fetch or manual snapshot |
| EC-Council | ECE: 120 credits / 3 yr + annual membership fee | **seeded** |
| PMI | PMP: 60 PDUs / 3 yr + fee; PDU taxonomy maps well to CreditRule | investigate — pmi.org/certifications/maintain |
| ISACA / ISC2 / CompTIA / GIAC / Scrum Alliance | — | done (rules in catalog) |
| PeopleCert (ITIL) | Recert every 3 yr (re-exam or CPD points) since 2023 | investigate |
| IAPP | CIPP/CIPM/CIPT: 20 CPE / 2 yr + maintenance fee | investigate |
| SANS | Runs through GIAC (already covered) — verify no separate track | low |
| CWNP | 3-yr recert via higher cert or re-exam | investigate |
| ASQ | CQE etc.: 18 RUs / 3 yr | investigate |

## Tier 2 — expiring certs, re-exam only (renewal dates matter, CEUs don't)

| Provider | Shape | Status |
|---|---|---|
| Microsoft | Free annual online renewal, 6-month window | **in progress this session** (97 pages crawling, extractor rule live) |
| Google Cloud | Recert cycle (2 yr for most) | **seeded** (policy page) |
| Google Skillshop (Analytics/Ads) | 12-month expiry, free re-exam | **seeded** |
| HubSpot Academy | Certs expire 13–25 months, free retake | **seeded** (academy.hubspot.com) |
| Moz Academy | Certification courses — verify expiry semantics on-page | **seeded** (academy.moz.com) |
| Kubernetes/CNCF | CKA/CKAD/CKS: 2–3 yr, re-exam | investigate |
| HashiCorp | 2-yr expiry | investigate |
| Red Hat | 3-yr "current" window, renew via re-exam/higher exam | investigate |
| Salesforce | Release-cycle maintenance modules (free, but miss = expiry!) | investigate — high user value, unusual shape |
| VMware/Broadcom | Recert policy relaxed post-acquisition — verify current state | investigate |
| Juniper | 3-yr, recert via exam | low |
| Fortinet / Palo Alto | 2-yr cycles | investigate |
| Databricks / Snowflake | 2-yr expiry | low |
| Okta | 3-yr + maintenance exams | low |

## Tier 3 — non-expiring or course-completion (low renewal value; catalog-only)

Linux Foundation (some certs now expire — spot-check), LPI (5-yr "active" status),
Scrum.org (PSM — lifetime, no renewal: good *contrast* data for compatibility),
ICAgile (lifetime), SAFe (annual membership renewal $100 — actually Tier 1-ish, verify),
Adobe (2-yr — verify), Oracle (release-tied), IBM, ServiceNow (release-tied maintenance),
Tableau (2-yr — verify), Unity, Autodesk (annual — verify).

## Non-providers to keep out

Credly/Accredible/Skilljar (issuing platforms, not cert owners — importer targets, not
catalog providers); Coursera/Udemy (courseware; certificates aren't renewable credentials).

## Process note

Adding a provider = seed its **renewal-policy URL** (verify live first — most seed-list
rot is here), crawl rendered, extract rules; cert inventory then arrives via same-domain
discovery + the per-provider extractor rules (worker/extractors.py) when og:title format
is verified. Salesforce and SAFe have unusual renewal shapes worth modeling care.
