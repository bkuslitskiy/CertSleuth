"""Crawl-discovery ingestion (SEC-017).

The worker reports each page's fetch metadata + same-domain discovered links (no raw HTML,
SEC-006). We classify the source for cadence and enqueue the links as inert
`SourceSubmission`s (origin=crawl) — the app ADDS to the queue; a human still processes it.
`active` is set later at submit time (it needs the extracted-fact count).
"""
from django.utils import timezone

from apps.catalog.models import Source
from .models import SourceSubmission

MAX_DEPTH = 4                 # hops from a seed (docs/crawl-procedure.md)
MAX_LINKS_PER_REPORT = 50     # per-source-page cap on new frontier entries
# Content chars OUTSIDE site chrome. Full-page counts do not separate a shell from a real
# page — nav/footer boilerplate put learn.microsoft.com/credentials/browse/ at 603 chars,
# past the threshold, so it was filed `barren`. Measured on main content the same page
# scores 175 against 5,760-9,402 for real cert pages, a clean 30x gap (SEC-019).
SHELL_TEXT_THRESHOLD = 500


def classify_fetch(http_status, text_len, link_count, unchanged=False,
                   rendered=None, main_text_len=None):
    """Source status from fetch signals alone. Returns None for a 304 (don't reclassify).
    `active` is not decided here — submit sets it when facts are staged.

    `needs_render` now means "we could not run a browser on this page", not a guess about
    the markup: the worker renders by default (SEC-019), so a page that still looks empty
    after rendering is genuinely barren. Older reports omit both new fields and fall back
    to the previous full-page heuristic.
    """
    if unchanged:
        return None
    if not isinstance(http_status, int) or http_status >= 400:
        return Source.Status.DEAD                       # 404/403/robots/error
    content_len = main_text_len if main_text_len is not None else text_len
    looks_empty = (content_len is not None) and content_len < SHELL_TEXT_THRESHOLD
    if looks_empty and rendered is False:
        return Source.Status.NEEDS_RENDER               # empty AND no browser was available
    if looks_empty and rendered is None and link_count == 0:
        return Source.Status.NEEDS_RENDER               # legacy report: old heuristic
    if link_count > 0:
        return Source.Status.HUB                        # links but no facts (yet)
    return Source.Status.BARREN                         # rendered (or dense) and yielded nothing


def _already_known(url):
    return (Source.objects.filter(url=url).exists()
            or SourceSubmission.objects.filter(
                url=url, status=SourceSubmission.Status.QUEUED).exists())


def enqueue_links(source, links):
    """Enqueue same-domain discovered links as inert crawl-origin submissions, deduped and
    depth-capped. Returns the count newly queued."""
    if source.depth >= MAX_DEPTH:
        return 0
    queued = 0
    for url in links[:MAX_LINKS_PER_REPORT]:
        if _already_known(url):
            continue
        SourceSubmission.objects.create(
            url=url[:500], description=f"Crawl discovery from {source.url}"[:300],
            origin=SourceSubmission.Origin.CRAWL, discovered_from=source,
            depth=source.depth + 1, status=SourceSubmission.Status.QUEUED)
        queued += 1
    return queued


def apply_fetch_report(source, report):
    """Update the source's fetch metadata + status and enqueue its discovered links.
    Returns (status_or_None, queued_count)."""
    links = report.get("discovered_links") or []
    status = classify_fetch(report.get("http_status"), report.get("text_len"),
                            len(links), report.get("unchanged", False),
                            rendered=report.get("rendered"),
                            main_text_len=report.get("main_text_len"))
    source.last_fetched_at = timezone.now()
    if report.get("etag"):
        source.etag = report["etag"][:250]
    if report.get("last_modified"):
        source.http_last_modified = report["last_modified"][:80]
    if report.get("snapshot_hash"):
        source.last_content_hash = report["snapshot_hash"]
    if status is not None:
        source.status = status
        source.cadence_days = Source.CADENCE_BY_STATUS.get(status, source.cadence_days)
    source.save()
    return status, enqueue_links(source, links)
