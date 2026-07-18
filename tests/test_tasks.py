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


def test_dead_and_needs_render_never_recrawled(db):
    old = timezone.now() - timedelta(days=400)
    Source.objects.create(url="https://example.com/dead", scheduled=True,
                          status=Source.Status.DEAD, last_fetched_at=old)
    Source.objects.create(url="https://example.com/shell", scheduled=True,
                          status=Source.Status.NEEDS_RENDER, last_fetched_at=old)
    queue_due_sources()
    assert ExtractionJob.objects.count() == 0        # parked, never auto-recrawled


def test_barren_uses_long_cadence(db):
    # 30 days old: past active/hub cadence but well within barren's 180d -> not due.
    Source.objects.create(url="https://example.com/barren", scheduled=True,
                          status=Source.Status.BARREN,
                          last_fetched_at=timezone.now() - timedelta(days=30))
    queue_due_sources()
    assert ExtractionJob.objects.count() == 0
