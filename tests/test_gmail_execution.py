"""Gmail scan EXECUTION (apps/tracker/gmail.py + the run/callback views, SEC-020).

Google endpoints are mocked at the httpx layer — the tests exercise the real state
machine, signed-state validation, bounded fetch, deterministic parsing, and the
token-never-stored property (no model anywhere receives the token).
"""
import pytest
from django.core import signing

from apps.research.models import GmailScanRequest
from apps.tracker import gmail

pytestmark = pytest.mark.django_db


@pytest.fixture
def approved(user, db):
    return GmailScanRequest.objects.create(user=user, status=GmailScanRequest.Status.APPROVED)


@pytest.fixture
def creds(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"


def _raw(mid, sender, subject, date="Fri, 18 Jul 2026 10:00:00 +0000"):
    """Gmail API wire shape (messages.get response)."""
    return {"id": mid, "snippet": "snip", "payload": {"headers": [
        {"name": "From", "value": sender}, {"name": "Subject", "value": subject},
        {"name": "Date", "value": date}]}}


def _norm(mid, sender, subject, date="Fri, 18 Jul 2026 10:00:00 +0000"):
    """fetch_messages output shape (what parse_messages consumes)."""
    return {"message_id": mid, "from": sender, "subject": subject, "date": date,
            "snippet": "snip"}


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


# --- gates (unchanged behavior) ---------------------------------------------

def test_disabled_by_default(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = settings.GOOGLE_OAUTH_CLIENT_SECRET = ""
    assert gmail.is_configured() is False


def test_query_is_scoped_to_issuers_not_whole_inbox():
    q = gmail.gmail_query()
    assert q.startswith("from:") and "from:credly.com" in q and "OR" in q


def test_run_scan_refuses_unapproved(user, creds):
    pending = GmailScanRequest.objects.create(user=user)
    with pytest.raises(ValueError, match="not approved"):
        gmail.run_scan(pending, "tok")


def test_run_scan_blocked_without_creds(approved, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = settings.GOOGLE_OAUTH_CLIENT_SECRET = ""
    with pytest.raises(gmail.GmailNotConfigured):
        gmail.run_scan(approved, "tok")


# --- signed state ------------------------------------------------------------

def test_state_round_trip_and_user_binding(user, approver):
    raw = signing.dumps({"u": user.pk, "s": 7}, salt="gmail-scan")
    assert gmail.read_state(raw, user) == 7
    with pytest.raises(signing.BadSignature):
        gmail.read_state(raw, approver)          # someone else's state
    with pytest.raises(signing.BadSignature):
        gmail.read_state(raw + "x", user)        # tampered


# --- parsing (extract-and-discard) ------------------------------------------

def test_parse_congratulations_subject():
    items = gmail.parse_messages([_norm("m1", "no-reply@credly.com",
                                        "Congratulations! You earned: AWS Certified Security - Specialty")])
    assert len(items) == 1
    it = items[0]
    assert it["name"] == "AWS Certified Security - Specialty"
    assert it["external_key"] == "m1" and it["external_system"] == "gmail"
    assert it["issued"] == "2026-07-18"
    assert it["confidence"] == "inferred"


def test_parse_your_certification_is_ready():
    items = gmail.parse_messages([_norm("m2", "certs@isc2.org",
                                        "Your CISSP certification has been issued")])
    assert items[0]["name"] == "CISSP"


def test_unparseable_subjects_are_dropped_not_guessed():
    items = gmail.parse_messages([
        _norm("m3", "news@credly.com", "Weekly digest: top badges this month"),
        _norm("m4", "no-reply@isc2.org", "Renew your membership today")])
    assert items == []


# --- run_scan end-to-end with mocked Gmail -----------------------------------

def test_run_scan_fetches_parses_and_completes(approved, creds, monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        if url.endswith("/messages"):
            assert params["q"] == gmail.gmail_query()        # bounded query, never blank
            assert params["maxResults"] == gmail.MAX_MESSAGES
            return _Resp({"messages": [{"id": "m1"}]})
        assert params["format"] == "metadata"                # headers+snippet only
        return _Resp(_raw("m1", "no-reply@credly.com",
                          "Congratulations! You earned: Certified ScrumMaster"))

    monkeypatch.setattr(gmail.httpx, "get", fake_get)
    items = gmail.run_scan(approved, "short-lived-token")
    assert [i["name"] for i in items] == ["Certified ScrumMaster"]
    approved.refresh_from_db()
    assert approved.status == GmailScanRequest.Status.COMPLETED


# --- views -------------------------------------------------------------------

def test_run_view_requires_approved_request(client, user, creds):
    client.force_login(user)
    resp = client.get("/track/gmail/run/", follow=True)
    assert b"No approved scan" in resp.content


def test_run_view_redirects_to_google(client, user, approved, creds):
    client.force_login(user)
    resp = client.get("/track/gmail/run/")
    assert resp.status_code == 302
    assert resp.url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "gmail.readonly" in resp.url and "access_type=online" in resp.url


def test_callback_rejects_foreign_state(client, user, approver, approved, creds):
    state = signing.dumps({"u": approver.pk, "s": approved.pk}, salt="gmail-scan")
    client.force_login(user)
    resp = client.get(f"/track/gmail/callback/?code=x&state={state}", follow=True)
    assert b"stale or not yours" in resp.content


def test_callback_happy_path_renders_preview(client, user, approved, creds, monkeypatch):
    monkeypatch.setattr(gmail, "exchange_code", lambda code, uri: "tok")
    monkeypatch.setattr(gmail, "fetch_messages", lambda tok: [
        _norm("m1", "no-reply@credly.com", "Congratulations! You earned: Certified ScrumMaster")])
    state = signing.dumps({"u": user.pk, "s": approved.pk}, salt="gmail-scan")
    client.force_login(user)
    resp = client.get(f"/track/gmail/callback/?code=abc&state={state}")
    assert resp.status_code == 200
    assert b"Certified ScrumMaster" in resp.content
    approved.refresh_from_db()
    assert approved.status == GmailScanRequest.Status.COMPLETED


def test_mark_completed_transitions(approved):
    gmail.mark_completed(approved)
    approved.refresh_from_db()
    assert approved.status == GmailScanRequest.Status.COMPLETED
    assert approved.resolved_at is not None
