"""Worker API (SEC-004): pull-only, token-authed, writes only to staging (SEC-005)."""
import hashlib
import json
from datetime import timedelta
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError
from .models import ExtractionJob, StagedChange, WorkerToken
from .schemas import ExtractionResult

LEASE_MINUTES = 30


def _auth(request):
    raw = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not raw:
        return None
    h = hashlib.sha256(raw.encode()).hexdigest()
    return WorkerToken.objects.filter(token_hash=h, revoked=False).first()


@csrf_exempt
@require_POST
def claim(request):
    tok = _auth(request)
    if not tok:
        return HttpResponseForbidden()
    n = min(int(request.GET.get("n", 5)), 25)
    now = timezone.now()
    # requeue expired leases
    ExtractionJob.objects.filter(status=ExtractionJob.Status.LEASED,
                                 lease_expires_at__lt=now).update(
        status=ExtractionJob.Status.QUEUED, leased_by="")
    jobs = list(ExtractionJob.objects.select_for_update(skip_locked=True)
                .filter(status=ExtractionJob.Status.QUEUED)[:n]) if _pg() else \
           list(ExtractionJob.objects.filter(status=ExtractionJob.Status.QUEUED)[:n])
    out = []
    for j in jobs:
        j.status = ExtractionJob.Status.LEASED
        j.leased_by = tok.name
        j.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
        j.save(update_fields=["status", "leased_by", "lease_expires_at"])
        # Prior validators let the worker send a conditional GET (skip unchanged pages).
        out.append({"job_id": j.pk, "source_url": j.source.url,
                    "etag": j.source.etag, "last_modified": j.source.http_last_modified})
    return JsonResponse({"jobs": out})


def _pg():
    from django.db import connection
    return connection.vendor == "postgresql"


@csrf_exempt
@require_POST
def submit_result(request, job_id: int):
    tok = _auth(request)
    if not tok:
        return HttpResponseForbidden()
    try:
        job = ExtractionJob.objects.get(pk=job_id, leased_by=tok.name)
    except ExtractionJob.DoesNotExist:
        return JsonResponse({"error": "unknown or unleased job"}, status=404)
    try:
        body = json.loads(request.body)
        results = body if isinstance(body, list) else [body]
        staged = 0
        for r in results:
            res = ExtractionResult(**{**r, "job_id": job.pk})
            StagedChange.objects.create(job=job, kind=res.kind,
                                        payload=res.validated_payload(),
                                        extractor=res.extractor)
            staged += 1
    except (json.JSONDecodeError, ValidationError) as e:
        return JsonResponse({"error": str(e)}, status=422)
    job.status = ExtractionJob.Status.DONE
    job.completed_at = timezone.now()
    job.snapshot_hash = results[0].get("snapshot_hash", "") if results else ""
    job.save(update_fields=["status", "completed_at", "snapshot_hash"])
    return JsonResponse({"staged": staged})
