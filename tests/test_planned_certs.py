"""Planned certifications (UserGoal reused as the favorites list): toggle endpoint,
dashboard section with compatibility, catalog integration."""
import pytest

from apps.catalog.models import Certification, Provider, RenewalRule, UpgradePath
from apps.tracker.models import UserCertification, UserGoal

pytestmark = pytest.mark.django_db


@pytest.fixture
def scrum(db):
    p = Provider.objects.create(name="Scrum Alliance", slug="scrum-alliance",
                                ceu_currency="SEU")
    csm = Certification.objects.create(provider=p, name="Certified ScrumMaster",
                                       slug="csm", level="Foundational")
    acsm = Certification.objects.create(provider=p, name="Advanced CSM",
                                        slug="a-csm", level="Advanced")
    RenewalRule.objects.create(certification=acsm, ceu_required=30, cycle_years=2)
    UpgradePath.objects.create(from_cert=csm, to_cert=acsm, effect="renews")
    return p, csm, acsm


def test_toggle_adds_then_removes(client, user, scrum):
    _, _, acsm = scrum
    client.force_login(user)
    client.post(f"/track/plan/{acsm.pk}/")
    assert UserGoal.objects.filter(user=user, certification=acsm).exists()
    client.post(f"/track/plan/{acsm.pk}/")
    assert not UserGoal.objects.filter(user=user, certification=acsm).exists()


def test_toggle_get_is_a_noop_redirect(client, user, scrum):
    _, _, acsm = scrum
    client.force_login(user)
    resp = client.get(f"/track/plan/{acsm.pk}/")
    assert resp.status_code == 302
    assert not UserGoal.objects.exists()


def test_toggle_unknown_cert_404(client, user, scrum):
    client.force_login(user)
    assert client.post("/track/plan/99999/").status_code == 404


def test_dashboard_shows_planned_with_compat(client, user, scrum):
    _, csm, acsm = scrum
    UserCertification.objects.create(user=user, certification=csm)
    UserGoal.objects.create(user=user, certification=acsm)
    client.force_login(user)
    body = client.get("/").content.decode()
    assert "Planned certifications" in body
    assert "Advanced CSM" in body
    assert 'data-compat="renews-yours"' in body      # earning it renews the held CSM
    assert "30 SEU / 2yr" in body


def test_dashboard_empty_planned_state(client, user, scrum):
    client.force_login(user)
    assert b"Nothing planned yet" in client.get("/").content


def test_cert_page_plan_button_reflects_state(client, user, scrum):
    _, _, acsm = scrum
    client.force_login(user)
    body = client.get("/catalog/scrum-alliance/a-csm/").content.decode()
    assert 'data-planned="no"' in body
    UserGoal.objects.create(user=user, certification=acsm)
    body = client.get("/catalog/scrum-alliance/a-csm/").content.decode()
    assert 'data-planned="yes"' in body


def test_provider_page_marks_planned(client, user, scrum):
    _, _, acsm = scrum
    UserGoal.objects.create(user=user, certification=acsm)
    client.force_login(user)
    body = client.get("/catalog/scrum-alliance/").content.decode()
    assert 'title="Planned"' in body


def test_duplicate_plan_is_impossible(user, scrum):
    _, _, acsm = scrum
    UserGoal.objects.create(user=user, certification=acsm)
    import django.db
    with pytest.raises(django.db.IntegrityError):
        UserGoal.objects.create(user=user, certification=acsm)
