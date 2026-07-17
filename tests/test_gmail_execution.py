"""Gmail scan EXECUTION side (apps/tracker/gmail.py). The OAuth/Gmail body needs creds,
but the state-machine guard, config gate, and query builder are real and tested now."""
import pytest
from apps.tracker import gmail
from apps.research.models import GmailScanRequest


@pytest.fixture
def approved(user, db):
    return GmailScanRequest.objects.create(user=user, status=GmailScanRequest.Status.APPROVED)


def test_disabled_by_default(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ""
    assert gmail.is_configured() is False


def test_enabled_when_creds_present(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"
    assert gmail.is_configured() is True


def test_query_is_scoped_to_issuers_not_whole_inbox():
    q = gmail.gmail_query()
    assert q.startswith("from:")
    assert "from:credly.com" in q and "from:isc2.org" in q
    assert "OR" in q


def test_run_scan_refuses_unapproved(user, db, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"
    pending = GmailScanRequest.objects.create(user=user)  # PENDING
    with pytest.raises(ValueError, match="not approved"):
        gmail.run_scan(pending)


def test_run_scan_blocked_without_creds(approved, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = ""
    settings.GOOGLE_OAUTH_CLIENT_SECRET = ""
    with pytest.raises(gmail.GmailNotConfigured):
        gmail.run_scan(approved)


def test_run_scan_reaches_todo_body_when_approved_and_configured(approved, settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = "id"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = "secret"
    # Gate + config both pass -> control reaches the not-yet-implemented execution body.
    with pytest.raises(NotImplementedError):
        gmail.run_scan(approved)


def test_mark_completed_transitions(approved):
    gmail.mark_completed(approved)
    approved.refresh_from_db()
    assert approved.status == GmailScanRequest.Status.COMPLETED
    assert approved.resolved_at is not None
