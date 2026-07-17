from django.contrib import admin
from django.utils import timezone
from .models import FreeOffer


@admin.register(FreeOffer)
class FreeOfferAdmin(admin.ModelAdmin):
    list_display = ("title", "provider", "priority", "status", "ends", "submitted_by")
    list_filter = ("status", "priority", "provider")
    ordering = ("-priority", "-created_at")
    actions = ["approve", "reject"]

    @admin.action(description="Approve -> active")
    def approve(self, request, queryset):
        queryset.update(status=FreeOffer.Status.ACTIVE, last_verified_at=timezone.now())

    @admin.action(description="Reject")
    def reject(self, request, queryset):
        queryset.update(status=FreeOffer.Status.REJECTED)
