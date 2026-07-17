from django.contrib import admin
from .models import Provider, Certification, RenewalRule, UpgradePath, CreditRule, Source

admin.site.register(Provider)
admin.site.register(Source)


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "name", "validity_years", "exam_cost_usd")
    list_filter = ("provider",)
    search_fields = ("name",)


@admin.register(RenewalRule)
class RenewalRuleAdmin(admin.ModelAdmin):
    list_display = ("certification", "ceu_required", "cycle_years", "confidence",
                    "last_verified_at", "effective_date")
    list_filter = ("confidence", "certification__provider")


admin.site.register(UpgradePath)
admin.site.register(CreditRule)
