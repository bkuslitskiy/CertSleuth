from django.conf import settings
from django.db import models


class FreeOffer(models.Model):
    """D12: all tiers submit; Approver+ submissions prioritized in review."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REJECTED = "rejected", "Rejected"

    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    url = models.URLField(max_length=500)
    provider = models.ForeignKey("catalog.Provider", null=True, blank=True, on_delete=models.SET_NULL)
    starts = models.DateField(null=True, blank=True)
    ends = models.DateField(null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    priority = models.BooleanField(default=False)  # True when submitter was Approver+
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
