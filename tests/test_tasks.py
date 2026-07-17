from datetime import timedelta
from django.utils import timezone
from apps.catalog.models import Source
from apps.research.models import ExtractionJob
from apps.research.tasks import queue_due_sources


def test_due_source_queued_once(db):
    src = Source.objects.create(url="https://example.com/x", scheduled=True,
                                cadence_days=7,
                                last_fetched_at=timezone.now() - timedelta(days=8))
    queue_due_sources()
    queue_due_sources()  # idempotent while job open
    assert ExtractionJob.objects.filter(source=src).count() == 1


def test_fresh_source_not_queued(db):
    Source.objects.create(url="https://example.com/y", scheduled=True, cadence_days=7,
                          last_fetched_at=timezone.now() - timedelta(days=1))
    queue_due_sources()
    assert ExtractionJob.objects.count() == 0
