"""User-facing catalog browse (login-gated like the rest of the app; read-only)."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, render

from apps.core.staleness import staleness
from apps.tracker.models import UserCertification
from .compat import compatibility
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
                     "chip": staleness(rule.last_verified_at) if rule else "red"})
    return render(request, "catalog/provider.html",
                  {"provider": provider, "rows": rows})


@login_required
def cert_detail(request, provider_slug, cert_slug):
    cert = get_object_or_404(
        Certification.objects.select_related("provider"),
        provider__slug=provider_slug, slug=cert_slug)
    rule = cert.current_rule
    compat = compatibility(cert, _my_certs(request.user))
    planned = request.user.goals.filter(certification=cert).exists()
    return render(request, "catalog/certification.html", {
        "cert": cert, "rule": rule, "compat": compat, "planned": planned,
        "chip": staleness(rule.last_verified_at) if rule else "red",
    })
