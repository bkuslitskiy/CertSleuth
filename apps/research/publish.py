"""Approval -> canonical publication. Called from admin action. Versioning per spec §2."""
from django.utils import timezone
from apps.catalog.models import Provider, Certification, CreditRule, RenewalRule, UpgradePath
from apps.offers.models import FreeOffer


def publish(staged, reviewer):
    p = staged.payload
    if staged.kind == "certification":
        provider, _ = Provider.objects.get_or_create(slug=p["provider_slug"],
                                                     defaults={"name": p["provider_slug"].title()})
        defaults = {"name": p["name"], "level": p.get("level", ""),
                    **({"abbreviation": p["abbreviation"]} if p.get("abbreviation") else {}),
                    "exam_cost_usd": p.get("exam_cost_usd"),
                    "validity_years": p.get("validity_years"),
                    "external_ids": p.get("external_ids", {})}
        # Lifecycle only changes when the fact asserts it — an ordinary re-crawl of a
        # cert page must never silently resurrect or retire a certification.
        if p.get("status"):
            defaults["status"] = p["status"]
            if p.get("retired_date"):
                defaults["retired_date"] = p["retired_date"]
        Certification.objects.update_or_create(
            provider=provider, slug=p["slug"], defaults=defaults)
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
                      "confidence": p.get("confidence", "commonly_accepted"),
                      "ceu_amount": p.get("ceu_amount")})
    elif staged.kind == "credit_rule":
        provider = Provider.objects.get(slug=p["provider_slug"])
        CreditRule.objects.update_or_create(
            provider=provider, category=p["category"],
            defaults={"activity_kinds": p.get("activity_kinds", []),
                      "credits_per_hour": p.get("credits_per_hour", 1),
                      "source": staged.job.source,
                      "confidence": p.get("confidence", "commonly_accepted"),
                      "last_verified_at": timezone.now()})
    elif staged.kind == "free_offer":
        FreeOffer.objects.create(title=p["title"], url=p["url"], starts=p.get("starts"),
                                 ends=p.get("ends"), description=p.get("description", ""),
                                 status=FreeOffer.Status.ACTIVE,
                                 last_verified_at=timezone.now())
    else:
        # A kind with no publish branch must never be silently marked approved —
        # that's an approve-and-lose path (credit_rule fell through here until 2026-07-19).
        raise ValueError(f"no publish handler for kind {staged.kind!r}")
    staged.status = staged.Status.APPROVED
    staged.reviewed_by = reviewer
    staged.save(update_fields=["status", "reviewed_by"])
