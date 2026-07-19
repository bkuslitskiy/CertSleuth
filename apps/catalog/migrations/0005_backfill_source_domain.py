"""Backfill domain for sources created before the column existed."""
from django.db import migrations


def backfill(apps, schema_editor):
    from urllib.parse import urlparse
    Source = apps.get_model("catalog", "Source")
    batch = []
    for src in Source.objects.filter(domain="").iterator():
        host = (urlparse(src.url).netloc or "").lower().split(":")[0]
        parts = [p for p in host.split(".") if p]
        src.domain = (".".join(parts[-2:]) if len(parts) >= 2 else host)[:120]
        batch.append(src)
        if len(batch) >= 500:
            Source.objects.bulk_update(batch, ["domain"])
            batch = []
    if batch:
        Source.objects.bulk_update(batch, ["domain"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_source_domain")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
