"""Shared credential-import plumbing (spec 5.2-5.5).

Each source normalizes its data to a list of dicts, match_catalog() links them to catalog
Certifications, and confirm_import() writes matched rows + queues unmatched for research
(D16) — identically for every source. Credly (credly.py) predates this and keeps its own
view; these cover Microsoft Learn, Accredible, Open Badges, and LinkedIn.

SEC-013 note: the URL-based fetchers here (Microsoft Learn, Accredible) are the same
carve-out as the Credly lookup — user-triggered, domain-pinned to a credential platform,
fetching the *user's own* public credential, no LLM, no catalog write. Unmatched results
go to the inert SourceSubmission queue, so nothing here triggers research-crawler spend.
Uploaded-file parsers never fetch URLs found inside the file (SSRF guard, SEC-006).
"""
import csv
import io
import json
import re
import struct
from datetime import date
from urllib.parse import urlparse

import httpx

from apps.catalog.models import Certification


def _date(value):
    """ISO date/datetime -> 'YYYY-MM-DD', or None if absent/unparseable."""
    if not value:
        return None
    s = str(value)[:10]
    try:
        date.fromisoformat(s)
        return s
    except ValueError:
        return None


def match_catalog(items):
    """items: [{name, external_system, external_key, issued, expires, source, url}].
    Returns the same dicts with 'cert' set to a Certification or None. Match on
    external_ids first (D26), then case-insensitive name."""
    out = []
    for it in items:
        cert = None
        key, system = it.get("external_key"), it.get("external_system")
        if key and system:
            cert = Certification.objects.filter(**{f"external_ids__{system}": key}).first()
        if cert is None and it.get("name"):
            cert = Certification.objects.filter(name__iexact=it["name"]).first()
        out.append({**it, "cert": cert})
    return out


def confirm_import(request):
    """Shared confirm handler for every non-Credly source. Reads import_badge[] (matched,
    JSON with cert_id/issued/expires/source) and queue_badge[] (unmatched, JSON with
    name/url/source). Writes UserCertification rows; queues SourceSubmissions (D16,
    deduped). Returns (created, queued)."""
    from apps.research.models import SourceSubmission
    from .models import UserCertification
    created = queued = 0
    for raw in request.POST.getlist("import_badge"):
        try:
            b = json.loads(raw)
        except ValueError:
            continue
        if not b.get("cert_id"):
            continue
        _, was_new = UserCertification.objects.get_or_create(
            user=request.user, certification_id=b["cert_id"],
            defaults={"earned_date": b.get("issued") or None,
                      "expiry_date": b.get("expires") or None,
                      "import_source": b.get("source", "import")})
        created += was_new
    for raw in request.POST.getlist("queue_badge"):
        try:
            b = json.loads(raw)
        except ValueError:
            continue
        name = (b.get("name") or "").strip()
        if not name:
            continue
        label = b.get("source", "Import")
        _, was_new = SourceSubmission.objects.get_or_create(
            url=(b.get("url") or f"(no url) {name}")[:500],
            description=f"{label} credential with no catalog match: {name}"[:300],
            defaults={"submitted_by": request.user})
        queued += was_new
    return created, queued


# --- Microsoft Learn transcript (spec 5.5; confirmed schema in docs/research/import-sources.md) ---

MS_SHARE_RE = re.compile(r"/transcript/([A-Za-z0-9]+)")


def microsoft_fetch(form):
    """Paste a transcript share URL; fetch the (unofficial) share API; return active certs.
    Only cert fields are read — contactEmail/legalName/mcid in the response are ignored (D7)."""
    url = form.cleaned_data["transcript_url"]
    m = MS_SHARE_RE.search(url)
    if not m:
        raise httpx.HTTPError("Not a Microsoft Learn transcript share URL.")
    resp = httpx.get(
        f"https://learn.microsoft.com/api/profiles/transcript/share/{m.group(1)}",
        params={"locale": "en-us"}, timeout=15, headers={"Accept": "application/json"})
    resp.raise_for_status()
    cert_data = resp.json().get("certificationData") or {}
    items = []
    for c in cert_data.get("activeCertifications") or []:
        items.append({"name": c.get("name", ""), "external_system": "ms_learn",
                      "external_key": None, "issued": _date(c.get("dateEarned")),
                      "expires": _date(c.get("expiration")), "source": "Microsoft Learn",
                      "url": url})
    return items


# --- Accredible / credential.net (confirmed unauthenticated endpoint) ---

def accredible_fetch(form):
    """Paste a credential URL (credential.net or a branded Accredible domain); fetch the
    public credential-net endpoint by its id. Private credentials return nothing."""
    url = form.cleaned_data["credential_url"]
    segments = [s for s in urlparse(url).path.split("/") if s]
    if not segments:
        raise httpx.HTTPError("Not a credential URL.")
    cid = segments[-1]
    resp = httpx.get(
        f"https://api.accredible.com/v1/credential-net/credentials/{cid}",
        timeout=15, headers={"Accept": "application/json"})
    resp.raise_for_status()
    d = resp.json().get("data") or {}
    if d.get("private") or not d.get("name"):
        return []
    return [{"name": d.get("name", ""), "external_system": "accredible_group",
             "external_key": d.get("group_id"), "issued": _date(d.get("issued_on")),
             "expires": _date(d.get("expired_on")), "source": "Accredible", "url": url}]


