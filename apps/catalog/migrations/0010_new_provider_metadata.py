"""Pre-create the incoming providers with correct display names + CEU currency, so
publish's get_or_create finds them instead of title-casing slugs ("Pmi", "Asq").
Idempotent: updates name/currency if a row already exists (D26: keyed by slug)."""
from django.db import migrations

PROVIDERS = {  # slug -> (display name, ceu_currency)
    "pmi": ("PMI", "PDU"),
    "adobe": ("Adobe", ""),
    "scrum-org": ("Scrum.org", ""),
    "icagile": ("ICAgile", ""),
    "oracle": ("Oracle", ""),
    "peoplecert": ("PeopleCert", "CPD"),
    "asq": ("ASQ", "RU"),
    "eccouncil": ("EC-Council", "ECE"),
    "iapp": ("IAPP", "CPE"),
    "redhat": ("Red Hat", ""),
    "cncf": ("CNCF", ""),
    "linux-foundation": ("Linux Foundation", ""),
    "hashicorp": ("HashiCorp", ""),
    "salesforce": ("Salesforce", ""),
    "cwnp": ("CWNP", ""),
    "paloalto": ("Palo Alto Networks", ""),
    "ibm": ("IBM", ""),
    "fortinet": ("Fortinet", ""),
    "hubspot": ("HubSpot", ""),
    "moz": ("Moz", ""),
    "google-skillshop": ("Google Skillshop", ""),
    "tableau": ("Tableau", ""),
    "cisco": ("Cisco", "CE"),
}


def apply_providers(apps, schema_editor):
    Provider = apps.get_model("catalog", "Provider")
    for slug, (name, currency) in PROVIDERS.items():
        obj, created = Provider.objects.get_or_create(
            slug=slug, defaults={"name": name, "ceu_currency": currency})
        if not created and (obj.name != name or obj.ceu_currency != currency):
            obj.name, obj.ceu_currency = name, currency
            obj.save()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0009_backfill_abbreviations")]
    operations = [migrations.RunPython(apply_providers, migrations.RunPython.noop)]
