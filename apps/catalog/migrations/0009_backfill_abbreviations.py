"""Backfill certification abbreviations where derivable without guessing:

1. A parenthesized short form in the name is the provider's own abbreviation —
   "GIAC Strategic OSINT Analyst (GSOA)" -> GSOA.
2. For providers whose slugs ARE the industry short form (ISACA cism, ISC2 cissp,
   Scrum Alliance a-csm, PMI capm), uppercase the slug when it's short and letterish.
3. CompTIA-style names that are already the short form ("Security+") copy the name.

Anything else stays blank — extraction fills the rest from provider pages over time.
"""
import re

from django.db import migrations

PAREN = re.compile(r"\(([A-Z][A-Za-z0-9|/+\- ]{1,15})\)")
SLUG_IS_ABBREV = {"isaca", "isc2", "scrum-alliance", "pmi"}
SHORT_NAME = re.compile(r"^[A-Za-z]{1,10}\+$")          # Security+, CySA+ ...


def backfill(apps, schema_editor):
    Certification = apps.get_model("catalog", "Certification")
    batch = []
    for cert in Certification.objects.select_related("provider").filter(abbreviation=""):
        abbrev = ""
        m = PAREN.search(cert.name)
        if m:
            abbrev = m.group(1).strip()
        elif SHORT_NAME.match(cert.name):
            abbrev = cert.name
        elif (cert.provider.slug in SLUG_IS_ABBREV and len(cert.slug) <= 7
              and re.fullmatch(r"[a-z]+(-[a-z0-9]+)?", cert.slug)):
            abbrev = cert.slug.upper().replace("-", "-")
        if abbrev:
            cert.abbreviation = abbrev[:40]
            batch.append(cert)
    if batch:
        Certification.objects.bulk_update(batch, ["abbreviation"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0008_certification_abbreviation")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
