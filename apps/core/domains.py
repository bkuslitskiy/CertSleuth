"""Registrable-domain helper shared by catalog.Source and research.SourceSubmission.
Mirrors worker/crawl.py registrable_domain — the worker stays stdlib-standalone, so the
two-line logic is duplicated there, not imported."""
from urllib.parse import urlparse


def registrable_domain(url):
    """Best-effort eTLD+1 (last two labels), port stripped, lowercased."""
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host
