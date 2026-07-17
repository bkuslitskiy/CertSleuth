from django.contrib import admin
from .models import ExtractionJob, StagedChange, SourceSubmission, ChangeReport, WorkerToken
from .publish import publish


@admin.register(StagedChange)
class StagedChangeAdmin(admin.ModelAdmin):
    """The review queue (D3). Bulk approve/reject by provider/source for the preload pass (D24)."""
    list_display = ("id", "kind", "extractor", "job", "status", "created_at")
    list_filter = ("status", "kind", "extractor", "job__source")
    actions = ["approve_selected", "reject_selected"]

    @admin.action(description="Approve & publish selected")
    def approve_selected(self, request, queryset):
        for staged in queryset.filter(status=StagedChange.Status.PENDING):
            publish(staged, request.user)

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


@admin.register(WorkerToken)
class WorkerTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "revoked")

    def save_model(self, request, obj, form, change):
        if not change:
            raw, obj.token_hash = WorkerToken.make()
            self.message_user(request, f"Worker token (shown ONCE): {raw}")
        super().save_model(request, obj, form, change)
