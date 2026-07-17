"""Worker API + JSONL ingest: lease, submit, validation failure, token auth (SEC-004/005)."""
import json
import pytest
from django.test import Client
from apps.catalog.models import Source
from apps.research.models import ExtractionJob, StagedChange, WorkerToken


@pytest.fixture
def token(db):
    raw, h = WorkerToken.make()
    WorkerToken.objects.create(name="test-worker", token_hash=h)
    return raw


@pytest.fixture
def job(db):
    src = Source.objects.create(url="https://example.com/policy")
    return ExtractionJob.objects.create(source=src)


def test_claim_requires_token(db, job):
    resp = Client().post("/api/worker/jobs/claim")
    assert resp.status_code == 403


def test_claim_and_submit(db, token, job):
    c = Client()
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    claimed = c.post("/api/worker/jobs/claim", **auth).json()["jobs"]
    assert claimed[0]["job_id"] == job.pk
    result = [{"job_id": job.pk, "kind": "certification", "extractor": "claude-code-local",
               "payload": {"provider_slug": "isc2", "slug": "cc", "name": "CC"}}]
    resp = c.post(f"/api/worker/jobs/{job.pk}/result", json.dumps(result),
                  content_type="application/json", **auth)
    assert resp.json()["staged"] == 1
    assert StagedChange.objects.get().status == StagedChange.Status.PENDING  # never auto-published


def test_invalid_payload_422(db, token, job):
    c = Client()
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    c.post("/api/worker/jobs/claim", **auth)
    bad = [{"job_id": job.pk, "kind": "certification", "extractor": "x",
            "payload": {"name": "missing slugs"}}]
    resp = c.post(f"/api/worker/jobs/{job.pk}/result", json.dumps(bad),
                  content_type="application/json", **auth)
    assert resp.status_code == 422
    assert StagedChange.objects.count() == 0
