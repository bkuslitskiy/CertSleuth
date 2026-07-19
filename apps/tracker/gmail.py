"""D13 Gmail on-demand scan — EXECUTION side (SEC-013: runs only approved requests).

The approval gate is GmailScanRequest (research app): a user's "Scan my inbox" click
queues a request; an approver approves it; only then may this run. Token acquisition and
the Gmail API calls need GOOGLE_OAUTH_* creds (docs/gcp-setup.md §2) and are stubbed until
those exist — run_scan enforces the state machine and the config gate today, so wiring the
OAuth/Gmail internals later is the only remaining step.

Contract (spec 5.1, SEC-003/SEC-006/SEC-020):
- fresh OAuth consent per scan; access token used for one pass, then discarded (no storage)
- query ONLY known issuer senders (gmail_query below), never the whole mailbox
- only message metadata is fetched (format=metadata: headers + snippet) — bodies never
  leave Google; extract-and-discard keeps message-id + extracted fields + confidence (D7)
- findings are USER-credential sightings, so they flow through the shared importer
  preview/confirm (match_catalog/confirm_import) like Credly/MS Learn — the user confirms
  rows into their own tracker; unmatched names queue for research (D16). Catalog-side
  StagedChange is not involved: nothing here is a catalog fact.
"""
import re

import httpx
from django.conf import settings
from django.core import signing
from django.urls import reverse
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


GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
MAX_MESSAGES = 50            # one-shot pass, bounded (spec 5.1)
STATE_MAX_AGE = 600          # seconds a consent round-trip may take

# Subject-line shapes issuers actually use. Deterministic — no LLM reads mail (v1).
_SUBJECT_PATTERNS = [
    re.compile(r"(?:congratulations|congrats).{0,40}?(?:earned|achieved|passed)[:\s]+(?P<name>[A-Z][^!.]{4,90})", re.I),
    re.compile(r"you(?:'ve| have) (?:earned|achieved|been awarded)[:\s]+(?P<name>[A-Z][^!.]{4,90})", re.I),
    re.compile(r"your (?P<name>[A-Z][^!.]{4,80}?) (?:certification|credential|badge) (?:is ready|has been issued|was issued)", re.I),
    re.compile(r"certificat(?:e|ion) (?:earned|issued|awarded)[:\s]+(?P<name>[A-Z][^!.]{4,90})", re.I),
]


def auth_url(request, scan_request):
    """Google consent URL for one approved scan. State is a signed (user, scan) pair so
    the callback can't be replayed across users or scans (SEC-013)."""
    from urllib.parse import urlencode
    state = signing.dumps({"u": request.user.pk, "s": scan_request.pk}, salt="gmail-scan")
    return GOOGLE_AUTH + "?" + urlencode({
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": request.build_absolute_uri(reverse("gmail_scan_callback")),
        "response_type": "code", "scope": SCOPE, "state": state,
        "access_type": "online",      # no refresh token: one-shot by construction
        "prompt": "consent",
    })


def read_state(raw, user):
    """Validate the signed state; returns the scan-request pk or raises BadSignature."""
    data = signing.loads(raw, salt="gmail-scan", max_age=STATE_MAX_AGE)
    if data.get("u") != user.pk:
        raise signing.BadSignature("state was issued to a different user")
    return data["s"]


def exchange_code(code, redirect_uri):
    """Authorization code -> short-lived access token. The token lives only in the
    caller's frame for the duration of one scan pass (SEC-003: never persisted)."""
    resp = httpx.post(GOOGLE_TOKEN, data={
        "code": code, "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": redirect_uri, "grant_type": "authorization_code"}, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_messages(access_token):
    """One bounded pass: list issuer-sender messages, then metadata per hit. Only
    headers + snippet are ever requested (format=metadata) — bodies never leave Google."""
    headers = {"Authorization": f"Bearer {access_token}"}
    listing = httpx.get(f"{GMAIL_API}/messages",
                        params={"q": gmail_query(), "maxResults": MAX_MESSAGES},
                        headers=headers, timeout=20)
    listing.raise_for_status()
    out = []
    for ref in listing.json().get("messages", []):
        msg = httpx.get(f"{GMAIL_API}/messages/{ref['id']}",
                        params={"format": "metadata",
                                "metadataHeaders": ["From", "Subject", "Date"]},
                        headers=headers, timeout=20)
        msg.raise_for_status()
        data = msg.json()
        hdrs = {h["name"].lower(): h["value"]
                for h in data.get("payload", {}).get("headers", [])}
        out.append({"message_id": ref["id"], "from": hdrs.get("from", ""),
                    "subject": hdrs.get("subject", ""), "date": hdrs.get("date", ""),
                    "snippet": data.get("snippet", "")})
    return out


def parse_messages(messages):
    """Deterministic extract-and-discard: message metadata -> importer-shaped items.
    Emits only what a subject line states; no match -> the message is simply dropped."""
    from email.utils import parsedate_to_datetime
    items = []
    for m in messages:
        name = None
        for pat in _SUBJECT_PATTERNS:
            hit = pat.search(m["subject"])
            if hit:
                name = hit.group("name").strip().strip('"')
                break
        if not name:
            continue
        issued = None
        try:
            issued = parsedate_to_datetime(m["date"]).date().isoformat()
        except (TypeError, ValueError):
            pass
        sender_domain = m["from"].split("@")[-1].strip(">").lower()
        items.append({"name": name, "external_system": "gmail",
                      "external_key": m["message_id"], "issued": issued, "expires": None,
                      "source": "Gmail", "url": "",
                      "confidence": "inferred", "sender": sender_domain})
    return items


def run_scan(scan_request, access_token):
    """Execute one APPROVED GmailScanRequest with a caller-supplied consent token.
    Fetch -> parse -> COMPLETED. The token is used for this pass and discarded by the
    caller; nothing here stores it. Returns importer-shaped items for preview/confirm."""
    from apps.research.models import GmailScanRequest
    if scan_request.status != GmailScanRequest.Status.APPROVED:
        raise ValueError(
            f"GmailScanRequest {scan_request.pk} is '{scan_request.status}', not approved")
    if not is_configured():
        raise GmailNotConfigured(
            "Set GOOGLE_OAUTH_CLIENT_ID/SECRET (docs/gcp-setup.md §2) before running scans.")
    items = parse_messages(fetch_messages(access_token))
    mark_completed(scan_request)
    return items


def mark_completed(scan_request):
    """Helper the execution body will call on success (kept here so the state transition
    is defined and tested now)."""
    from apps.research.models import GmailScanRequest
    scan_request.status = GmailScanRequest.Status.COMPLETED
    scan_request.resolved_at = timezone.now()
    scan_request.save(update_fields=["status", "resolved_at"])
