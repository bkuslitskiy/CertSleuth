"""Worker API (SEC-004): pull-only, token-authed, writes only to staging (SEC-005)."""
import hashlib
import json
from datetime import timedelta
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError
from . import discovery
from .models import ExtractionJob, StagedChange, WorkerToken
from .schemas import ExtractionResult

# Lease = crash recovery, not recrawl cadence (that's Source.CADENCE_BY_STATUS, 7-365
# days). Operator extraction legitimately takes hours between fetch and submit; the old
# 30-minute lease expired mid-session and the requeued jobs then starved never-claimed
# ones (claim ordered by pk, and requeues have lower pks). 24h covers a working session
# while still freeing genuinely-abandoned jobs by the next day's run.
LEASE_MINUTES = 60 * 24


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
    try:
        n = int(request.GET.get("n", 5))
    except (TypeError, ValueError):
        n = 5
    n = max(1, min(n, 25))  # clamp: a bad/negative ?n can't 500 or invert the slice
    now = timezone.now()
    # requeue expired leases
    ExtractionJob.objects.filter(status=ExtractionJob.Status.LEASED,
                                 lease_expires_at__lt=now).update(
        status=ExtractionJob.Status.QUEUED, leased_by="")
    # Never-leased jobs first (lease_expires_at is NULL until first lease), then
    # expired-lease requeues — so churn on old jobs can't starve fresh ones. Within each
    # tier, interleave across source domains: a claim batch alternates between sites
    # instead of hammering one (the worker's politeness delay then spaces out same-domain
    # hits by a full round). Window of n*10 candidates keeps the query bounded.
    from django.db.models import F
    fresh_first = (F("lease_expires_at").asc(nulls_first=True), "pk")
    base = (ExtractionJob.objects.filter(status=ExtractionJob.Status.QUEUED)
            .order_by(*fresh_first).select_related("source"))
    window = max(n * 10, 100)
    cand = list(base.select_for_update(skip_locked=True, of=("self",))[:window]) if _pg() \
        else list(base[:window])
    fresh = [j for j in cand if j.lease_expires_at is None]
    retry = [j for j in cand if j.lease_expires_at is not None]
    jobs = (_interleave_by_domain(fresh) + _interleave_by_domain(retry))[:n]
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


def _interleave_by_domain(jobs):
    """Round-robin jobs across their source domains, preserving arrival order within a
    domain and first-seen order across domains."""
    from collections import defaultdict, deque
    queues, order = defaultdict(deque), []
    for j in jobs:
        d = j.source.domain
        if d not in queues:
            order.append(d)
        queues[d].append(j)
    out = []
    while len(out) < len(jobs):
        for d in order:
            if queues[d]:
                out.append(queues[d].popleft())
    return out


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
    # Facts staged -> the source is 'active' on the normal cadence (SEC-017); overrides
    # any hub/barren set by the fetch report.
    if staged:
        src = job.source
        src.status = src.Status.ACTIVE
        src.cadence_days = src.CADENCE_BY_STATUS["active"]
        src.last_yield_count = staged
        src.last_yield_at = timezone.now()
        src.save(update_fields=["status", "cadence_days", "last_yield_count", "last_yield_at"])
    return JsonResponse({"staged": staged})


@csrf_exempt
@require_POST
def fetch_report(request, job_id: int):
    """SEC-017: the worker reports fetch metadata + same-domain discovered links (no raw
    HTML). We classify the source for cadence and enqueue links as inert submissions."""
    tok = _auth(request)
    if not tok:
        return HttpResponseForbidden()
    try:
        job = ExtractionJob.objects.get(pk=job_id, leased_by=tok.name)
    except ExtractionJob.DoesNotExist:
        return JsonResponse({"error": "unknown or unleased job"}, status=404)
    try:
        report = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({"error": str(e)}, status=422)
    status, queued = discovery.apply_fetch_report(job.source, report)
    return JsonResponse({"status": status, "queued": queued})
