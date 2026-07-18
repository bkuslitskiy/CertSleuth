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
SHELL_TEXT_THRESHOLD = 500    # visible chars; below this + no links => JS shell, not barren


def classify_fetch(http_status, text_len, link_count, unchanged=False):
    """Source status from fetch signals alone. Returns None for a 304 (don't reclassify).
    `active` is not decided here — submit sets it when facts are staged."""
    if unchanged:
        return None
    if not isinstance(http_status, int) or http_status >= 400:
        return Source.Status.DEAD                       # 404/403/robots/error
    if (text_len is not None) and text_len < SHELL_TEXT_THRESHOLD and link_count == 0:
        return Source.Status.NEEDS_RENDER               # 200 but JS-hidden ("not fully loaded")
    if link_count > 0:
        return Source.Status.HUB                        # links but no facts (yet)
    return Source.Status.BARREN                         # fully loaded, nothing


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
                            len(links), report.get("unchanged", False))
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
