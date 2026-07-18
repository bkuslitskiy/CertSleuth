"""Per-provider certification-name extraction from snapshot HTML.

og:title is the reliable cert-name source across providers; the generic <h1> is a
promotional banner on some (ISACA shows "CISM Wins at SC Awards!"). Rules are per-provider
because the og:title format differs (ISACA: "CODE | Full Name"; CompTIA: "Name | CompTIA";
GIAC/AWS: the whole string). Stdlib only, deterministic — output goes to staging (SEC-005),
never straight to the catalog. Category/non-cert pages return None.
"""
import html as _html
import re
from urllib.parse import urlparse

_OG = re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)', re.I)
_OG2 = re.compile(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:title["\']', re.I)
_TITLE = re.compile(r'<title[^>]*>([^<]*)', re.I)
_H1 = re.compile(r'<h1[^>]*>\s*([^<]{2,90})', re.I)
_SLUGLIKE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)+$')
_CATEGORY = re.compile(
    r'^(certifications?|our certifications|certification home|home|micro-?credentials?|'
    r'find a certification|portfolio|overview|discover.*|resources|training|'
    r'renewing.*|cpe information|.* awards?.*|.* wins .*|.* finalist .*)$', re.I)


def _clean(s):
    """Decode entities, drop ®/™/mis-decoded bytes, collapse whitespace."""
    s = _html.unescape(s or "")
    s = re.sub(r"[^\x00-\x7f]+", "", s)
    return re.sub(r"\s+", " ", s).strip(" -|")


def _og_title(page):
    m = _OG.search(page) or _OG2.search(page)
    return m.group(1) if m else ""


def _fallback_title(page):
    m = _TITLE.search(page)
    if m:
        return m.group(1)
    m = _H1.search(page)
    return m.group(1) if m else ""


# --- per-provider name rules (validated against live pages 2026-07-18) ---

def _name_whole(page):        # GIAC: "GIAC Strategic OSINT Analyst (GSOA)"
    return _clean(_og_title(page))


def _name_before_pipe(page):  # CompTIA: "Network+ (Plus) Certification | CompTIA"
    n = _clean(_og_title(page).split("|")[0])
    n = re.sub(r"\s*\bV\d+\b", "", n)                        # version tag
    n = re.sub(r"\s*\((?:New|Retiring) Version\)", "", n, flags=re.I)
    n = re.sub(r"\s*\(Plus\)", "", n)
    n = re.sub(r"\s+Certification$", "", n, flags=re.I)
    return n.strip()


def _name_after_pipe(page):   # ISACA: "CISM Certification | Certified Information Security Manager"
    parts = _og_title(page).split("|")
    return _clean(parts[1] if len(parts) > 1 else parts[0])


def _name_og_or_title(page):  # AWS: og:title usually clean; some newer pages return the slug
    name = _clean(_og_title(page))
    if not name or _SLUGLIKE.match(name):
        name = _clean(_fallback_title(page).split("|")[0])
    return name


# domain -> dict(slug, individual-cert URL regex, name fn, optional accept regex). URL
# regexes are anchored to the top-level cert page so sub-pages (exam outlines, quizzes)
# don't masquerade as certs.
PROVIDERS = {
    "giac.org": dict(slug="giac", url=re.compile(r"/certifications/.+-g[a-z]{2,6}/?$", re.I),
                     name=_name_whole),
    "comptia.org": dict(slug="comptia",
                        url=re.compile(r"/certifications/[a-z][a-z0-9-]*(?:/v\d+)?/?$", re.I),
                        name=_name_before_pipe),
    "isaca.org": dict(slug="isaca", url=re.compile(r"/credentialing/[a-z]{2,7}/?$", re.I),
                      name=_name_after_pipe,
                      accept=re.compile(r"^(certified|isaca (advanced|ai))", re.I)),
    "amazon.com": dict(slug="aws", url=re.compile(r"/certification/certified-[a-z0-9-]+/?$", re.I),
                       name=_name_og_or_title),
}


def _registrable(host):
    host = (host or "").lower().split(":")[0]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def extract_certification(url, page_html):
    """Return {provider_slug, slug, name} for an individual cert page, else None.
    Only handles the providers whose category h1 was unusable; the clean-template ones
    (Google, ISC2, Scrum Alliance) are handled elsewhere."""
    parsed = urlparse(url)
    rule = PROVIDERS.get(_registrable(parsed.netloc))
    if not rule:
        return None
    if not rule["url"].search(parsed.path):
        return None                                   # a category/sub/non-cert page
    slug = next((s for s in reversed(parsed.path.split("/"))
                 if s and not re.fullmatch(r"v\d+", s.lower())), "")
    name = rule["name"](page_html)
    if len(name) < 5 or _SLUGLIKE.match(name) or _CATEGORY.match(name):
        return None                                   # unreliable / not a real cert name
    if "accept" in rule and not rule["accept"].match(name):
        return None                                   # provider says this isn't a credential
    return {"provider_slug": rule["slug"], "slug": slug.lower(), "name": name}
