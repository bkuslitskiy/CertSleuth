# CertSleuth — Post-MVP Feature Backlog

Parking lot for features deliberately excluded from v1. Roughly ordered by expected value.

## Planning & guidance
- **Study planning**: target-date → CEU pacing plans, weekly targets, catch-up alerts (deferred per D4)
- **"Cheapest renewal path" optimizer v2**: full cost-of-ownership solver across the upgrade graph (fees + CEU effort), not just hints
- **Recommendation engine**: "people with your stack typically pursue X next"

## Import & sync
- **Gmail persistent sync** (requires Google verification + CASA; revisit if on-demand scan proves insufficient)
- **Forwarding inbox** (`u_xxxx@` per user + inbound email parsing) — shares extraction pipeline with Gmail scanner
- **Credly polling**: periodic re-fetch of connected profiles to auto-detect newly earned badges
- **Microsoft Learn transcript sync**; other provider-specific importers as demand appears

## Research pipeline
- **Headless-browser fetcher** for JS-rendered or bot-mitigated sources (D11 deferral)
- **Broad free-offer discovery**: search-API sweeps of blogs/Reddit/LinkedIn with heavier review gating
- **Contributor credibility scoring** to auto-prioritize ChangeReports and submissions
- **Wiki-style community rule editing** with moderation (vs current closed curation)

## Product & platform
- **Paid tier** (D15): candidates — priority research on requested providers, API access, org/team dashboards
- **Team/org features**: manager view, compliance heatmap, bulk import (the TrackACert market)
- **Push notifications / mobile PWA**
- **Public read-only profile pages** (opt-in shareable cert wall)
- **Localization** of provider rules (several bodies publish region-specific pricing)

## Security & ops
- **Formal ASVS L2 full-catalog audit + CASA Tier 2** (triggered by >100 users or Gmail persistent sync)
- **SSO (OIDC) for org accounts** if team features land
- **Anomaly alerts** on research pipeline (source disappeared, extraction confidence collapse)
