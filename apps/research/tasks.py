"""django-q scheduled tasks. Register with: python manage.py setup_schedules"""
from datetime import timedelta
from django.utils import timezone


def queue_due_sources():
    """Re-crawl cadence (spec 3.5, SEC-017): scheduled sources past their status-based
    cadence get a job, unless one is already open. Community submissions never enter here
    (D16). dead/needs_render pages are never auto-recrawled (a fixed URL / headless path
    is a manual action); active/hub/barren recrawl on their tiered cadence and don't
    refresh recency until they actually yield."""
    from apps.catalog.models import Source
    from .models import ExtractionJob
    now = timezone.now()
    recrawlable = [Source.Status.ACTIVE, Source.Status.HUB, Source.Status.BARREN]
    queued = 0
    for src in Source.objects.filter(scheduled=True, status__in=recrawlable):
        cadence = Source.CADENCE_BY_STATUS.get(src.status, src.cadence_days)
        if src.last_fetched_at and src.last_fetched_at > now - timedelta(days=cadence):
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
