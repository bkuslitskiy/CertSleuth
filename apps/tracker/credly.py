"""Credly public-profile import (spec 5.2). Unofficial endpoint — SEC/D6 accepted with backups."""
import re
import httpx
from apps.catalog.models import Certification

PROFILE_RE = re.compile(r"credly\.com/users/([A-Za-z0-9._-]+)")


def fetch_credly_badges(profile_url: str) -> list[dict]:
    m = PROFILE_RE.search(profile_url)
    if not m:
        raise httpx.HTTPError("Not a Credly profile URL")
    url = f"https://www.credly.com/users/{m.group(1)}/badges.json"
    resp = httpx.get(url, timeout=15, headers={"Accept": "application/json"})
    resp.raise_for_status()
    return resp.json().get("data", [])


def match_badges(badges: list[dict]) -> list[dict]:
    """Match on external_ids.credly_template first (D26), fall back to name contains."""
    out = []
    for b in badges:
        template = b.get("badge_template", {})
        tid, tname = template.get("id"), template.get("name", "")
        cert = (Certification.objects.filter(external_ids__credly_template=tid).first()
                or Certification.objects.filter(name__iexact=tname).first())
        out.append({"badge": tname, "issued": b.get("issued_at_date"),
                    "expires": b.get("expires_at_date"), "cert": cert})
    return out
