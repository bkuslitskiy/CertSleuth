"""Claim ordering: never-claimed jobs must not be starved by expired-lease requeues.

Observed in the 2026-07-18 promoted-queue crawl: expired 30-minute leases requeued old
jobs (lower pks), claim ordered by pk, and 187 never-claimed sources — including the
CompTIA CE pages the crawl existed for — were still unfetched when the batch cap hit.
"""
import hashlib
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.catalog.models import Source
from apps.research.models import ExtractionJob, WorkerToken

pytestmark = pytest.mark.django_db

RAW = "test-token"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {RAW}"}


@pytest.fixture
def token(db):
    return WorkerToken.objects.create(
        name="w", token_hash=hashlib.sha256(RAW.encode()).hexdigest())


def _job(url, leased_ago_minutes=None):
    src = Source.objects.create(url=url)
    job = ExtractionJob.objects.create(source=src)
    if leased_ago_minutes is not None:
        # simulate a previously-leased job whose lease expired (organic requeue keeps
        # the stale lease_expires_at — that's the previously-leased marker)
        job.status = ExtractionJob.Status.LEASED
        job.leased_by = "w"
        job.lease_expires_at = timezone.now() - timedelta(minutes=leased_ago_minutes)
        job.save()
    return job


def test_fresh_jobs_claim_before_expired_requeues(token):
    old = _job("https://ex.test/old-expired", leased_ago_minutes=10)   # lower pk, expired
    fresh = _job("https://ex.test/never-claimed")                      # higher pk, never leased
    got = Client().post("/api/worker/jobs/claim?n=1", **AUTH).json()["jobs"]
    assert got[0]["job_id"] == fresh.pk        # fresh wins despite higher pk
    got2 = Client().post("/api/worker/jobs/claim?n=1", **AUTH).json()["jobs"]
    assert got2[0]["job_id"] == old.pk         # expired requeue claims next, not never


def test_expired_lease_requeues_and_is_claimable(token):
    old = _job("https://ex.test/expired", leased_ago_minutes=5)
    got = Client().post("/api/worker/jobs/claim?n=5", **AUTH).json()["jobs"]
    assert [j["job_id"] for j in got] == [old.pk]


def test_lease_is_a_day_not_half_an_hour(token):
    from apps.research.api import LEASE_MINUTES
    assert LEASE_MINUTES == 60 * 24
    _job("https://ex.test/a")
    Client().post("/api/worker/jobs/claim?n=1", **AUTH)
    job = ExtractionJob.objects.get()
    remaining = job.lease_expires_at - timezone.now()
    assert remaining > timedelta(hours=23)
