from django.db import models


class Staleness(models.TextChoices):  # D3 chips derive from last_verified, computed in core.staleness
    pass


class Confidence(models.TextChoices):  # D8
    CONFIRMED = "confirmed", "Confirmed (handbook-cited)"
    ACCEPTED = "commonly_accepted", "Commonly accepted"
    INFERRED = "inferred", "Inferred"


class Source(models.Model):
    """Provenance record (SEC-005/006: provenance stored apart from content).
    Crawl classification + cadence per docs/crawl-procedure.md (SEC-017)."""
    class Status(models.TextChoices):
        ACTIVE = "active", "Active (yields facts)"
        HUB = "hub", "Hub (same-domain links, no facts)"
        BARREN = "barren", "Barren (no facts, no links)"
        NEEDS_RENDER = "needs_render", "Needs render (JS-hidden content)"
        DEAD = "dead", "Dead (404/403)"

    # cadence by status (days); barren/needs_render/dead recrawl rarely, never delete.
    CADENCE_BY_STATUS = {"active": 7, "hub": 30, "barren": 180, "needs_render": 365, "dead": 365}

    url = models.URLField(unique=True, max_length=500)
    # Registrable domain, auto-set on save. Powers domain-interleaved job claims
    # (politeness: a claim batch alternates across sites) and admin filtering.
    domain = models.CharField(max_length=120, blank=True, db_index=True)
    cadence_days = models.PositiveSmallIntegerField(default=7)  # weekly rules, daily offers
    scheduled = models.BooleanField(default=False)  # D16: only Approver-promoted sources auto-crawl
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    last_content_hash = models.CharField(max_length=64, blank=True)
    etag = models.CharField(max_length=250, blank=True)          # conditional GET
    http_last_modified = models.CharField(max_length=80, blank=True)
    last_yield_count = models.PositiveIntegerField(default=0)     # facts from the last crawl
    last_yield_at = models.DateTimeField(null=True, blank=True)
    discovered_from = models.ForeignKey("self", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="discovered")
    depth = models.PositiveSmallIntegerField(default=0)           # hops from a seed
    submitted_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        if not self.domain:
            from apps.core.domains import registrable_domain
            self.domain = registrable_domain(self.url)[:120]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.url


class Provider(models.Model):
    name = models.CharField(max_length=120)          # mutable display (D26)
    slug = models.SlugField(unique=True)             # stable URL identity
    portal_url = models.URLField(blank=True)
    ceu_currency = models.CharField(max_length=40, blank=True)  # "CPE", "SEU", ...

    def __str__(self):
        return self.name


class Certification(models.Model):
    class Lifecycle(models.TextChoices):
        ACTIVE = "active", "Active (attainable)"
        # No longer attainable from the provider; existing holders keep tracking it
        # (renewal rules may still apply, upgrade edges may point at successors).
        RETIRED = "retired", "Retired"

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="certifications")
    name = models.CharField(max_length=200)
    # The short form people actually know (CISM, PMP, SAA). Display + alphabetical
    # lookup; never keyed on (D26 — that's what slug/pk are for).
    abbreviation = models.CharField(max_length=40, blank=True)
    slug = models.SlugField()
    status = models.CharField(max_length=10, choices=Lifecycle.choices, default=Lifecycle.ACTIVE)
    retired_date = models.DateField(null=True, blank=True)
    level = models.CharField(max_length=80, blank=True)
    # Eligibility/prerequisite text stated by the provider (e.g. "5+ years required work
    # experience"). Separate from `level` (a tier/difficulty word) — the two were getting
    # conflated by extraction because there was nowhere else to put an experience
    # requirement (2026-07-21 audit found ISC2 facts miscaptured this way).
    eligibility_requirement = models.CharField(max_length=300, blank=True)
    exam_cost_usd = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    validity_years = models.PositiveSmallIntegerField(null=True, blank=True)
    external_ids = models.JSONField(default=dict, blank=True)  # {"credly_template": "...", ...} (D26)
    # Provenance for the certification fact itself (SEC-005/006) — lets the browse UI
    # link back to the page a user can confirm the data on. RenewalRule/UpgradePath/
    # CreditRule already carry their own `source`; this is the analogous field for the
    # certification metadata row (name/level/cost/etc), which had none before.
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")

    class Meta:
        unique_together = [("provider", "slug")]

    def __str__(self):
        return f"{self.provider.name} {self.name}"

    @property
    def current_rule(self):
        return self.renewal_rules.filter(superseded_by__isnull=True).order_by("-effective_date").first()


