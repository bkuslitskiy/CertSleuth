"""User-facing catalog browse (login-gated like the rest of the app; read-only)."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, render

from apps.core.staleness import staleness
from apps.tracker.models import UserCertification
from .compat import compatibility, tier_rank
from .models import Certification, Provider


def _my_certs(user):
    return (UserCertification.objects.filter(user=user)
            .select_related("certification__provider"))


@login_required
def provider_list(request):
    providers = (Provider.objects.annotate(n_certs=Count("certifications"))
                 .filter(n_certs__gt=0).order_by("name"))
    mine = {uc.certification.provider_id for uc in _my_certs(request.user)}
    return render(request, "catalog/providers.html",
                  {"providers": providers, "my_provider_ids": mine})


@login_required
def provider_detail(request, provider_slug):
    provider = get_object_or_404(Provider, slug=provider_slug)
    # Alphabetize on the short form when it exists — people scan for "CISM", not
    # "Certified Information Security Manager" (Boris, 2026-07-19).
    certs = sorted(provider.certifications.prefetch_related(Prefetch("renewal_rules")),
                   key=lambda c: (c.abbreviation or c.name).lower())
    held_ids = {uc.certification_id for uc in _my_certs(request.user)}
    planned_ids = set(request.user.goals.values_list("certification_id", flat=True))
    rows = []
    for c in certs:
        rule = c.current_rule
        rows.append({"cert": c, "rule": rule, "held": c.pk in held_ids,
                     "planned": c.pk in planned_ids,
                     "chip": staleness(rule.last_verified_at) if rule else "red",
                     # Numeric sort keys for the browse table (client-side sort): tier
                     # rank so "beginner" certs group together across free-text `level`
                     # spellings, fee picks whichever of renewal/annual is on file.
                     "level_rank": tier_rank(c.level),
                     "fee": (rule.renewal_fee_usd if rule and rule.renewal_fee_usd
                             else rule.annual_fee_usd if rule else None)})
    return render(request, "catalog/provider.html",
                  {"provider": provider, "rows": rows})


def _cert_sources(cert, rule):
    """Distinct source pages backing what's shown on this cert's detail page, so a user
    can confirm the data, read more, or go apply — de-duped by URL, most relevant first."""
    seen = {}

    def add(source, label):
        if source and source.url not in seen:
            seen[source.url] = {"url": source.url, "label": label}

    add(cert.source, "Certification details")
    if rule:
        add(rule.source, "Renewal rule")
    # Model naming trap: `upgrade_edges_in` is the related_name on the *from_cert* field
    # (rows where this cert IS from_cert, i.e. it leads TO something else), and
    # `upgrade_edges_out` is the related_name on *to_cert* (rows where this cert IS
    # to_cert, i.e. something else leads TO it) — the reverse of what the names suggest.
    for edge in cert.upgrade_edges_in.select_related("source", "to_cert"):
        add(edge.source, f"Upgrade path to {edge.to_cert.name}")
    for edge in cert.upgrade_edges_out.select_related("source", "from_cert"):
        add(edge.source, f"Upgrade path from {edge.from_cert.name}")
    return list(seen.values())


@login_required
def cert_detail(request, provider_slug, cert_slug):
    cert = get_object_or_404(
        Certification.objects.select_related("provider", "source"),
        provider__slug=provider_slug, slug=cert_slug)
    rule = cert.current_rule
    compat = compatibility(cert, _my_certs(request.user))
    planned = request.user.goals.filter(certification=cert).exists()
    return render(request, "catalog/certification.html", {
        "cert": cert, "rule": rule, "compat": compat, "planned": planned,
        "chip": staleness(rule.last_verified_at) if rule else "red",
        "sources": _cert_sources(cert, rule),
    })
