from django.urls import path
from . import views

urlpatterns = [
    path("", views.provider_list, name="catalog_providers"),
    path("<slug:provider_slug>/", views.provider_detail, name="catalog_provider"),
    path("<slug:provider_slug>/<slug:cert_slug>/", views.cert_detail, name="catalog_cert"),
]
