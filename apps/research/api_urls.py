from django.urls import path
from . import api

urlpatterns = [
    path("jobs/claim", api.claim, name="worker_claim"),
    path("jobs/<int:job_id>/result", api.submit_result, name="worker_submit"),
]