class RenewalRule(models.Model):
    """Versioned, never overwritten. New extraction -> new row, old row gets superseded_by."""
    certification = models.ForeignKey(Certification, on_delete=models.CASCADE, related_name="renewal_rules")
    ceu_required = models.PositiveSmallIntegerField(null=True, blank=True)
    ceu_categories = models.JSONField(default=dict, blank=True)  # {"Group A": 60, "Group B": 30}
    annual_fee_usd = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    renewal_fee_usd = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    cycle_years = models.PositiveSmallIntegerField(null=True, blank=True)
    grace_period_days = models.PositiveSmallIntegerField(null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    source = models.ForeignKey(Source, null=True, on_delete=models.SET_NULL)
    confidence = models.CharField(max_length=20, choices=Confidence.choices, default=Confidence.ACCEPTED)
    last_verified_at = models.DateTimeField(null=True, blank=True)  # drives staleness chip
    superseded_by = models.OneToOneField("self", null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="supersedes")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        current = " (superseded)" if self.superseded_by_id else ""
        return f"{self.certification} rule: {self.ceu_required or '?'} CEU / {self.cycle_years or '?'}yr{current}"


class UpgradePath(models.Model):
    class Effect(models.TextChoices):
        RENEWS = "renews", "Renews"
        WAIVES_FEE = "waives_fee", "Waives fee"
        SUPERSEDES = "supersedes", "Supersedes"
        # to_cert REQUIRES from_cert as a prerequisite (A-CSM requires CSM). Distinct
        # from tier: Network+ is a lower CompTIA tier than Security+ but not required
        # by it — providers wire these differently, so it's an edge, not an inference.
        REQUIRES = "requires", "Requires (prerequisite)"
        # Earning to_cert grants a FIXED number of CEUs toward from_cert's renewal —
        # short of a full RENEWS (CompTIA: "SecurityX grants 25 CEUs toward Cloud+", out
        # of Cloud+'s 50 required). ceu_amount carries the count; null for every other
        # effect. Distinct from CreditRule, which is a generic activity-kind rate, not a
        # specific cert-to-cert credit.
        PARTIAL_CREDIT = "partial_credit", "Partial credit"

    from_cert = models.ForeignKey(Certification, on_delete=models.CASCADE, related_name="upgrade_edges_in")
    to_cert = models.ForeignKey(Certification, on_delete=models.CASCADE, related_name="upgrade_edges_out")
    effect = models.CharField(max_length=16, choices=Effect.choices)
    ceu_amount = models.PositiveSmallIntegerField(null=True, blank=True)  # only for PARTIAL_CREDIT
    source = models.ForeignKey(Source, null=True, on_delete=models.SET_NULL)
    confidence = models.CharField(max_length=20, choices=Confidence.choices, default=Confidence.ACCEPTED)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("from_cert", "to_cert", "effect")]

    def __str__(self):
        return f"{self.from_cert.name} → {self.to_cert.name} ({self.get_effect_display()})"


class CreditRule(models.Model):
    """Cross-crediting eligibility (D8): activity kinds -> provider category. The matrix."""
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    category = models.CharField(max_length=80)                  # e.g. "Group A"
    activity_kinds = models.JSONField(default=list)             # ["webinar", "course", ...]
    credits_per_hour = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    source = models.ForeignKey(Source, null=True, on_delete=models.SET_NULL)
    confidence = models.CharField(max_length=20, choices=Confidence.choices, default=Confidence.ACCEPTED)
    last_verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.provider.name} {self.category}: {self.credits_per_hour}/hr"
