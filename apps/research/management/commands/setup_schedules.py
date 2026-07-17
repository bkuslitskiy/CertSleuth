from django.core.management.base import BaseCommand
from django_q.models import Schedule


TASKS = [
    ("apps.research.tasks.queue_due_sources", Schedule.DAILY),
    ("apps.research.tasks.expire_offers", Schedule.DAILY),
    ("apps.research.tasks.notify_expiring_certs", Schedule.DAILY),
]


class Command(BaseCommand):
    help = "Register django-q schedules (idempotent)"

    def handle(self, *args, **opts):
        for func, cadence in TASKS:
            _, created = Schedule.objects.get_or_create(
                func=func, defaults={"schedule_type": cadence})
            self.stdout.write(f"{func}: {'created' if created else 'exists'}")
