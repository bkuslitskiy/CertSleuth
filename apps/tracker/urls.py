from django.urls import path
from . import views

urlpatterns = [
    path("certs/add/", views.add_cert, name="add_cert"),
    path("activities/add/", views.add_activity, name="add_activity"),
    path("import/credly/", views.credly_import, name="credly_import"),
    path("gmail/scan-request/", views.request_gmail_scan, name="request_gmail_scan"),
    path("calendar/<str:token>.ics", views.ics_feed, name="ics_feed"),
]
