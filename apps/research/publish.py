"""Approval -> canonical publication. Called from admin action. Versioning per spec §2."""
from django.utils import timezone
from apps.catalog.models import Provider, Certification, RenewalRule, UpgradePath
from apps.offers.models import FreeOffer


def publish(staged, reviewer):
    p = staged.payload
    if staged.kind == "certification":
        provider, _ = Provider.objects.get_or_create(slug=p["provider_slug"],
                                                     defaults={"name": p["provider_slug"].title()})
        Certification.objects.update_or_create(
            provider=provider, slug=p["slug"],
            defaults={"name": p["name"], "level": p.get("level", ""),
                      "exam_cost_usd": p.get("exam_cost_usd"),
                      "validity_years": p.get("validity_years"),
                      "external_ids": p.get("external_ids", {})})
    elif staged.kind == "renewal_rule":
        cert = Certification.objects.get(provider__slug=p["provider_slug"],
                                         slug=p["certification_slug"])
        old = cert.current_rule
        new = RenewalRule.objects.create(
            certification=cert, ceu_required=p.get("ceu_required"),
            ceu_categories=p.get("ceu_categories", {}), annual_fee_usd=p.get("annual_fee_usd"),
            renewal_fee_usd=p.get("renewal_fee_usd"),
            cycle_years=p.get("cycle_years"), grace_period_days=p.get("grace_period_days"),
            effective_date=p.get("effective_date"), source=staged.job.source,
            confidence=p.get("confidence", "commonly_accepted"),
            last_verified_at=timezone.now())
        if old and old.pk != new.pk:
            old.superseded_by = new
            old.save(update_fields=["superseded_by"])
    elif staged.kind == "upgrade_path":
        from_c = Certification.objects.get(provider__slug=p["provider_slug"],
                                           slug=p["from_certification_slug"])
        to_c = Certification.objects.get(provider__slug=p["provider_slug"],
                                         slug=p["to_certification_slug"])
        UpgradePath.objects.update_or_create(
            from_cert=from_c, to_cert=to_c, effect=p["effect"],
            defaults={"source": staged.job.source, "last_verified_at": timezone.now(),
                      "confidence": p.get("confidence", "commonly_accepted")})
    elif staged.kind == "free_offer":
        FreeOffer.objects.create(title=p["title"], url=p["url"], starts=p.get("starts"),
                                 ends=p.get("ends"), description=p.get("description", ""),
                                 status=FreeOffer.Status.ACTIVE,
                                 last_verified_at=timezone.now())
    staged.status = staged.Status.APPROVED
    staged.reviewed_by = reviewer
    staged.save(update_fields=["status", "reviewed_by"])
