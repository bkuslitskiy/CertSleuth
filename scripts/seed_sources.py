"""Load scripts/seeds/sources.json into Source + queue ExtractionJobs for preload.
Run: python manage.py shell < scripts/seed_sources.py  (or convert to a mgmt command)"""
import json
from pathlib import Path
from apps.catalog.models import Source
from apps.research.models import ExtractionJob

data = json.loads(Path("scripts/seeds/sources.json").read_text())
created = 0
for entry in data["sources"]:
    for url in entry["urls"]:
        src, was_new = Source.objects.get_or_create(
            url=url, defaults={"cadence_days": entry["cadence_days"], "scheduled": True})
        if was_new:
            ExtractionJob.objects.create(source=src)
            created += 1
print(f"seeded, {created} jobs queued")
