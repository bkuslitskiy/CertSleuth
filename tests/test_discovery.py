"""Crawl-discovery ingestion (SEC-017): classification, link enqueue, fetch-report endpoint."""
import json

import pytest
from django.test import Client

from apps.catalog.models import Source
from apps.research import discovery
from apps.research.models import ExtractionJob, SourceSubmission, WorkerToken


# --- classify_fetch ---

@pytest.mark.parametrize("status,text_len,links,expected", [
    (404, 8000, 0, Source.Status.DEAD),
    ("robots_disallowed", None, 0, Source.Status.DEAD),
    (200, 100, 0, Source.Status.NEEDS_RENDER),      # 200 but JS-hidden
    (200, 100, 3, Source.Status.HUB),               # low text but has links -> hub, not shell
    (200, 8000, 0, Source.Status.BARREN),           # fully loaded, nothing
    (200, 8000, 5, Source.Status.HUB),              # links, no facts
])
def test_classify_fetch(status, text_len, links, expected):
    assert discovery.classify_fetch(status, text_len, links) == expected


def test_classify_fetch_304_is_none():
    assert discovery.classify_fetch(200, 8000, 3, unchanged=True) is None


# --- enqueue_links ---

@pytest.fixture
def source(db):
    return Source.objects.create(url="https://p.org/hub", depth=1)


def test_enqueue_creates_crawl_submissions(source):
    n = discovery.enqueue_links(source, ["https://p.org/a/cert", "https://p.org/b/cert"])
    assert n == 2
    sub = SourceSubmission.objects.first()
    assert sub.origin == SourceSubmission.Origin.CRAWL
    assert sub.discovered_from == source
    assert sub.depth == 2                            # parent depth + 1
    assert sub.status == SourceSubmission.Status.QUEUED


def test_enqueue_dedupes_against_sources_and_queue(source, db):
    Source.objects.create(url="https://p.org/known/cert")
    SourceSubmission.objects.create(url="https://p.org/pending/cert",
                                    description="x", status=SourceSubmission.Status.QUEUED)
    n = discovery.enqueue_links(source, [
        "https://p.org/known/cert", "https://p.org/pending/cert", "https://p.org/new/cert"])
    assert n == 1                                    # only the genuinely new one


def test_enqueue_respects_depth_cap(db):
    deep = Source.objects.create(url="https://p.org/deep", depth=discovery.MAX_DEPTH)
    assert discovery.enqueue_links(deep, ["https://p.org/x/cert"]) == 0


def test_enqueue_caps_per_report(source):
    links = [f"https://p.org/c{i}/cert" for i in range(discovery.MAX_LINKS_PER_REPORT + 20)]
    assert discovery.enqueue_links(source, links) == discovery.MAX_LINKS_PER_REPORT


# --- fetch-report endpoint + active-on-submit ---

@pytest.fixture
def token(db):
    raw, h = WorkerToken.make()
    WorkerToken.objects.create(name="w", token_hash=h)
    return raw


def _leased_job(token_name="w"):
    src = Source.objects.create(url="https://p.org/page")
    return ExtractionJob.objects.create(source=src, leased_by=token_name,
                                        status=ExtractionJob.Status.LEASED)


def test_fetch_report_classifies_and_enqueues(token, db):
    job = _leased_job()
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    report = {"http_status": 200, "text_len": 9000, "etag": 'W/"abc"',
              "discovered_links": ["https://p.org/x/cert", "https://p.org/y/renew"]}
    resp = Client().post(f"/api/worker/jobs/{job.pk}/fetch-report",
                         json.dumps(report), content_type="application/json", **auth)
    assert resp.status_code == 200
    assert resp.json()["queued"] == 2
    job.source.refresh_from_db()
    assert job.source.status == Source.Status.HUB
    assert job.source.cadence_days == Source.CADENCE_BY_STATUS["hub"]
    assert job.source.etag == 'W/"abc"'
    assert SourceSubmission.objects.filter(origin=SourceSubmission.Origin.CRAWL).count() == 2


def test_fetch_report_marks_dead(token, db):
    job = _leased_job()
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    Client().post(f"/api/worker/jobs/{job.pk}/fetch-report",
                  json.dumps({"http_status": 404}), content_type="application/json", **auth)
    job.source.refresh_from_db()
    assert job.source.status == Source.Status.DEAD


def test_submit_sets_source_active(token, db):
    job = _leased_job()
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    result = [{"job_id": job.pk, "kind": "certification", "extractor": "claude-code-local",
               "payload": {"provider_slug": "isc2", "slug": "cc", "name": "CC"}}]
    Client().post(f"/api/worker/jobs/{job.pk}/result", json.dumps(result),
                  content_type="application/json", **auth)
    job.source.refresh_from_db()
    assert job.source.status == Source.Status.ACTIVE
    assert job.source.last_yield_count == 1
