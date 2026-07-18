"""Main-content measurement + render-aware classification (SEC-019).

The old heuristic measured the WHOLE page and could not separate a JS shell from a real
page: learn.microsoft.com/credentials/browse/ shipped 603 visible chars of pure chrome —
past the 500 threshold — and was filed `barren`. Measured outside nav/header/footer the
same page scores ~175 while real cert pages score thousands. Character counts here mirror
the live pages measured 2026-07-18.
"""
import importlib.util
import pathlib

import pytest

from apps.catalog.models import Source
from apps.research.discovery import classify_fetch

_spec = importlib.util.spec_from_file_location(
    "worker_crawl", pathlib.Path(__file__).resolve().parent.parent / "worker" / "crawl.py")
crawl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crawl)


def _chrome(n=700):
    # site furniture: present on every page, carries no content signal
    return (f"<nav>{'nav link ' * (n // 9)}</nav>"
            f"<header>{'brand tagline ' * 20}</header>"
            f"<footer>{'legal notice ' * 40}</footer>")


def test_main_text_len_excludes_chrome():
    shell = f"<html><body>{_chrome()}<main></main></body></html>"
    assert crawl.visible_text_len(shell) > 500      # full page looks substantial...
    assert crawl.main_text_len(shell) < 100         # ...but there is no content


def test_main_text_len_keeps_real_content():
    page = f"<html><body>{_chrome()}<main>{'real policy text ' * 400}</main></body></html>"
    assert crawl.main_text_len(page) > 5000


def test_cookie_banner_is_treated_as_chrome():
    shell = ('<html><body><div class="cookie-consent-banner">'
             + "we use cookies to improve your experience " * 30
             + "</div><main></main></body></html>")
    assert crawl.main_text_len(shell) < 100


# --- classification ---------------------------------------------------------

def test_empty_after_render_is_barren_not_needs_render():
    # a browser ran and the page is still empty: that is a real fact about the page
    assert classify_fetch(200, 603, 0, rendered=True, main_text_len=175) == Source.Status.BARREN


def test_empty_without_renderer_is_needs_render():
    # no browser available -> needs_render means "unrendered", not a guess
    assert classify_fetch(200, 603, 0, rendered=False,
                          main_text_len=175) == Source.Status.NEEDS_RENDER


def test_real_page_is_not_flagged_empty():
    assert classify_fetch(200, 12844, 0, rendered=True,
                          main_text_len=7728) == Source.Status.BARREN
    assert classify_fetch(200, 12844, 3, rendered=True,
                          main_text_len=7728) == Source.Status.HUB


def test_ms_learn_page_no_longer_misfiled_as_barren():
    # the regression this work exists to fix, at the live numbers
    assert classify_fetch(200, 603, 0, rendered=False,
                          main_text_len=175) == Source.Status.NEEDS_RENDER


def test_legacy_report_without_new_fields_keeps_old_behaviour():
    # pre-SEC-019 reports omit rendered/main_text_len
    assert classify_fetch(200, 100, 0) == Source.Status.NEEDS_RENDER
    assert classify_fetch(200, 100, 2) == Source.Status.HUB
    assert classify_fetch(200, 9000, 0) == Source.Status.BARREN


def test_dead_and_unchanged_are_unaffected():
    assert classify_fetch(404, None, 0, rendered=True) == Source.Status.DEAD
    assert classify_fetch("robots_disallowed", None, 0) == Source.Status.DEAD
    assert classify_fetch(200, 5, 0, unchanged=True, rendered=True) is None


def test_links_win_over_emptiness_when_rendered():
    # a rendered page with links is a hub even if its own text is thin
    assert classify_fetch(200, 400, 5, rendered=True, main_text_len=120) == Source.Status.HUB


@pytest.mark.parametrize("status", [500, 503, 403])
def test_server_errors_are_dead(status):
    assert classify_fetch(status, None, 0, rendered=True) == Source.Status.DEAD
