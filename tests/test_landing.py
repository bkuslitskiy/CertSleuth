"""Public landing, waitlist capture, root routing, and SEO surfaces.

The gap these cover: before this, "/" was @login_required, so an anonymous visitor was
bounced to a bare login form — no providers, no copy, no waitlist, no meta description.
"""
import pytest
from django.urls import reverse

from apps.accounts.models import WaitlistEntry
from apps.catalog.models import Certification, Provider

pytestmark = pytest.mark.django_db

DESC = "Track your IT, security, tech, and product management certifications."


def _provider_with_cert(name="Scrum Alliance", slug="scrum-alliance"):
    p = Provider.objects.create(name=name, slug=slug)
    Certification.objects.create(provider=p, name="CSM", slug="csm")
    return p


# --- routing ---------------------------------------------------------------------------

def test_anonymous_root_renders_landing_not_login(client):
    resp = client.get("/")
    assert resp.status_code == 200                      # not a 302 to /accounts/login/
    assert b"Join the waitlist" in resp.content
    assert DESC.encode() in resp.content                # the descriptive copy + meta


def test_authenticated_root_renders_dashboard(client, user):
    client.force_login(user)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Your certifications" in resp.content       # dashboard h1, not the landing


# --- providers on the landing ----------------------------------------------------------

def test_landing_lists_providers(client):
    _provider_with_cert()
    resp = client.get("/")
    assert b"Scrum Alliance" in resp.content
    assert b"1 certification" in resp.content


def test_landing_handles_empty_catalog(client):
    resp = client.get("/")                              # no providers seeded (like prod)
    assert resp.status_code == 200
    assert b"building out the catalog" in resp.content


# --- waitlist capture ------------------------------------------------------------------

def test_waitlist_post_creates_normalized_entry(client):
    resp = client.post("/", {"email": "  New.User@Example.COM "})
    assert resp.status_code == 302
    assert resp.headers["Location"] == reverse("dashboard")
    assert WaitlistEntry.objects.filter(email="new.user@example.com").exists()


def test_waitlist_dedupes_on_case_and_whitespace(client):
    client.post("/", {"email": "dup@example.com"})
    client.post("/", {"email": "DUP@example.com "})
    assert WaitlistEntry.objects.filter(email="dup@example.com").count() == 1


def test_waitlist_rejects_bad_email(client):
    resp = client.post("/", {"email": "not-an-email"})
    assert resp.status_code == 200                      # re-renders landing, no redirect
    assert WaitlistEntry.objects.count() == 0


# --- SEO surfaces ----------------------------------------------------------------------

def test_robots_txt_served(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/plain")
    assert b"Sitemap:" in resp.content
    assert b"Disallow: /admin/" in resp.content


def test_sitemap_xml_lists_public_pages(client):
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert b"<urlset" in resp.content
    assert b"/privacy/" in resp.content
