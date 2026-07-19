"""Fix auto-created provider metadata: display names (publish title-cased slugs into
names like "Isaca") and CEU currency (browse UI falls back to generic "CEU" without it).
Keyed by slug (D26); providers created after this get correct values at publish/review
time. Reverse restores nothing (the old names were junk)."""
from django.db import migrations

FIXES = {  # slug -> (display name, ceu_currency)
    "isaca": ("ISACA", "CPE"),
    "giac": ("GIAC", "CPE"),
    "isc2": ("ISC2", "CPE"),
    "aws": ("AWS", ""),                       # exam-based, no CEU currency
    "comptia": ("CompTIA", "CEU"),
    "scrum-alliance": ("Scrum Alliance", "SEU"),
    "google-cloud": ("Google Cloud", ""),
    "google-career": ("Google Career Certificates", ""),
    "microsoft": ("Microsoft", ""),           # future-proof: applied if present
}


def apply_fixes(apps, schema_editor):
    Provider = apps.get_model("catalog", "Provider")
    for slug, (name, currency) in FIXES.items():
        Provider.objects.filter(slug=slug).update(name=name, ceu_currency=currency)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_backfill_source_domain")]
    operations = [migrations.RunPython(apply_fixes, migrations.RunPython.noop)]
