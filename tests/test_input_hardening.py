"""SEC-022: input/output hardening.

Tests that would have caught each gap:
- plan_toggle followed an unvalidated ?next -> open redirect to any external URL.
- the ICS feed interpolated catalog names into TEXT values with no RFC 5545 escaping.
- the worker claim endpoint did int(?n) with no guard -> 500 on garbage, inverted slice on
  a negative value.
"""
import hashlib
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from apps.catalog.models import Certification, Provider, Source
from apps.research.models import ExtractionJob, WorkerToken
from apps.tracker.models import UserCertification

pytestmark = pytest.mark.django_db


def _cert(name="Cert", slug="c"):
    prov = Provider.objects.create(name="Prov", slug="prov")
    return Certification.objects.create(provider=prov, name=name, slug=slug)


# --- open redirect ---------------------------------------------------------------------

def test_plan_toggle_ignores_external_next(client, user):
    cert = _cert()
    client.force_login(user)
    resp = client.post(reverse("plan_toggle", args=[cert.pk]),
                       {"next": "https://evil.example/steal"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == reverse("catalog_cert",
                                               args=[cert.provider.slug, cert.slug])


def test_plan_toggle_honors_local_next(client, user):
    cert = _cert()
    client.force_login(user)
    resp = client.post(reverse("plan_toggle", args=[cert.pk]), {"next": "/dashboard/"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/dashboard/"


# --- ICS output escaping ---------------------------------------------------------------

def test_ics_feed_escapes_special_chars(client, user):
    cert = _cert(name="Security, Advanced; Pro")
    UserCertification.objects.create(user=user, certification=cert, expiry_date=date(2030, 1, 1))
    body = client.get(reverse("ics_feed", args=[user.ics_token])).content.decode()
    assert "SUMMARY:Prov Security\\, Advanced\\; Pro expires" in body
    assert "SUMMARY:Prov Security, Advanced" not in body  # no raw comma survives


# --- bounded ?n on the token-authed claim endpoint -------------------------------------

RAW = "sec022-token"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {RAW}"}


def _mint_token():
    WorkerToken.objects.create(name="w", token_hash=hashlib.sha256(RAW.encode()).hexdigest())


def test_claim_non_integer_n_does_not_500(db):
    _mint_token()
    resp = Client().post("/api/worker/jobs/claim?n=not-a-number", **AUTH)
    assert resp.status_code == 200
    assert resp.json()["jobs"] == []


def test_claim_negative_n_is_clamped_not_inverted(db):
    _mint_token()
    ExtractionJob.objects.create(source=Source.objects.create(url="https://ex.test/a"))
    resp = Client().post("/api/worker/jobs/claim?n=-5", **AUTH)  # old code -> [:-5] -> []
    assert resp.status_code == 200
    assert len(resp.json()["jobs"]) == 1
