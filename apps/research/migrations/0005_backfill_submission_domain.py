"""Backfill domain for submissions created before the column existed."""
from django.db import migrations


def backfill(apps, schema_editor):
    from urllib.parse import urlparse
    SourceSubmission = apps.get_model("research", "SourceSubmission")
    batch = []
    for sub in SourceSubmission.objects.filter(domain="").iterator():
        host = (urlparse(sub.url).netloc or "").lower().split(":")[0]
        parts = [p for p in host.split(".") if p]
        sub.domain = (".".join(parts[-2:]) if len(parts) >= 2 else host)[:120]
        batch.append(sub)
        if len(batch) >= 500:
            SourceSubmission.objects.bulk_update(batch, ["domain"])
            batch = []
    if batch:
        SourceSubmission.objects.bulk_update(batch, ["domain"])


class Migration(migrations.Migration):
    dependencies = [("research", "0004_sourcesubmission_domain")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
