"""Deterministic crawl-frontier helpers (worker/crawl.py, SEC-017). Pure stdlib functions;
no Django, no network. The security-critical behavior is same-domain-only discovery."""
import importlib.util
import pathlib

# worker/ is not a package; load crawl.py directly (same pattern as its schema.py mirror).
_spec = importlib.util.spec_from_file_location(
    "worker_crawl", pathlib.Path(__file__).resolve().parent.parent / "worker" / "crawl.py")
crawl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crawl)


def test_registrable_domain_collapses_subdomains():
    assert crawl.registrable_domain("community.isc2.org") == "isc2.org"
    assert crawl.registrable_domain("www.scrumalliance.org") == "scrumalliance.org"
    assert crawl.registrable_domain("university.atlassian.com:443") == "atlassian.com"


def test_same_domain():
    base = "https://www.isc2.org/certifications"
    assert crawl.same_domain(base, "https://www.isc2.org/policies/cpe")
    assert crawl.same_domain(base, "https://community.isc2.org/cpe")   # subdomain, same provider
    assert not crawl.same_domain(base, "https://credly.com/cpe")


def test_normalize_and_dedupe():
    assert crawl.normalize("https://X.org/a/?utm=1#frag") == "https://x.org/a"
    assert crawl.normalize("https://x.org/a/") == "https://x.org/a"
    # canonical wins when present
    assert crawl.dedupe_key("https://x.org/p?ref=2", "https://x.org/canonical") == "https://x.org/canonical"
    assert crawl.dedupe_key("https://x.org/p?ref=2") == "https://x.org/p"


def test_extract_canonical_both_attr_orders():
    assert crawl.extract_canonical(
        '<link rel="canonical" href="https://x.org/real">', "https://x.org/p") == "https://x.org/real"
    assert crawl.extract_canonical(
        '<link href="/real" rel="canonical">', "https://x.org/p") == "https://x.org/real"
    assert crawl.extract_canonical("<html></html>", "https://x.org/p") == ""


def test_scan_links_same_domain_keyword_only():
    html = """
      <a href="/get-certified/renewing-certifications">renew</a>
      <a href="https://www.scrumalliance.org/certification/cal">cal</a>
      <a href="/about-us">about</a>            <!-- off-keyword: dropped -->
      <a href="https://twitter.com/x/certification">social</a>  <!-- cross-domain: dropped -->
      <a href="mailto:x@y.org/cert">mail</a>    <!-- non-http: dropped -->
      <a href="/get-certified/renewing-certifications#seu">dup</a> <!-- dup after normalize -->
    """
    links = crawl.scan_links(html, "https://www.scrumalliance.org/get-certified")
    assert links == [
        "https://www.scrumalliance.org/get-certified/renewing-certifications",
        "https://www.scrumalliance.org/certification/cal",
    ]


def test_scan_links_drops_all_cross_domain():
    html = '<a href="https://evil.example/certification/pwn">x</a>' \
           '<a href="https://partner.other.com/cpe">y</a>'
    assert crawl.scan_links(html, "https://www.isc2.org/certifications") == []


def test_robots_allows_with_injected_fetcher():
    crawl._ROBOTS_CACHE.clear()
    robots = "User-agent: *\nDisallow: /private/\n"

    def serve(_url):
        return robots
    assert crawl.robots_allows("https://x.org/certification", fetcher=serve)
    assert not crawl.robots_allows("https://x.org/private/x", fetcher=serve)


def test_robots_fails_open_when_missing():
    crawl._ROBOTS_CACHE.clear()
    assert crawl.robots_allows("https://x.org/anything", fetcher=lambda u: None)


def test_visible_text_len_ignores_markup_and_scripts():
    shell = '<html><head><script>var x=' + 'a' * 5000 + ';</script></head><body></body></html>'
    assert crawl.visible_text_len(shell) < 20            # JS-heavy shell -> tiny visible text
    real = '<p>' + 'word ' * 200 + '</p>'
    assert crawl.visible_text_len(real) > 500
