"""Deterministic crawl-frontier helpers (docs/crawl-procedure.md, SEC-017).

Stdlib only — the worker is standalone and never imports Django. No LLM: untrusted page
content cannot choose crawl targets. Same-registrable-domain links only; cross-domain
links are dropped entirely (not returned, not recorded). Raw HTML stays worker-side
(SEC-006); only distilled link URLs + the canonical go to the server.
"""
import re
from urllib import robotparser
from urllib.parse import urljoin, urlparse, urlunparse

# A discovered path must look like a cert/renewal page to enter the frontier.
PATH_KEYWORDS = ("renew", "recert", "cpe", "ceu", "pdu", "maintain",
                 "certification", "cert", "policy", "credential")

_HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\'#]+)', re.I)
_CANON_RE = re.compile(
    r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']+)|'
    r'<link\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*\brel=["\']canonical["\']', re.I)


def registrable_domain(host):
    """Best-effort eTLD+1 (last two labels). Good enough for provider .com/.org sites and
    collapses same-provider subdomains (community.isc2.org -> isc2.org). Multi-part public
    suffixes (.co.uk) over-collapse; acceptable for the provider set, revisit if needed."""
    host = (host or "").lower().split(":")[0]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def same_domain(base_url, url):
    return registrable_domain(urlparse(base_url).netloc) == registrable_domain(urlparse(url).netloc)


def normalize(url):
    """Strip query, fragment, and trailing slash; lowercase host."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", "", "", ""))


def dedupe_key(url, canonical=""):
    """Canonical URL if the page declares one; else the normalized URL."""
    return normalize(canonical or url)


def extract_canonical(html, base_url):
    """The page's <link rel=canonical> as an absolute URL, or '' if none."""
    m = _CANON_RE.search(html)
    if not m:
        return ""
    return urljoin(base_url, m.group(1) or m.group(2))


def scan_links(html, base_url):
    """Same-domain, keyword-matching, deduped candidate URLs from the page.
    Cross-domain, non-http, and off-keyword links are dropped (SEC-017)."""
    out, seen = [], set()
    for href in _HREF_RE.findall(html):
        url = urljoin(base_url, href.strip())
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            continue
        if not same_domain(base_url, url):
            continue                                   # cross-domain: dropped entirely
        if not any(k in p.path.lower() for k in PATH_KEYWORDS):
            continue
        norm = normalize(url)
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


_ROBOTS_CACHE = {}


def robots_allows(url, user_agent="CertSleuthBot", fetcher=None):
    """True if robots.txt permits fetching url. `fetcher(robots_url) -> text | None` is
    injectable for tests; a missing/unreadable robots.txt fails open (standard). Cached
    per origin."""
    p = urlparse(url)
    origin = f"{p.scheme}://{p.netloc}"
    rp = _ROBOTS_CACHE.get(origin)
    if rp is None:
        rp = robotparser.RobotFileParser()
        text = fetcher(origin + "/robots.txt") if fetcher else None
        if text is None:
            rp.parse([])                               # empty ruleset -> allow all
        else:
            rp.parse(text.splitlines())
        _ROBOTS_CACHE[origin] = rp
    return rp.can_fetch(user_agent, url)
