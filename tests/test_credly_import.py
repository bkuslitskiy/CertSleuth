"""Credly import (spec 5.2): matched badges create UserCertification rows on confirm;
unmatched badges queue inert SourceSubmissions for research (D16)."""
import json
import pytest
from apps.catalog.models import Provider, Certification
from apps.research.models import SourceSubmission
from apps.tracker.credly import match_badges
from apps.tracker.models import UserCertification


@pytest.fixture
def csm(db):
    p = Provider.objects.create(name="Scrum Alliance", slug="scrum-alliance")
    return Certification.objects.create(provider=p, name="Certified ScrumMaster", slug="csm")


def badge(name, template_id="t-1", issued="2024-05-05", expires=None):
    return {"issued_at_date": issued, "expires_at_date": expires,
            "badge_template": {"id": template_id, "name": name,
                               "url": f"https://www.credly.com/badges/{template_id}"}}


def test_match_badges_by_name_and_miss(csm):
    matched, missed = match_badges([badge("Certified ScrumMaster"),
                                    badge("Associate of ISC2", "t-2")])
    assert matched["cert"] == csm
    assert missed["cert"] is None
    assert missed["template_id"] == "t-2"


def test_confirm_imports_matched_rows(client, user, csm):
    client.force_login(user)
    resp = client.post("/track/import/credly/", {
        "confirm": "1", "profile_url": "https://www.credly.com/users/x/badges",
        "import_badge": [json.dumps({"cert_id": csm.pk, "issued": "2024-05-05",
                                     "expires": "2027-05-31"})]})
    assert resp.status_code == 302
    uc = UserCertification.objects.get(user=user, certification=csm)
    assert str(uc.expiry_date) == "2027-05-31"


def test_confirm_queues_unmatched_for_research(client, user, db):
    client.force_login(user)
    payload = json.dumps({"badge": "Associate of ISC2", "template_id": "t-2",
                          "template_url": "https://www.credly.com/badges/t-2"})
    for _ in range(2):  # resubmitting must not duplicate the queue entry
        resp = client.post("/track/import/credly/", {
            "confirm": "1", "profile_url": "https://www.credly.com/users/x/badges",
            "queue_badge": [payload]})
        assert resp.status_code == 302
    subs = SourceSubmission.objects.filter(
        description__contains="Associate of ISC2")
    assert subs.count() == 1
    sub = subs.get()
    assert sub.status == SourceSubmission.Status.QUEUED   # inert until approver acts
    assert sub.submitted_by == user
    assert sub.url == "https://www.credly.com/badges/t-2"


def test_confirm_ignores_malformed_payloads(client, user, db):
    client.force_login(user)
    resp = client.post("/track/import/credly/", {
        "confirm": "1", "profile_url": "https://www.credly.com/users/x/badges",
        "queue_badge": ["not-json"], "import_badge": ["{broken"]})
    assert resp.status_code == 302
    assert SourceSubmission.objects.count() == 0
    assert UserCertification.objects.count() == 0
