from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticSitemap(Sitemap):
    """Only publicly reachable pages. The catalog browse is @login_required, so it stays out
    of the sitemap (a crawler would just be bounced to the login form)."""
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return ["dashboard", "privacy", "terms"]  # "dashboard" == "/", the public landing for anon

    def location(self, name):
        return reverse(name)
