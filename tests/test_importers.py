"""Importers for spec 5.3-5.5 (Microsoft Learn, Accredible, Open Badges, LinkedIn) plus
the shared match/confirm layer. Network fetchers are mocked; parsers use real payloads."""
import json
import struct

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Provider, Certification
from apps.research.models import SourceSubmission
from apps.tracker import importers
from apps.tracker.models import UserCertification


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


@pytest.fixture
def csm(db):
    p = Provider.objects.create(name="Scrum Alliance", slug="scrum-alliance")
    return Certification.objects.create(provider=p, name="Certified ScrumMaster", slug="csm",
                                        external_ids={"accredible_group": 9549})


# --- shared layer ---

def test_date_normalizes_iso_and_datetime():
    assert importers._date("2020-10-22T23:23:59+00:00") == "2020-10-22"
    assert importers._date("2014-08-14") == "2014-08-14"
    assert importers._date(None) is None
    assert importers._date("not-a-date") is None


def test_match_catalog_by_external_key_then_name(csm):
    items = [
        {"name": "whatever", "external_system": "accredible_group", "external_key": 9549},
        {"name": "Certified ScrumMaster", "external_system": "x", "external_key": None},
        {"name": "Totally Unknown Cert", "external_system": "x", "external_key": None},
    ]
    matched = importers.match_catalog(items)
    assert matched[0]["cert"] == csm      # external key wins
    assert matched[1]["cert"] == csm      # name fallback
    assert matched[2]["cert"] is None     # miss


# --- Microsoft Learn ---

MS_PAYLOAD = {"certificationData": {"activeCertifications": [
    {"name": "Microsoft Certified: Azure Fundamentals",
     "certificationNumber": "XX-YY", "status": "Active",
     "dateEarned": "2020-10-22T23:23:59+00:00"}]}}


def test_microsoft_fetch(monkeypatch, db):
    monkeypatch.setattr(importers.httpx, "get", lambda *a, **k: FakeResp(MS_PAYLOAD))
    form = type("F", (), {"cleaned_data": {
        "transcript_url": "https://learn.microsoft.com/en-us/users/x/transcript/abc123"}})()
    items = importers.microsoft_fetch(form)
    assert len(items) == 1
    assert items[0]["name"] == "Microsoft Certified: Azure Fundamentals"
    assert items[0]["issued"] == "2020-10-22"
    assert items[0]["source"] == "Microsoft Learn"


def test_microsoft_fetch_rejects_bad_url(db):
    import httpx
    form = type("F", (), {"cleaned_data": {"transcript_url": "https://example.com/nope"}})()
    with pytest.raises(httpx.HTTPError):
        importers.microsoft_fetch(form)


# --- Accredible ---

def test_accredible_fetch(monkeypatch, db):
    payload = {"data": {"name": "Databricks Lakehouse", "group_id": 9549,
                        "issued_on": "2014-08-14", "expired_on": None, "private": False}}
    monkeypatch.setattr(importers.httpx, "get", lambda *a, **k: FakeResp(payload))
    form = type("F", (), {"cleaned_data": {
        "credential_url": "https://www.credential.net/10000005"}})()
    items = importers.accredible_fetch(form)
    assert items[0]["external_key"] == 9549
    assert items[0]["issued"] == "2014-08-14"


def test_accredible_skips_private(monkeypatch, db):
    monkeypatch.setattr(importers.httpx, "get",
                        lambda *a, **k: FakeResp({"data": {"name": "x", "private": True}}))
    form = type("F", (), {"cleaned_data": {"credential_url": "https://credential.net/9"}})()
    assert importers.accredible_fetch(form) == []


# --- Open Badges ---

def _upload(name, content):
    return type("F", (), {"cleaned_data": {"badge_file": SimpleUploadedFile(name, content)}})()


def test_openbadge_json_v2():
    obj = {"type": "Assertion", "issuedOn": "2023-01-15", "expires": "2026-01-15",
           "badge": {"name": "Kubernetes Administrator"}}
    items = importers.openbadge_parse(_upload("b.json", json.dumps(obj).encode()))
    assert items[0]["name"] == "Kubernetes Administrator"
    assert items[0]["issued"] == "2023-01-15"
    assert items[0]["expires"] == "2026-01-15"


