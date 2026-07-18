"""Per-provider cert-name extraction (worker/extractors.py). og:title is the source; the
generic h1 is a promo banner on some providers. Fixtures mirror the live og:title formats
validated 2026-07-18. Category/non-cert pages must return None."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "worker_extractors",
    pathlib.Path(__file__).resolve().parent.parent / "worker" / "extractors.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)


def _page(og="", title="", h1=""):
    parts = []
    if og:
        parts.append(f'<meta property="og:title" content="{og}">')
    if title:
        parts.append(f"<title>{title}</title>")
    if h1:
        parts.append(f"<h1>{h1}</h1>")
    return "<html><head>" + "".join(parts) + "</head></html>"


def test_isaca_takes_name_after_pipe_not_promo_h1():
    # h1 is a promotional banner; og:title carries the real name.
    page = _page(og="CISM&#174; Certification | Certified Information Security Manager&#174;",
                 h1="CISM Wins at SC Awards North America!")
    got = ex.extract_certification("https://www.isaca.org/credentialing/cism", page)
    assert got == {"provider_slug": "isaca", "slug": "cism",
                   "name": "Certified Information Security Manager"}


def test_comptia_takes_name_before_pipe():
    page = _page(og="Network+ (Plus) Certification | CompTIA")
    got = ex.extract_certification("https://www.comptia.org/en-us/certifications/network", page)
    assert got == {"provider_slug": "comptia", "slug": "network", "name": "Network+"}


def test_giac_uses_whole_og_title():
    page = _page(og="GIAC Strategic OSINT Analyst (GSOA)")
    got = ex.extract_certification(
        "https://www.giac.org/certifications/strategic-osint-analyst-gsoa", page)
    assert got["provider_slug"] == "giac"
    assert got["name"] == "GIAC Strategic OSINT Analyst (GSOA)"


def test_aws_falls_back_to_title_when_og_is_slug():
    page = _page(og="certified-machine-learning-engineer-associate",
                 title="AWS Certified Machine Learning Engineer - Associate")
    got = ex.extract_certification(
        "https://aws.amazon.com/certification/certified-machine-learning-engineer-associate", page)
    assert got["name"] == "AWS Certified Machine Learning Engineer - Associate"


def test_aws_clean_og_title():
    page = _page(og="AWS Certified Security - Specialty")
    got = ex.extract_certification(
        "https://aws.amazon.com/certification/certified-security-specialty", page)
    assert got["name"] == "AWS Certified Security - Specialty"


def test_category_page_returns_none():
    # a hub/category URL, not an individual cert
    assert ex.extract_certification("https://www.giac.org/certifications/", _page(og="Find a Certification")) is None
    assert ex.extract_certification("https://www.comptia.org/en-us/certifications",
                                    _page(og="Our Certifications | CompTIA")) is None


def test_promo_name_rejected():
    # even on a cert-shaped URL, a promo/awards name is rejected
    page = _page(og="CISA Is a Finalist for Two Notable Awards")
    assert ex.extract_certification("https://www.isaca.org/credentialing/cisa", page) is None


def test_unknown_provider_returns_none():
    assert ex.extract_certification("https://example.com/x", _page(og="Something")) is None


def test_isaca_subpages_rejected():
    # exam-outline / quiz sub-pages must not masquerade as certs (URL not top-level)
    page = _page(og="CISA Exam Content Outline | Something")
    assert ex.extract_certification(
        "https://www.isaca.org/credentialing/cisa-exam-content-outline", page) is None
    assert ex.extract_certification(
        "https://www.isaca.org/credentialing/cisa/practice-quiz", page) is None


def test_isaca_rejects_non_credential_names():
    # top-level URL but a promo/CMMC name that isn't "Certified.../ISACA Advanced|AI"
    for og in ["CCA Certification | CCA Certification",
               "x | Official CMMC Training Role",
               "x | ISACA Named New CAICO for DoW"]:
        assert ex.extract_certification("https://www.isaca.org/credentialing/cca", _page(og=og)) is None
    # a real one still passes
    got = ex.extract_certification("https://www.isaca.org/credentialing/ccoa",
                                   _page(og="CCOA | Certified Cybersecurity Operations Analyst"))
    assert got["name"] == "Certified Cybersecurity Operations Analyst"


def test_comptia_strips_version_and_plus_suffixes():
    got = ex.extract_certification(
        "https://www.comptia.org/en-us/certifications/cybersecurity-analyst/v3",
        _page(og="CySA+ Certification V3 (Retiring Version) | CompTIA"))
    assert got == {"provider_slug": "comptia", "slug": "cybersecurity-analyst", "name": "CySA+"}
    got2 = ex.extract_certification("https://www.comptia.org/en-us/certifications/security",
                                    _page(og="Security+ (Plus) Certification | CompTIA"))
    assert got2["name"] == "Security+"