# --- Open Badges 2.0/3.0 file upload (spec 5.3; issuer-agnostic, works for private profiles) ---

def _png_openbadges(raw):
    """Extract the baked 'openbadges' payload from a PNG's tEXt/iTXt chunk."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG file.")
    pos = 8
    while pos + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[pos:pos + 4])
        ctype = raw[pos + 4:pos + 8]
        data = raw[pos + 8:pos + 8 + length]
        if ctype in (b"tEXt", b"iTXt") and data.split(b"\x00", 1)[0] == b"openbadges":
            if ctype == b"tEXt":
                return data.split(b"\x00", 1)[1].decode("utf-8", "replace")
            # iTXt: keyword\0 compflag\0 compmethod\0 lang\0 transkeyword\0 text
            parts = data.split(b"\x00", 5)
            return parts[5].decode("utf-8", "replace")
        pos += 12 + length  # 4 len + 4 type + data + 4 crc
    raise ValueError("No Open Badge data baked into this PNG.")


def _svg_openbadges(raw):
    """Extract the baked assertion from an SVG's <openbadges:assertion> element."""
    text = raw.decode("utf-8", "replace")
    m = re.search(r"<openbadges:assertion[^>]*>(.*?)</openbadges:assertion>", text, re.S)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(r"<openbadges:assertion[^>]*\bverify=\"([^\"]+)\"", text)
    if m:
        return m.group(1)  # a URL — handled (and rejected) by the caller's SSRF guard
    raise ValueError("No Open Badge data embedded in this SVG.")


def _parse_ob_assertion(obj):
    """Normalize an OB 2.0 Assertion or OB 3.0 (Verifiable Credential) dict."""
    if "credentialSubject" in obj:  # OB 3.0 VC
        ach = obj["credentialSubject"].get("achievement", {})
        if isinstance(ach, list):
            ach = ach[0] if ach else {}
        name = ach.get("name", "")
        issued = obj.get("validFrom") or obj.get("issuanceDate")
        expires = obj.get("validUntil") or obj.get("expirationDate")
    else:  # OB 2.0 Assertion
        badge = obj.get("badge")
        name = badge.get("name", "") if isinstance(badge, dict) else ""
        issued = obj.get("issuedOn")
        expires = obj.get("expires")
    return {"name": name, "external_system": "openbadge", "external_key": None,
            "issued": _date(issued), "expires": _date(expires),
            "source": "Open Badge", "url": ""}


def openbadge_parse(form):
    """Parse an uploaded .json / .png / .svg Open Badge. Never fetches a hosted-assertion
    URL found inside the file (SSRF guard) — asks for the .json in that case."""
    f = form.cleaned_data["badge_file"]
    raw = f.read()
    name = (getattr(f, "name", "") or "").lower()
    if name.endswith(".png"):
        payload = _png_openbadges(raw)
    elif name.endswith(".svg"):
        payload = _svg_openbadges(raw)
    elif name.endswith(".json"):
        payload = raw.decode("utf-8", "replace")
    else:
        raise ValueError("Upload a .json, .png, or .svg Open Badge file.")
    payload = payload.strip()
    if not payload.startswith("{"):
        raise ValueError("This badge stores its data as a hosted link. Download and "
                         "upload the .json assertion instead.")
    obj = json.loads(payload)
    item = _parse_ob_assertion(obj)
    if not item["name"]:
        raise ValueError("Couldn't read a credential name from this badge.")
    return [item]


# --- LinkedIn certifications CSV (from the account data export) ---

def _linkedin_date(value):
    """LinkedIn exports dates as 'Mon YYYY' or 'YYYY-MM-DD'. Return ISO or None."""
    if not value:
        return None
    value = value.strip()
    iso = _date(value)
    if iso:
        return iso
    for fmt in ("%b %Y", "%B %Y"):
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def linkedin_parse(form):
    """Parse Certifications.csv from a LinkedIn data export. Column names per LinkedIn's
    documented export (Name, Url, Authority, Started On, Finished On, License Number);
    verify against a real export before relying on exact headers."""
    f = form.cleaned_data["csv_file"]
    text = f.read().decode("utf-8-sig", "replace")
    reader = csv.DictReader(io.StringIO(text))
    # Case-insensitive header access.
    items = []
    for row in reader:
        row = {(k or "").strip().lower(): v for k, v in row.items()}
        name = (row.get("name") or "").strip()
        if not name:
            continue
        items.append({"name": name, "external_system": "linkedin", "external_key": None,
                      "issued": _linkedin_date(row.get("started on")),
                      "expires": _linkedin_date(row.get("finished on")),
                      "source": "LinkedIn", "url": (row.get("url") or "").strip()})
    return items
