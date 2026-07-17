"""django-q scheduled tasks. Register with: python manage.py setup_schedules"""
from datetime import timedelta
from django.utils import timezone


def queue_due_sources():
    """Re-crawl cadence (spec 3.5): scheduled sources past their cadence get a job,
    unless one is already open. Community submissions never enter here (D16)."""
    from apps.catalog.models import Source
    from .models import ExtractionJob
    now = timezone.now()
    queued = 0
    for src in Source.objects.filter(scheduled=True):
        if src.last_fetched_at and src.last_fetched_at > now - timedelta(days=src.cadence_days):
            continue
        if ExtractionJob.objects.filter(source=src, status__in=["queued", "leased"]).exists():
            continue
        ExtractionJob.objects.create(source=src)
        queued += 1
    return f"queued {queued}"


def expire_offers():
    from apps.offers.models import FreeOffer
    n = (FreeOffer.objects.filter(status=FreeOffer.Status.ACTIVE, ends__lt=timezone.now().date())
         .update(status=FreeOffer.Status.EXPIRED))
    return f"expired {n}"


def notify_expiring_certs():
    """D5 email reminders at 90/30/7 days out. Idempotent per day via exact-day match."""
    from django.core.mail import send_mail
    from django.conf import settings
    from apps.tracker.models import UserCertification
    today = timezone.now().date()
    sent = 0
    for days in (90, 30, 7):
        target = today + timedelta(days=days)
        for uc in (UserCertification.objects.filter(expiry_date=target)
                   .select_related("user", "certification")):
            send_mail(
                subject=f"{uc.certification} expires in {days} days",
                message=(f"Your {uc.certification} expires on {uc.expiry_date}.\n"
                         f"Track renewal progress: https://certsleuth.com/\n"),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[uc.user.email], fail_silently=True)
            sent += 1
    return f"sent {sent}"
