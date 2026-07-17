"""Gmail scan approval gate (SEC-013): user clicks queue a request; approvers execute."""
import pytest
from django.utils import timezone
from apps.research.models import GmailScanRequest


@pytest.fixture
def enabled_user(user):
    user.gmail_scan_enabled = True
    user.save(update_fields=["gmail_scan_enabled"])
    return user


def test_unenrolled_user_cannot_queue_scan(client, user):
    client.force_login(user)
    resp = client.post("/track/gmail/scan-request/")
    assert resp.status_code == 302
    assert resp.url == "/accounts/gmail-enrollment/"
    assert GmailScanRequest.objects.count() == 0


def test_enrolled_click_queues_pending_without_running(client, enabled_user):
    client.force_login(enabled_user)
    resp = client.post("/track/gmail/scan-request/")
    assert resp.status_code == 302
    req = GmailScanRequest.objects.get(user=enabled_user)
    assert req.status == GmailScanRequest.Status.PENDING   # queued, nothing executed


def test_open_request_is_not_duplicated(client, enabled_user):
    client.force_login(enabled_user)
    client.post("/track/gmail/scan-request/")
    client.post("/track/gmail/scan-request/")
    assert GmailScanRequest.objects.filter(user=enabled_user).count() == 1
    # ...but a completed request allows asking again
    GmailScanRequest.objects.update(status=GmailScanRequest.Status.COMPLETED)
    client.post("/track/gmail/scan-request/")
    assert GmailScanRequest.objects.filter(user=enabled_user).count() == 2


def test_approver_action_resolves_pending_only(client, enabled_user, approver, rf):
    from django.contrib import admin, messages
    from apps.research.admin import GmailScanRequestAdmin
    done = GmailScanRequest.objects.create(user=enabled_user,
                                           status=GmailScanRequest.Status.COMPLETED,
                                           resolved_at=timezone.now())
    pending = GmailScanRequest.objects.create(user=enabled_user)
    request = rf.post("/admin/research/gmailscanrequest/")
    request.user = approver
    request.session = {}
    request._messages = messages.storage.default_storage(request)
    admin_obj = GmailScanRequestAdmin(GmailScanRequest, admin.site)
    admin_obj.approve_selected(request, GmailScanRequest.objects.all())
    pending.refresh_from_db()
    done.refresh_from_db()
    assert pending.status == GmailScanRequest.Status.APPROVED
    assert pending.resolved_by == approver
    assert done.status == GmailScanRequest.Status.COMPLETED  # untouched
