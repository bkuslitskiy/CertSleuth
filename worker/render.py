"""Headless rendering for the fetch pass (SEC-019).

Rendering by default beats detecting-then-rendering: deciding "does this page need a
browser" from raw HTML is strictly harder than just using one, and the signals that would
drive that decision (visible-text counts, text:markup ratios) do not separate a JS shell
from a content-heavy page — site chrome and inline bundles swamp both. Conditional fetch
keeps the cost bounded: a 304 never reaches the renderer.

Playwright is an OPTIONAL dependency. If it is not installed the worker degrades to plain
urllib and marks affected pages `needs_render` — which then means "no renderer available",
a fact, rather than a guess about the markup.

SECURITY: rendering EXECUTES untrusted provider JavaScript (SEC-006 treats page content as
untrusted). It runs in Chromium's sandbox, with JS confined to the page — but this module
never evaluates page-supplied script itself, never follows page-driven navigation to another
origin, and returns HTML only. No page content reaches an LLM or the server (SEC-005/006).
"""
import sys

RENDER_TIMEOUT_MS = 20000
# Content injected after load settles is what rendering exists to capture; networkidle
# overruns on sites with polling/analytics, so settle on the DOM and add a short grace.
SETTLE_MS = 1200


def available():
    """True if Playwright and a browser binary are importable."""
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def unavailable_reason():
    """Human-readable install hint, or '' when rendering is available."""
    if available():
        return ""
    return ("playwright not installed — `pip install playwright && playwright install "
            "chromium`; pages will be fetched unrendered and marked needs_render")


class Renderer:
    """Reusable browser for one fetch pass. Use as a context manager; a single browser
    process is amortized across the batch rather than paid per page."""

    def __init__(self, user_agent, timeout_ms=RENDER_TIMEOUT_MS):
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self._pw = self._browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        return self

    def __exit__(self, *exc):
        for closer in (getattr(self._browser, "close", None), getattr(self._pw, "stop", None)):
            if closer:
                try:
                    closer()
                except Exception:
                    pass
        self._browser = self._pw = None
        return False

    def render(self, url, headers=None):
        """Load url in the browser and return (status, html, response_headers).

        Returns (None, None, {}) on any failure so the caller can fall back to the raw
        fetch — a renderer problem must never lose a page.
        """
        ctx = None
        try:
            ctx = self._browser.new_context(user_agent=self.user_agent)
            if headers:
                ctx.set_extra_http_headers(headers)
            page = ctx.new_page()
            # Images/fonts/media cost time and tell us nothing; CSS and JS must load
            # because the content we came for is what the JS renders.
            page.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in ("image", "media", "font")
                else route.continue_()))
            resp = page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(SETTLE_MS)
            html = page.content()
            status = resp.status if resp is not None else None
            resp_headers = dict(resp.headers) if resp is not None else {}
            return status, html, resp_headers
        except Exception as e:
            print(f"render failed for {url}: {e}", file=sys.stderr)
            return None, None, {}
        finally:
            if ctx is not None:
                try:
                    ctx.close()
                except Exception:
                    pass
