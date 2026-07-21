"""Approval publishes + versions rules (spec: versioned, never overwritten)."""
import pytest
from django.contrib import admin, messages
from apps.catalog.models import Source, Provider, Certification, RenewalRule, UpgradePath
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


def test_bulk_approve_publishes_certs_before_dependents(db, approver, rf):
    """Admin lists newest-first; a batch staged as cert -> rule -> path must still
    publish the certification before the rows that look it up by slug."""
    from apps.research.admin import StagedChangeAdmin
    src = Source.objects.create(url="https://example.com/sa")
    job = ExtractionJob.objects.create(source=src)
    for kind, payload in [
        ("certification", {"provider_slug": "sa", "slug": "csm", "name": "CSM"}),
        ("certification", {"provider_slug": "sa", "slug": "a-csm", "name": "A-CSM"}),
        ("renewal_rule", {"provider_slug": "sa", "certification_slug": "csm",
                          "certification_name": "CSM", "ceu_required": 20}),
        ("upgrade_path", {"provider_slug": "sa", "from_certification_slug": "csm",
                          "to_certification_slug": "a-csm", "effect": "renews"}),
    ]:
        StagedChange.objects.create(job=job, kind=kind, extractor="t", payload=payload)
    request = rf.post("/admin/research/stagedchange/")
    request.user = approver
    request.session = {}
    request._messages = messages.storage.default_storage(request)
    admin_obj = StagedChangeAdmin(StagedChange, admin.site)
    admin_obj.approve_selected(request, StagedChange.objects.order_by("-id"))
    assert StagedChange.objects.filter(status=StagedChange.Status.APPROVED).count() == 4
    assert Certification.objects.get(slug="csm").current_rule.ceu_required == 20


def test_publish_versions_not_overwrites(staged_rule, approver):
    publish(staged_rule(120), approver)
    publish(staged_rule(125), approver)
    cert = Certification.objects.get(slug="cissp")
    assert RenewalRule.objects.count() == 2          # history kept
    assert cert.current_rule.ceu_required == 125     # new is current
    old = RenewalRule.objects.get(ceu_required=120)
    assert old.superseded_by == cert.current_rule    # chain intact


def test_certification_publish_sets_eligibility_and_source(approver):
    # Eligibility text is distinct from `level` (regression: ISC2 facts had experience
    # requirements stuffed into `level`) and every certification fact should attach its
    # source, same as renewal_rule/upgrade_path already do.
    src = Source.objects.create(url="https://isc2.example/cissp")
    job = ExtractionJob.objects.create(source=src)
    staged = StagedChange.objects.create(
        job=job, kind="certification", extractor="t",
        payload={"provider_slug": "isc2", "slug": "cissp", "name": "CISSP",
                 "level": "", "eligibility_requirement": "5+ Years Required Work Experience"})
    publish(staged, approver)
    cert = Certification.objects.get(provider__slug="isc2", slug="cissp")
    assert cert.eligibility_requirement == "5+ Years Required Work Experience"
    assert cert.level == ""
    assert cert.source == src


def test_partial_credit_upgrade_path_persists_ceu_amount(approver):
    """SEC-005-adjacent: partial_credit must carry its ceu_amount through publish, and
    must never be confused with a full renews (that would overstate what was earned)."""
    src = Source.objects.create(url="https://comptia.example/ce")
    job = ExtractionJob.objects.create(source=src)
    p = Provider.objects.create(name="CompTIA", slug="comptia")
    Certification.objects.create(provider=p, name="Cloud+", slug="cloud")
    Certification.objects.create(provider=p, name="SecurityX", slug="securityx")
    staged = StagedChange.objects.create(
        job=job, kind="upgrade_path", extractor="t",
        payload={"provider_slug": "comptia", "from_certification_slug": "cloud",
                 "to_certification_slug": "securityx", "effect": "partial_credit",
                 "ceu_amount": 25, "confidence": "confirmed"})
    publish(staged, approver)
    edge = UpgradePath.objects.get()
    assert edge.effect == UpgradePath.Effect.PARTIAL_CREDIT
    assert edge.ceu_amount == 25
    assert edge.from_cert.slug == "cloud" and edge.to_cert.slug == "securityx"
