"""Approval publishes + versions rules (spec: versioned, never overwritten)."""
import pytest
from apps.catalog.models import Source, Provider, Certification, RenewalRule
from apps.research.models import ExtractionJob, StagedChange
from apps.research.publish import publish


@pytest.fixture
def staged_rule(db):
    src = Source.objects.create(url="https://example.com/p")
    job = ExtractionJob.objects.create(source=src)
    p = Provider.objects.create(name="ISC2", slug="isc2")
    Certification.objects.create(provider=p, name="CISSP", slug="cissp")
    def make(ceu):
        return StagedChange.objects.create(job=job, kind="renewal_rule", extractor="t",
            payload={"provider_slug": "isc2", "certification_slug": "cissp",
                     "certification_name": "CISSP", "ceu_required": ceu})
    return make


def test_publish_versions_not_overwrites(staged_rule, approver):
    publish(staged_rule(120), approver)
    publish(staged_rule(125), approver)
    cert = Certification.objects.get(slug="cissp")
    assert RenewalRule.objects.count() == 2          # history kept
    assert cert.current_rule.ceu_required == 125     # new is current
    old = RenewalRule.objects.get(ceu_required=120)
    assert old.superseded_by == cert.current_rule    # chain intact
