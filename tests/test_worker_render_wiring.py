"""Renderer wiring in the worker fetch path (SEC-019).

Rendering is on by default, but it must never cost correctness: a 304 skips the browser
entirely, and a render failure falls back to the raw HTML rather than losing the page.
"""
import importlib.util
import io
import pathlib
import urllib.error

_WORKER = pathlib.Path(__file__).resolve().parent.parent / "worker"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"worker_{name}", _WORKER / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cw = _load("claude_worker")
render = _load("render")

RAW = b"<html><body><nav>nav</nav><main>raw server html</main></body></html>"
RENDERED = ("<html><body><nav>nav</nav><main>" + "content the JS built " * 60
            + "</main></body></html>")


class _Resp(io.BytesIO):
    headers = {"ETag": "W/\"x\"", "Last-Modified": "Wed, 01 Jan 2025 00:00:00 GMT"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Renderer:
    """Stand-in for render.Renderer with a scriptable outcome."""

    def __init__(self, status=200, html=RENDERED):
        self.status, self.html, self.calls = status, html, 0

    def render(self, url, headers=None):
        self.calls += 1
        if self.status is None:
            return None, None, {}
        return self.status, self.html, {}


def _ok(monkeypatch):
    monkeypatch.setattr(cw.crawl, "robots_allows", lambda *a, **k: True)
    monkeypatch.setattr(cw.urllib.request, "urlopen", lambda *a, **k: _Resp(RAW))


def test_rendered_html_replaces_raw_when_render_succeeds(monkeypatch):
    _ok(monkeypatch)
    r = _Renderer()
    report, content = cw._fetch_one("https://x.test/a", {}, r)
    assert r.calls == 1
    assert report["rendered"] is True
    assert b"content the JS built" in content          # snapshot is the rendered DOM
    assert report["main_text_len"] > 500


def test_falls_back_to_raw_when_render_fails(monkeypatch):
    _ok(monkeypatch)
    r = _Renderer(status=None)
    report, content = cw._fetch_one("https://x.test/a", {}, r)
    assert report["rendered"] is False
    assert content == RAW                              # page is kept, not lost
    assert report["http_status"] == 200


def test_falls_back_when_render_returns_non_200(monkeypatch):
    _ok(monkeypatch)
    report, content = cw._fetch_one("https://x.test/a", {}, _Renderer(status=403))
    assert report["rendered"] is False
    assert content == RAW


def test_render_2xx_with_content_is_accepted(monkeypatch):
    # scrum.org's CDN answers the rendered document request with 202 + the full page;
    # any 2xx with content is a successful render, not a failure to fall back from.
    _ok(monkeypatch)
    report, content = cw._fetch_one("https://x.test/a", {}, _Renderer(status=202))
    assert report["rendered"] is True
    assert b"content the JS built" in content


def test_no_renderer_reports_rendered_false(monkeypatch):
    _ok(monkeypatch)
    report, _ = cw._fetch_one("https://x.test/a", {}, None)
    assert report["rendered"] is False


def test_304_never_reaches_the_browser(monkeypatch):
    monkeypatch.setattr(cw.crawl, "robots_allows", lambda *a, **k: True)

    def _304(*a, **k):
        raise urllib.error.HTTPError("u", 304, "Not Modified", {}, None)

    monkeypatch.setattr(cw.urllib.request, "urlopen", _304)
    r = _Renderer()
    report, content = cw._fetch_one("https://x.test/a", {"etag": "W/\"x\""}, r)
    assert report == {"unchanged": True} and content is None
    assert r.calls == 0                                # conditional fetch shields the browser


def test_robots_disallow_never_reaches_the_browser(monkeypatch):
    monkeypatch.setattr(cw.crawl, "robots_allows", lambda *a, **k: False)
    r = _Renderer()
    report, content = cw._fetch_one("https://x.test/a", {}, r)
    assert report["http_status"] == "robots_disallowed"
    assert r.calls == 0


def test_render_module_degrades_without_playwright():
    # available() must answer, not raise, when the optional dep is absent
    assert isinstance(render.available(), bool)
    if not render.available():
        assert "playwright" in render.unavailable_reason()
    else:
        assert render.unavailable_reason() == ""


def test_fetch_disables_render_when_unavailable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cw.render, "available", lambda: False)
    monkeypatch.setattr(cw, "_req", lambda url, data=None: {"jobs": []})
    captured = {}
    monkeypatch.setattr(cw, "_fetch_loop",
                        lambda api, jobs, outdir, renderer: captured.setdefault("r", renderer))
    cw.fetch("https://stub", 1, use_render=True)
    assert captured["r"] is None                       # degraded, did not crash


def test_403_falls_through_to_renderer(monkeypatch):
    # Bot-gated sites 403 the raw client but pass a real browser (PMI/Tableau/Cisco).
    monkeypatch.setattr(cw.crawl, "robots_allows", lambda *a, **k: True)

    def _403(*a, **k):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

    monkeypatch.setattr(cw.urllib.request, "urlopen", _403)
    r = _Renderer()
    report, content = cw._fetch_one("https://bot-walled.test/certs", {}, r)
    assert r.calls == 1
    assert report["http_status"] == 200 and report["rendered"] is True
    assert b"content the JS built" in content


def test_403_without_renderer_stays_dead(monkeypatch):
    monkeypatch.setattr(cw.crawl, "robots_allows", lambda *a, **k: True)

    def _403(*a, **k):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

    monkeypatch.setattr(cw.urllib.request, "urlopen", _403)
    report, content = cw._fetch_one("https://bot-walled.test/certs", {}, None)
    assert report == {"http_status": 403} and content is None


def test_403_render_failure_stays_dead(monkeypatch):
    monkeypatch.setattr(cw.crawl, "robots_allows", lambda *a, **k: True)

    def _403(*a, **k):
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)

    monkeypatch.setattr(cw.urllib.request, "urlopen", _403)
    report, content = cw._fetch_one("https://bot-walled.test/certs", {}, _Renderer(status=None))
    assert report == {"http_status": 403} and content is None
