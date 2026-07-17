"""D13 Gmail on-demand scan — EXECUTION side (SEC-013: runs only approved requests).

The approval gate is GmailScanRequest (research app): a user's "Scan my inbox" click
queues a request; an approver approves it; only then may this run. Token acquisition and
the Gmail API calls need GOOGLE_OAUTH_* creds (docs/gcp-setup.md §2) and are stubbed until
those exist — run_scan enforces the state machine and the config gate today, so wiring the
OAuth/Gmail internals later is the only remaining step.

Contract when implemented (spec 5.1, SEC-003/SEC-006):
- fresh OAuth consent per scan; access token used for one pass, then discarded (no storage)
- query ONLY known issuer senders (gmail_query below), never the whole mailbox
- extract-and-discard: persist message-id + extracted fields + confidence, never raw bodies (D7)
- extraction output goes to StagedChange like every extractor (SEC-005), never to the catalog
"""
from django.conf import settings
from django.utils import timezone


class GmailNotConfigured(RuntimeError):
    """GOOGLE_OAUTH_* creds are absent, so the feature is disabled (settings default blank)."""


# Known credential-issuer sender domains — the scan is scoped to these, never the full inbox.
ISSUER_SENDERS = [
    "credly.com", "isc2.org", "scrumalliance.org", "microsoft.com", "pmi.org",
    "comptia.org", "aws.amazon.com", "cloud.google.com", "credential.net", "accredible.com",
]


def is_configured():
    """True when Gmail scanning is enabled (OAuth creds present)."""
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def gmail_query():
    """The bounded sender query — a scoped filter, never a full-mailbox crawl (spec 5.1)."""
    return " OR ".join(f"from:{domain}" for domain in ISSUER_SENDERS)


def run_scan(scan_request):
    """Execute one APPROVED GmailScanRequest. Guards the state machine and the config gate;
    the OAuth/Gmail/extract body lands here once creds exist. Meant to be dispatched by a
    django-q task or the approver action, not called directly from a user request."""
    from apps.research.models import GmailScanRequest
    if scan_request.status != GmailScanRequest.Status.APPROVED:
        raise ValueError(
            f"GmailScanRequest {scan_request.pk} is '{scan_request.status}', not approved")
    if not is_configured():
        raise GmailNotConfigured(
            "Set GOOGLE_OAUTH_CLIENT_ID/SECRET (docs/gcp-setup.md §2) before running scans.")
    # --- Remaining work (needs creds), per the contract above: ---
    # 1. fresh OAuth consent -> short-lived access token (discarded after this call)
    # 2. Gmail users.messages.list(q=gmail_query()) -> users.messages.get for each hit
    # 3. extract-and-discard cert facts -> StagedChange rows (SEC-005), never raw bodies
    # 4. mark the request COMPLETED and stamp resolved_at
    raise NotImplementedError(
        "Gmail scan execution body lands here once GOOGLE_OAUTH_* creds are configured.")


def mark_completed(scan_request):
    """Helper the execution body will call on success (kept here so the state transition
    is defined and tested now)."""
    from apps.research.models import GmailScanRequest
    scan_request.status = GmailScanRequest.Status.COMPLETED
    scan_request.resolved_at = timezone.now()
    scan_request.save(update_fields=["status", "resolved_at"])
