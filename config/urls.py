from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import TemplateView

from apps.core.sitemaps import StaticSitemap

sitemaps = {"static": StaticSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt",
                                            content_type="text/plain")),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("track/", include("apps.tracker.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("offers/", include("apps.offers.urls")),
    path("api/worker/", include("apps.research.api_urls")),
    path("research/", include("apps.research.urls")),
    path("privacy/", TemplateView.as_view(template_name="legal/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="legal/terms.html"), name="terms"),
]
