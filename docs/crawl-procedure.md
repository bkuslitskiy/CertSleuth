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
| **barren** | facts = 0, no promising links, **after rendering** | very low — 180d; recency not treated as fresh |
| **needs_render** | page looked empty and **no renderer was available** | no text recrawl; re-run the fetch on a host with Playwright installed |
| **dead** | 404 / 403 | very low / none; kept so rediscovery doesn't re-crawl eagerly |

"Looked empty" is measured by `crawl.main_text_len()` — visible characters **outside** nav,
header, footer, aside, and cookie banners — against a 500-char threshold. Whole-page counts
were tried first and do not work: site chrome alone put a pure JS shell at 603 chars, past
the threshold, while the same page measures 175 on main content against 5,760–9,402 for real
cert pages (SEC-019).

## Caps

- Depth ≤ **4** from seed (providers nest cert detail deep behind categories).
- ≤ **50** new pages per domain per run.
- **English only** (2026-07-19): a path segment that parses as a non-English locale code
  (`/ja-jp/`, `/de_DE/`, `/es/`) drops the link — providers duplicate content per locale
  and the frontier was multiplying. Blocklist-based so short non-locale segments like
  CompTIA's `/ce/` can't be misread (`crawl.is_english_url`).

## Rendering

`fetch` renders every live 200 in headless Chromium by default (SEC-019), because deciding
*whether* a page needs a browser turned out to be harder and less reliable than just using
one. Order of operations keeps it cheap:

1. robots.txt check — a disallowed URL never loads.
2. Conditional GET (`If-None-Match` / `If-Modified-Since`) — a **304 never reaches the browser**.
3. Only a live 200 is re-loaded in Chromium; a render failure falls back to the raw HTML.

Setup is operator-side: `pip install -e .[render]` then `playwright install chromium`.
Without it the worker still runs, fetches unrendered, and marks affected sources
`needs_render`. `--no-render` disables it explicitly.

Cost is roughly 6.6s/page rendered vs 0.2s raw, bounded by the 304 path and the cadence
tiers above. Worth it: `learn.microsoft.com/credentials/browse/` unrendered yields 603
visible chars and **0** links (filed `barren`, 180d); rendered it yields 9,797 chars and
**34** same-domain links, including the Microsoft renewal-policy page.

### One-time gotcha: bust the etag cache when enabling rendering

Conditional fetch keys on **server content identity** (etag / Last-Modified), but rendering
changes what *we* extract from byte-identical server HTML. A source snapshotted before
rendering was enabled still has a matching etag, so the first render pass 304s and the
browser never runs — the page keeps its stale pre-render status. Observed exactly this:
8 of 32 renewal targets (including the MS Learn browse page this work exists to fix) 304'd
on the first pass and stayed `barren`/`hub` until their etags were cleared.

So the render migration is a **one-time cache bust**: clear `etag` + `http_last_modified`
on the sources you want re-rendered, then recrawl. Steady state needs no bust — new etags
are stored alongside rendered snapshots, so a later 304 correctly means "rendered content
still current."

## Out of scope for now

- **Sitemaps** — carry far more URLs than are relevant; wasted budget. Revisit much later.
