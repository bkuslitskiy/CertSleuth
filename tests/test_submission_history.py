"""Prior-crawl context in the submission review queue.

An approver reviewing the frontier needs to distinguish a brand-new URL from a
re-discovery of a page already crawled — previously the queue showed neither the matched
Source nor its history, so approving was blind.
"""
import pytest
from django.utils import timezone

from apps.catalog.models import Source
from apps.research.admin import SubmissionAdmin
from apps.research.models import SourceSubmission

pytestmark = pytest.mark.django_db


def _admin():
    from django.contrib import admin as dj_admin
    return SubmissionAdmin(SourceSubmission, dj_admin.site)


def _rf_get(approver):
    from django.test import RequestFactory
    req = RequestFactory().get("/admin/research/sourcesubmission/")
    req.user = approver
    return req


def test_new_url_shows_as_new(approver):
    sub = SourceSubmission.objects.create(url="https://ex.test/never-seen",
                                          description="d")
    obj = _admin().get_queryset(_rf_get(approver)).get(pk=sub.pk)
    assert _admin().prior_crawl(obj) == "—  (new URL)"


def test_previously_crawled_url_shows_status_fetch_and_yield(approver):
    Source.objects.create(url="https://ex.test/known", status="hub",
                          last_fetched_at=timezone.now(), last_yield_count=3)
    sub = SourceSubmission.objects.create(url="https://ex.test/known", description="d")
    out = _admin().prior_crawl(_admin().get_queryset(_rf_get(approver)).get(pk=sub.pk))
    assert "hub" in out and "fetched" in out and "3 fact(s)" in out


def test_canonical_url_also_matches(approver):
    # discovery dedupes on rel=canonical; history must match through it too
    Source.objects.create(url="https://ex.test/canonical-page", status="active")
    sub = SourceSubmission.objects.create(url="https://ex.test/?utm=x",
                                          canonical_url="https://ex.test/canonical-page",
                                          description="d")
    out = _admin().prior_crawl(_admin().get_queryset(_rf_get(approver)).get(pk=sub.pk))
    assert out.startswith("active")


def test_queryset_is_constant_queries(approver, django_assert_num_queries):
    # subquery annotations, not per-row lookups
    for i in range(10):
        SourceSubmission.objects.create(url=f"https://ex.test/{i}", description="d")
    qs = _admin().get_queryset(_rf_get(approver))
    with django_assert_num_queries(1):
        [_admin().prior_crawl(o) for o in qs]


def test_trigger_crawl_warns_on_existing_source(approver, client):
    src = Source.objects.create(url="https://ex.test/dup", status="hub")
    sub = SourceSubmission.objects.create(url="https://ex.test/dup", description="d")
    client.force_login(approver)
    resp = client.post("/admin/research/sourcesubmission/",
                       {"action": "trigger_crawl", "_selected_action": [sub.pk]},
                       follow=True)
    msgs = [str(m) for m in resp.context["messages"]]
    assert any("already existed" in m for m in msgs)
    sub.refresh_from_db()
    assert sub.status == SourceSubmission.Status.CRAWLED
    assert Source.objects.filter(url="https://ex.test/dup").count() == 1  # no duplicate
    assert src.extractionjob_set.count() == 1                             # but re-queued


def test_domain_auto_set_on_save(approver):
    sub = SourceSubmission.objects.create(
        url="https://community.example.co:8443/certifications/foo", description="d")
    assert sub.domain == "example.co"          # registrable domain, port stripped


def test_domain_filter_narrows_queue(approver, client):
    SourceSubmission.objects.create(url="https://a.comptia.org/x", description="d")
    SourceSubmission.objects.create(url="https://www.isaca.org/y", description="d")
    client.force_login(approver)
    resp = client.get("/admin/research/sourcesubmission/?domain=comptia.org")
    body = resp.content.decode()
    assert "a.comptia.org/x" in body
    assert "isaca.org/y" not in body


def test_changelist_renders_with_history_column(approver, client):
    Source.objects.create(url="https://ex.test/known", status="barren",
                          last_fetched_at=timezone.now())
    SourceSubmission.objects.create(url="https://ex.test/known", description="d")
    client.force_login(approver)
    resp = client.get("/admin/research/sourcesubmission/")
    assert resp.status_code == 200
    assert b"barren" in resp.content
