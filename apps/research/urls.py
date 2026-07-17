from django.urls import path
from . import views

urlpatterns = [
    path("ingest/", views.ingest_jsonl, name="ingest_jsonl"),
    path("sources/submit/", views.submit_source, name="submit_source"),
    path("report/<str:kind>/<int:pk>/", views.report_outdated, name="report_outdated"),
]
