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

# English-only crawling (operator decision 2026-07-19): providers publish the same
# content under locale path segments (/ja-jp/, /de-de/, /es/), which multiplied the
# frontier with duplicates. A path segment that parses as a locale whose language isn't
# English drops the URL. Blocklist (not "everything non-en") so short non-locale segments
# like CompTIA's /ce/ can never be misread as a language.
_LOCALE_SEG = re.compile(r"^([a-z]{2})(?:[-_]([a-z]{2,4}))?$", re.I)
_NON_ENGLISH_LANGS = {
    "ar", "bg", "bn", "ca", "cs", "da", "de", "el", "es", "et", "fa", "fi", "fr",
    "he", "hi", "hr", "hu", "id", "it", "ja", "ko", "lt", "lv", "ms", "nb", "nl",
    "no", "pl", "pt", "ro", "ru", "sk", "sl", "sr", "sv", "ta", "th", "tr", "uk",
    "ur", "vi", "zh",
}


def is_english_url(url):
    """False when any path segment is a non-English locale code (ja-jp, de_DE, /fr/)."""
    for seg in urlparse(url).path.split("/"):
        m = _LOCALE_SEG.match(seg)
        if m and m.group(1).lower() in _NON_ENGLISH_LANGS:
            return False
    return True

_SCRIPT_STYLE_RE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.I | re.S)
_TAG_RE = re.compile(r'<[^>]+>')
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


def visible_text_len(html):
    """Rough count of visible (non-markup, non-script) characters. A JS-rendered shell
    returns a small number even on a 200 — one signal for 'needs_render' vs 'barren'."""
    t = _SCRIPT_STYLE_RE.sub(" ", html)
    t = _TAG_RE.sub(" ", t)
    return len(" ".join(t.split()))


# A JS shell still ships nav, footer, and a cookie banner — often well over a thousand
# visible chars — so a low text count alone misses them (learn.microsoft.com/credentials/
# browse/ was filed 'barren' at ~1.4k chars of pure chrome). These are positive shell
# markers: an app mount point left empty, or an explicit enable-JavaScript notice.
_EMPTY_MOUNT_RE = re.compile(
    r'<(div|main|section)\b[^>]*\bid=["\'](root|app|__next|main-content|content)["\'][^>]*>\s*'
    r'</\1>', re.I)
_ENABLE_JS_RE = re.compile(
    r'<noscript\b[^>]*>(?:(?!</noscript>).){0,400}?'
    r'(enable\s+javascript|javascript\s+(?:is\s+)?(?:required|disabled)|'
    r'requires\s+javascript|turn\s+on\s+javascript)', re.I | re.S)


# Chrome (nav, header, footer, cookie banner) is roughly constant across a site and swamps
# the content signal: learn.microsoft.com/credentials/browse/ carries 603 visible chars of
# pure chrome, while comptia's real cert page carries 15,749 — but measured against total
# markup the two are indistinguishable (0.037 vs 0.033), because inline JS dominates both.
# Measuring MAIN content instead of the whole page is what separates them.
_CHROME_RE = re.compile(
    r'<(nav|header|footer|aside)\b[^>]*>.*?</\1>|'
    r'<div\b[^>]*\b(?:class|id)=["\'][^"\']*\b(?:cookie|consent|banner|breadcrumb|'
    r'site-header|site-footer|skip-link)\b[^"\']*["\'][^>]*>.*?</div>', re.I | re.S)


def main_text_len(html):
    """Visible characters outside site chrome — the content signal, with nav/header/footer/
    aside and cookie-banner blocks removed. A shell drops to near zero here; a real page
    keeps nearly all of its text."""
    return visible_text_len(_CHROME_RE.sub(" ", html))


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
        if not is_english_url(url):
            continue                                   # locale duplicate: dropped
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
