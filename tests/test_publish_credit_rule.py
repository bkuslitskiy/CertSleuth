"""credit_rule publish support + the no-silent-approve guard.

Until 2026-07-19, publish() had no credit_rule branch and unknown kinds fell through to
"approved" without writing anything — an approve-and-lose path.
"""
import pytest

from apps.catalog.models import CreditRule, Provider, Source
from apps.research.models import ExtractionJob, StagedChange
from apps.research.publish import publish

pytestmark = pytest.mark.django_db


@pytest.fixture
def staged_factory(db):
    src = Source.objects.create(url="https://ex.test/policy")
    job = ExtractionJob.objects.create(source=src)

    def make(kind, payload):
        return StagedChange.objects.create(job=job, kind=kind, payload=payload,
                                           extractor="t")
    return make


def test_credit_rule_publishes(staged_factory, approver):
    Provider.objects.create(name="ISACA", slug="isaca", ceu_currency="CPE")
    staged = staged_factory("credit_rule", {
        "provider_slug": "isaca", "category": "Certification-aligned",
        "activity_kinds": ["course", "conference"], "credits_per_hour": 1,
        "confidence": "confirmed"})
    publish(staged, approver)
    rule = CreditRule.objects.get()
    assert rule.provider.slug == "isaca"
    assert rule.activity_kinds == ["course", "conference"]
    staged.refresh_from_db()
    assert staged.status == StagedChange.Status.APPROVED


def test_credit_rule_reapproval_updates_not_duplicates(staged_factory, approver):
    Provider.objects.create(name="ISACA", slug="isaca")
    for kinds in (["course"], ["course", "webinar"]):
        publish(staged_factory("credit_rule", {
            "provider_slug": "isaca", "category": "Cat", "activity_kinds": kinds}), approver)
    assert CreditRule.objects.count() == 1
    assert CreditRule.objects.get().activity_kinds == ["course", "webinar"]


def test_unknown_kind_raises_instead_of_silent_approve(staged_factory, approver):
    staged = staged_factory("mystery_kind", {"x": 1})
    with pytest.raises(ValueError):
        publish(staged, approver)
    staged.refresh_from_db()
    assert staged.status == StagedChange.Status.PENDING   # untouched, still reviewable


def test_retired_status_publishes_and_recrawl_does_not_resurrect(staged_factory, approver):
    from apps.catalog.models import Certification
    Provider.objects.create(name="CompTIA", slug="comptia")
    publish(staged_factory("certification", {
        "provider_slug": "comptia", "slug": "old", "name": "Old Cert",
        "status": "retired", "retired_date": "2026-01-01"}), approver)
    cert = Certification.objects.get(slug="old")
    assert cert.status == "retired" and str(cert.retired_date) == "2026-01-01"
    # a later ordinary re-crawl fact (no status field) must not resurrect it
    publish(staged_factory("certification", {
        "provider_slug": "comptia", "slug": "old", "name": "Old Cert"}), approver)
    cert.refresh_from_db()
    assert cert.status == "retired"
