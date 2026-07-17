from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from .models import (ExtractionJob, StagedChange, SourceSubmission, ChangeReport,
                     WorkerToken, GmailScanRequest)
from .publish import publish

# Publish order within a batch: rows that others reference go first (a renewal_rule
# or upgrade_path looks up its Certification by slug at publish time).
PUBLISH_KIND_ORDER = {"certification": 0, "renewal_rule": 1, "credit_rule": 2,
                      "upgrade_path": 3, "free_offer": 4}


@admin.register(StagedChange)
class StagedChangeAdmin(admin.ModelAdmin):
    """The review queue (D3). Bulk approve/reject by provider/source for the preload pass (D24)."""
    list_display = ("id", "kind", "extractor", "job", "status", "created_at")
    list_filter = ("status", "kind", "extractor", "job__source")
    actions = ["approve_selected", "reject_selected"]

    @admin.action(description="Approve & publish selected")
    def approve_selected(self, request, queryset):
        pending = sorted(queryset.filter(status=StagedChange.Status.PENDING),
                         key=lambda s: (PUBLISH_KIND_ORDER.get(s.kind, 9), s.pk))
        published, failed = 0, 0
        for staged in pending:
            try:
                publish(staged, request.user)
                published += 1
            except ObjectDoesNotExist as e:
                failed += 1
                self.message_user(request, f"#{staged.pk} ({staged.kind}) left pending: {e}",
                                  level=messages.ERROR)
        if published:
            self.message_user(request, f"Published {published} change(s).", level=messages.SUCCESS)
        if failed:
            self.message_user(request, f"{failed} change(s) reference a missing catalog row; "
                              "publish their certifications first.", level=messages.WARNING)

    @admin.action(description="Reject selected")
    def reject_selected(self, request, queryset):
        queryset.update(status=StagedChange.Status.REJECTED, reviewed_by=request.user)


@admin.register(ExtractionJob)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "status", "leased_by", "created_at", "completed_at")
    list_filter = ("status",)


@admin.register(SourceSubmission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("url", "description", "submitted_by", "status", "created_at")
    actions = ["trigger_crawl"]

    @admin.action(description="Trigger crawl (D16: promotes to Source + queues job)")
    def trigger_crawl(self, request, queryset):
        from apps.catalog.models import Source
        for sub in queryset.filter(status=SourceSubmission.Status.QUEUED):
            src, _ = Source.objects.get_or_create(url=sub.url,
                                                  defaults={"submitted_by": sub.submitted_by})
            ExtractionJob.objects.create(source=src)
            sub.status = SourceSubmission.Status.CRAWLED
            sub.save(update_fields=["status"])


admin.site.register(ChangeReport)


@admin.register(GmailScanRequest)
class GmailScanRequestAdmin(admin.ModelAdmin):
    """SEC-013 spend gate: scans run only after an approver approves here."""
    list_display = ("user", "status", "created_at", "resolved_by", "resolved_at")
    list_filter = ("status",)
    actions = ["approve_selected", "deny_selected"]

    def _resolve(self, request, queryset, status):
        n = queryset.filter(status=GmailScanRequest.Status.PENDING).update(
            status=status, resolved_by=request.user, resolved_at=timezone.now())
        return n

    @admin.action(description="Approve selected scans")
    def approve_selected(self, request, queryset):
        n = self._resolve(request, queryset, GmailScanRequest.Status.APPROVED)
        self.message_user(request, f"Approved {n} scan(s). Execution runs once "
                          "apps/tracker/gmail.py lands (OAuth creds required).")

    @admin.action(description="Deny selected scans")
    def deny_selected(self, request, queryset):
        n = self._resolve(request, queryset, GmailScanRequest.Status.DENIED)
        self.message_user(request, f"Denied {n} scan(s).")


@admin.register(WorkerToken)
class WorkerTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "revoked")

    def save_model(self, request, obj, form, change):
        if not change:
            raw, obj.token_hash = WorkerToken.make()
            self.message_user(request, f"Worker token (shown ONCE): {raw}")
        super().save_model(request, obj, form, change)
