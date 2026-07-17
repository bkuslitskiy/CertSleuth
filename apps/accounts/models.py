from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets


class Role(models.TextChoices):
    USER = "user", "User"
    APPROVER = "approver", "Approver"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    """D26: BigAutoField numeric PK (project default). Email is the login identity."""
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.USER)
    timezone = models.CharField(max_length=64, default="America/New_York")  # D27
    # D25: Gmail scan unlocks only after manual console enrollment is confirmed by an admin
    gmail_scan_enabled = models.BooleanField(default=False)
    ics_token = models.CharField(max_length=64, unique=True, blank=True)  # tokenized calendar feed

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def save(self, *args, **kwargs):
        if not self.ics_token:
            self.ics_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_approver(self):
        return self.role in (Role.APPROVER, Role.ADMIN)


class RegistrationMode(models.Model):
    """Singleton toggle (D1): invite-only vs open; waitlist past WAITLIST_THRESHOLD."""
    open_registration = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Invite(models.Model):
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)


class WaitlistEntry(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EnrollmentTask(models.Model):
    """D25: pending Google-console test-user additions. Console has no API; this is the
    copy-paste queue. Marking done flips user.gmail_scan_enabled."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending console add"
        DONE = "done", "Enrolled"
        DECLINED = "declined", "Declined"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    gmail_address = models.EmailField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
