from django.contrib import admin
from django.utils import timezone
from .models import User, Invite, RegistrationMode, WaitlistEntry, EnrollmentTask


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "role", "gmail_scan_enabled", "is_active", "date_joined")
    list_filter = ("role", "gmail_scan_enabled", "is_active")
    search_fields = ("email",)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("email", "invited_by", "created_at", "accepted_at")


admin.site.register(RegistrationMode)
admin.site.register(WaitlistEntry)


@admin.register(EnrollmentTask)
class EnrollmentTaskAdmin(admin.ModelAdmin):
    """The D25 console queue: copy addresses, paste into Google console, mark done."""
    list_display = ("gmail_address", "user", "status", "created_at")
    list_filter = ("status",)
    actions = ["mark_enrolled", "copy_batch"]

    @admin.action(description="Mark enrolled (after console paste) — unlocks scan")
    def mark_enrolled(self, request, queryset):
        for task in queryset:
            task.status = EnrollmentTask.Status.DONE
            task.resolved_at = timezone.now()
            task.save(update_fields=["status", "resolved_at"])
            task.user.gmail_scan_enabled = True
            task.user.save(update_fields=["gmail_scan_enabled"])

    @admin.action(description="Show comma-separated batch for console paste")
    def copy_batch(self, request, queryset):
        batch = ", ".join(queryset.values_list("gmail_address", flat=True))
        self.message_user(request, f"Paste into Google console → Audience → Test users: {batch}")
