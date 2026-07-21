"""Backfill for the new eligibility_requirement/source fields:

1. Move ISC2-style experience-requirement text (mis-captured into `level` because there
   was no better field before this migration — see worker/CLAUDE.md and the 2026-07-21
   taxonomy audit) into `eligibility_requirement`, clearing `level` so tier ranking isn't
   asked to judge non-tier text.
2. Populate `source` from the latest approved "certification" StagedChange for each cert
   (matched by provider_slug + slug), so cert pages that already have provenance can show
   it immediately instead of waiting for the next re-crawl to set it going forward.
"""
import re

from django.db import migrations

ELIGIBILITY_TEXT = re.compile(r"required work experience", re.IGNORECASE)


def backfill(apps, schema_editor):
    Certification = apps.get_model("catalog", "Certification")
    StagedChange = apps.get_model("research", "StagedChange")

    moved = []
    for cert in Certification.objects.filter(level__regex=r"(?i)required work experience"):
        if ELIGIBILITY_TEXT.search(cert.level):
            cert.eligibility_requirement = cert.level
            cert.level = ""
            moved.append(cert)
    if moved:
        Certification.objects.bulk_update(moved, ["eligibility_requirement", "level"])

    by_provider_and_slug = {}
    facts = (StagedChange.objects.filter(kind="certification", status="approved")
             .select_related("job__source").order_by("created_at"))
    for sc in facts:
        p = sc.payload
        key = (p.get("provider_slug"), p.get("slug"))
        if key[0] and key[1] and sc.job.source_id:
            by_provider_and_slug[key] = sc.job.source_id  # last approval wins

    sourced = []
    for cert in Certification.objects.select_related("provider").filter(source__isnull=True):
        source_id = by_provider_and_slug.get((cert.provider.slug, cert.slug))
        if source_id:
            cert.source_id = source_id
            sourced.append(cert)
    if sourced:
        Certification.objects.bulk_update(sourced, ["source"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_certification_eligibility_and_source"),
        ("research", "0005_backfill_submission_domain"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
