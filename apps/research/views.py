"""Batch JSONL ingest (mode 2) + source submission + report-outdated."""
import json
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django import forms
from pydantic import ValidationError
from .models import ExtractionJob, StagedChange, SourceSubmission, ChangeReport
from .schemas import ExtractionResult


class JSONLUploadForm(forms.Form):
    results = forms.FileField(help_text="results.jsonl produced offline against schema v1")


@staff_member_required
def ingest_jsonl(request):
    """Preload path: offline Claude Code output -> same validation -> same staging queue."""
    form = JSONLUploadForm(request.POST or None, request.FILES or None)
    report = None
    if request.method == "POST" and form.is_valid():
        ok, errors = 0, []
        for i, line in enumerate(request.FILES["results"].read().decode().splitlines(), 1):
            if not line.strip():
                continue
            try:
                res = ExtractionResult(**json.loads(line))
                job = ExtractionJob.objects.get(pk=res.job_id)
                StagedChange.objects.create(job=job, kind=res.kind,
                                            payload=res.validated_payload(),
                                            extractor=res.extractor)
                ok += 1
            except (json.JSONDecodeError, ValidationError, ExtractionJob.DoesNotExist) as e:
                errors.append(f"line {i}: {e}")
        report = {"staged": ok, "errors": errors[:50]}
    return render(request, "dashboard/ingest.html", {"form": form, "report": report})


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = SourceSubmission
        fields = ("url", "description")


@login_required
def submit_source(request):
    form = SubmissionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sub = form.save(commit=False)
        sub.submitted_by = request.user
        sub.save()
        messages.success(request, "Source queued for curator review. Nothing is fetched "
                                  "until an approver triggers it.")
        return redirect("dashboard")
    return render(request, "dashboard/submit_source.html", {"form": form})


def _requeue_source(kind, pk):
    """Spec 3.6: a report bumps the fact's source straight back into the job queue."""
    from apps.catalog.models import RenewalRule, UpgradePath, CreditRule
    model = {"renewal_rule": RenewalRule, "upgrade_path": UpgradePath,
             "credit_rule": CreditRule}.get(kind)
    if not model:
        return
    obj = model.objects.filter(pk=pk).select_related("source").first()
    if obj and obj.source and not ExtractionJob.objects.filter(
            source=obj.source, status__in=["queued", "leased"]).exists():
        ExtractionJob.objects.create(source=obj.source)


@login_required
def report_outdated(request, kind, pk):
    if request.method == "POST":
        ChangeReport.objects.create(target_kind=kind, target_id=pk,
                                    note=request.POST.get("note", "")[:500],
                                    reported_by=request.user)
        _requeue_source(kind, pk)
        messages.success(request, "Reported. The fact is flagged and its source re-queued.")
    return redirect(request.META.get("HTTP_REFERER", "/"))
