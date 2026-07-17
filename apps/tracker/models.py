from django.conf import settings
from django.db import models
from apps.core.crypto import EncryptedCharField


class UserCertification(models.Model):
    """D7: cert number + external evidence link, no documents. Trusted as genuine (SEC-002)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certs")
    certification = models.ForeignKey("catalog.Certification", on_delete=models.PROTECT)
    earned_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    cert_number = EncryptedCharField(max_length=500, blank=True)  # SEC-009: ciphertext at rest
    evidence_url = models.URLField(blank=True, max_length=500)
    import_source = models.CharField(max_length=40, default="manual")  # manual|credly|badge|upload|gmail|linkedin_csv

    class Meta:
        unique_together = [("user", "certification")]

    def __str__(self):
        return f"{self.user.email}: {self.certification}"


class UserGoal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals")
    certification = models.ForeignKey("catalog.Certification", on_delete=models.PROTECT)
    target_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} → {self.certification}"


class Activity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    title = models.CharField(max_length=250)
    kind = models.CharField(max_length=40, default="course")  # matches CreditRule.activity_kinds
    date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    evidence_url = models.URLField(blank=True, max_length=500)

    class Meta:
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.title} ({self.hours}h, {self.date})"


class CreditMapping(models.Model):
    """One activity -> N provider submissions. The cross-crediting ledger."""
    class SubmissionStatus(models.TextChoices):
        UNSUBMITTED = "unsubmitted", "Not yet submitted"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="mappings")
    provider = models.ForeignKey("catalog.Provider", on_delete=models.CASCADE)
    category = models.CharField(max_length=80, blank=True)
    credits = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=16, choices=SubmissionStatus.choices,
                              default=SubmissionStatus.UNSUBMITTED)

    def __str__(self):
        return f"{self.activity.title} → {self.provider.name}: {self.credits} ({self.get_status_display()})"
