from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
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