def test_openbadge_json_v3_vc():
    obj = {"type": ["VerifiableCredential", "OpenBadgeCredential"],
           "validFrom": "2024-06-01T00:00:00Z",
           "credentialSubject": {"achievement": {"name": "Terraform Associate"}}}
    items = importers.openbadge_parse(_upload("b.json", json.dumps(obj).encode()))
    assert items[0]["name"] == "Terraform Associate"
    assert items[0]["issued"] == "2024-06-01"


def test_openbadge_png_baked():
    obj = {"type": "Assertion", "issuedOn": "2022-03-03", "badge": {"name": "PNG Badge"}}
    data = b"openbadges\x00" + json.dumps(obj).encode()
    chunk = struct.pack(">I", len(data)) + b"tEXt" + data + b"\x00\x00\x00\x00"
    png = b"\x89PNG\r\n\x1a\n" + chunk
    items = importers.openbadge_parse(_upload("badge.png", png))
    assert items[0]["name"] == "PNG Badge"


def test_openbadge_svg_baked():
    obj = {"type": "Assertion", "issuedOn": "2021-09-09", "badge": {"name": "SVG Badge"}}
    svg = (b'<svg xmlns:openbadges="x"><openbadges:assertion verify="hosted">'
           + json.dumps(obj).encode() + b'</openbadges:assertion></svg>')
    items = importers.openbadge_parse(_upload("badge.svg", svg))
    assert items[0]["name"] == "SVG Badge"


def test_openbadge_rejects_hosted_url_no_ssrf():
    svg = b'<svg><openbadges:assertion verify="https://evil.example/assertion.json"/></svg>'
    with pytest.raises(ValueError, match="hosted link"):
        importers.openbadge_parse(_upload("badge.svg", svg))


def test_openbadge_rejects_unknown_extension():
    with pytest.raises(ValueError, match="json, .png, or .svg"):
        importers.openbadge_parse(_upload("badge.txt", b"nope"))


# --- LinkedIn CSV ---

def test_linkedin_parse_headers_and_dates():
    csv_bytes = (
        "Name,Url,Authority,Started On,Finished On,License Number\r\n"
        "AWS Certified Solutions Architect,https://aws.example/1,AWS,Jan 2023,Jan 2026,ABC123\r\n"
        "PMP,,PMI,2022-05-01,2025-05-01,\r\n"
        ",,,,,\r\n"  # blank name row skipped
    ).encode("utf-8-sig")
    form = type("F", (), {"cleaned_data": {"csv_file": SimpleUploadedFile("c.csv", csv_bytes)}})()
    items = importers.linkedin_parse(form)
    assert len(items) == 2
    assert items[0]["name"] == "AWS Certified Solutions Architect"
    assert items[0]["issued"] == "2023-01-01"      # "Jan 2023" parsed
    assert items[1]["issued"] == "2022-05-01"       # ISO passthrough


# --- generic view: lookup + confirm round-trip ---

def test_import_view_unknown_source_404(client, user):
    client.force_login(user)
    assert client.get("/track/import/nope/").status_code == 404


def test_import_view_confirm_writes_and_queues(client, user, csm):
    client.force_login(user)
    resp = client.post("/track/import/microsoft/", {
        "confirm": "1",
        "import_badge": [json.dumps({"cert_id": csm.pk, "issued": "2020-10-22",
                                     "expires": "", "source": "microsoft"})],
        "queue_badge": [json.dumps({"name": "Unknown MS Cert", "url": "https://x", "source": "Microsoft Learn"})],
    })
    assert resp.status_code == 302
    uc = UserCertification.objects.get(user=user, certification=csm)
    assert uc.import_source == "microsoft"
    assert str(uc.earned_date) == "2020-10-22"
    sub = SourceSubmission.objects.get(description__contains="Unknown MS Cert")
    assert sub.status == SourceSubmission.Status.QUEUED


def test_import_view_lookup_renders_matches(client, user, csm, monkeypatch):
    client.force_login(user)
    monkeypatch.setattr(importers.httpx, "get", lambda *a, **k: FakeResp(MS_PAYLOAD))
    resp = client.post("/track/import/microsoft/",
                       {"transcript_url": "https://learn.microsoft.com/en-us/users/x/transcript/abc"})
    assert resp.status_code == 200
    assert b"Azure Fundamentals" in resp.content
    assert b"queue for research" in resp.content   # no catalog match -> queue path shown
