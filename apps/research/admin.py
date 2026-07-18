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
    """Review queue for the crawl frontier (D16/SEC-017). Each row carries its crawl
    history: whether a Source already exists for the URL, its status, when it was last
    fetched, and whether it ever yielded facts — so an approver can tell a brand-new page
    from a re-discovery of something already crawled."""
    list_display = ("url", "description", "origin", "depth", "discovered_from",
                    "prior_crawl", "status", "created_at")
    list_filter = ("status", "origin", "depth")
    search_fields = ("url", "description")
    list_select_related = ("discovered_from", "submitted_by")
    readonly_fields = ("prior_crawl", "canonical_url", "discovered_from", "depth",
                       "origin", "created_at")

    actions = ["trigger_crawl"]

    def get_queryset(self, request):
        # Match the existing Source by exact URL or by the submission's canonical URL
        # (the dedupe key) — one subquery per column, no per-row queries.
        from django.db.models import OuterRef, Q, Subquery
        from apps.catalog.models import Source
        match = Source.objects.filter(
            Q(url=OuterRef("url")) | Q(url=OuterRef("canonical_url")))
        return super().get_queryset(request).annotate(
            prior_status=Subquery(match.values("status")[:1]),
            prior_fetched=Subquery(match.values("last_fetched_at")[:1]),
            prior_yield=Subquery(match.values("last_yield_count")[:1]))

    @admin.display(description="Prior crawl")
    def prior_crawl(self, obj):
        """'—' for a never-seen URL; else status + last fetch + historical yield."""
        status = getattr(obj, "prior_status", None)
        if status is None:
            return "—  (new URL)"
        fetched = getattr(obj, "prior_fetched", None)
        parts = [status, f"fetched {fetched:%Y-%m-%d}" if fetched else "never fetched"]
        y = getattr(obj, "prior_yield", None)
        if y:
            parts.append(f"{y} fact(s)")
        return " · ".join(parts)

    @admin.action(description="Trigger crawl (D16: promotes to Source + queues job)")
    def trigger_crawl(self, request, queryset):
        from apps.catalog.models import Source
        already, promoted = 0, 0
        for sub in queryset.filter(status=SourceSubmission.Status.QUEUED):
            # Carry crawl provenance (depth/discovered_from) onto the promoted Source (SEC-017).
            src, created = Source.objects.get_or_create(
                url=sub.url,
                defaults={"submitted_by": sub.submitted_by, "depth": sub.depth,
                          "discovered_from": sub.discovered_from})
            ExtractionJob.objects.create(source=src)
            sub.status = SourceSubmission.Status.CRAWLED
            sub.save(update_fields=["status"])
            promoted += created
            already += (not created)
        if already:
            self.message_user(
                request, f"{already} of {already + promoted} URL(s) already existed as "
                         f"Sources — re-queued for crawl rather than duplicated.",
                level=messages.WARNING)


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
