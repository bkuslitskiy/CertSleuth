import secrets
from django.conf import settings
from django.db import models


class ExtractionJob(models.Model):
    """The queue both ingest modes feed from (spec 3.5). Lease with TTL; expired -> requeued."""
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        LEASED = "leased", "Leased"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    source = models.ForeignKey("catalog.Source", on_delete=models.CASCADE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    leased_by = models.CharField(max_length=80, blank=True)      # extractor identity
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    snapshot_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Job {self.pk} [{self.get_status_display()}] {self.source.url}"


class WorkerToken(models.Model):
    """SEC-004: per-worker token, scoped to claim/submit only. Store hash, never the token."""
    name = models.CharField(max_length=80, unique=True)
    token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}{' (revoked)' if self.revoked else ''}"

    @staticmethod
    def make():
        import hashlib
        raw = secrets.token_urlsafe(32)
        return raw, hashlib.sha256(raw.encode()).hexdigest()


class StagedChange(models.Model):
    """SEC-005: everything an extractor produces lands here. Human approval publishes."""
    class Kind(models.TextChoices):
        RENEWAL_RULE = "renewal_rule", "Renewal rule"
        UPGRADE_PATH = "upgrade_path", "Upgrade path"
        CREDIT_RULE = "credit_rule", "Credit rule"
        FREE_OFFER = "free_offer", "Free offer"
        CERTIFICATION = "certification", "Certification"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    job = models.ForeignKey(ExtractionJob, on_delete=models.CASCADE, related_name="staged")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    payload = models.JSONField()                 # schema-validated on ingest
    extractor = models.CharField(max_length=80)  # claude-code-local | api-haiku | local-<model>
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        label = (self.payload.get("name") or self.payload.get("certification_name")
                 or self.payload.get("title") or self.payload.get("from_certification_slug", ""))
        return f"#{self.pk} {self.get_kind_display()}: {label}"


class SourceSubmission(models.Model):
    """D16: inert until an Approver triggers the crawl. Untrusted users can't cause spend."""
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued (inert)"
        # value stays 'crawled' (no migration); label says what actually happened —
        # promotion to the Source registry + a queued ExtractionJob, not a finished crawl
        CRAWLED = "crawled", "Promoted — extraction job queued"
        REJECTED = "rejected", "Rejected"

    url = models.URLField(max_length=500)
    description = models.CharField(max_length=300)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description or self.url


class ChangeReport(models.Model):
    """'Report outdated' on any fact. N open reports on one target -> disputed badge."""
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        VERIFIED = "verified", "Verified & fixed"
        REJECTED = "rejected", "Rejected"

    target_kind = models.CharField(max_length=30)   # model label
    target_id = models.BigIntegerField()            # numeric PK (D26)
    note = models.CharField(max_length=500, blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_status_display()}: {self.target_kind} #{self.target_id}"
