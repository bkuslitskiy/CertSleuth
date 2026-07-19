from django.urls import path
from . import views

urlpatterns = [
    path("certs/add/", views.add_cert, name="add_cert"),
    path("activities/add/", views.add_activity, name="add_activity"),
    path("import/credly/", views.credly_import, name="credly_import"),
    path("import/<slug:source>/", views.import_source, name="import_source"),
    path("gmail/scan-request/", views.request_gmail_scan, name="request_gmail_scan"),
    path("plan/<int:cert_id>/", views.plan_toggle, name="plan_toggle"),
    path("gmail/run/", views.gmail_scan_run, name="gmail_scan_run"),
    path("gmail/callback/", views.gmail_scan_callback, name="gmail_scan_callback"),
    path("calendar/<str:token>.ics", views.ics_feed, name="ics_feed"),
]
