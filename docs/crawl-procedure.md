# Crawl procedure — frontier, classification, cadence

Agreed 2026-07-17. Governs how the preload/recrawl worker expands the source set and how
sources are recrawled. Preserves SEC-006/007/013: **the app only ADDS to the queue; a
human triggers crawl processing (the spend).**

## Trust boundary (SEC-017)

- The app never triggers a crawl. Links discovered while crawling are **enqueued as inert
  `SourceSubmission`s**; an approver processes the queue (promote → `Source` + job) exactly
  as for a user submission. Every queue item records its **`origin`** (`user` | `crawl`).
- The extractor LLM does **not** choose crawl targets. A deterministic (no-LLM) link scan
  builds the frontier, so untrusted page content can never steer the fetcher.

## Link discovery (per crawled page)

1. Parse `<a href>` from the snapshot — deterministic, no LLM.
2. Resolve relative URLs against the page; keep `http(s)` only.
3. **Same registrable domain as the page → candidate. Cross-domain → dropped: not crawled,
   not queued, not recorded.** The frontier only ever goes deeper into the provider's own
   site.
4. Canonicalize (below) and dedupe against existing `Source`s and open `SourceSubmission`s.
5. Path-keyword shortlist: keep paths matching
   `renew|recert|cpe|ceu|pdu|maintain|certification|cert|policy|credential`.
6. Enqueue survivors as `SourceSubmission(origin=crawl, discovered_from=<page>,
   depth=<page>.depth+1)`, capped by the limits below.

## Canonicalization / dedupe

- Read `<link rel="canonical">`. If present, the canonical URL is the dedupe key.
- Otherwise dedupe on the **query-param-stripped path** (with host + scheme).

## Conditional fetch (efficiency)

- Store ETag / Last-Modified / content hash per `Source`.
- On recrawl send `If-None-Match` / `If-Modified-Since`. A `304` (or unchanged content
  hash) → **skip extraction**, just bump `last_fetched_at`. Most cadence recrawls become a
  cheap no-op.

## Politeness

- Respect `robots.txt` per domain; honor `crawl-delay`; apply a default per-domain delay.
- Identify honestly as `CertSleuthBot` (already in the worker UA).

## Classification → cadence

Every crawled page scans links regardless of status; **status only sets recrawl cadence.**
Nothing is deleted — a deleted URL just gets rediscovered and repopulated next crawl.

| Status | Condition | Cadence (default) |
|---|---|---|
| **active** | facts > 0 | normal — 7d |
| **hub** | facts = 0, promising same-domain links > 0 | moderate — 30d (to surface new certs) |
| **barren** | facts = 0, no promising links | very low — 180d; recency not treated as fresh |
| **needs_render** | real 200 but content is JS-hidden ("not fully loaded") | no text recrawl; flagged for the future headless path (D11) |
| **dead** | 404 / 403 | very low / none; kept so rediscovery doesn't re-crawl eagerly |

## Caps

- Depth ≤ **4** from seed (providers nest cert detail deep behind categories).
- ≤ **50** new pages per domain per run.

## Out of scope for now

- **Sitemaps** — carry far more URLs than are relevant; wasted budget. Revisit much later.
- **Headless rendering** — `needs_render` sources wait until that path exists (D11).
