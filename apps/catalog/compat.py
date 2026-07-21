"""Compatibility of a catalog certification against the user's own certs.

Answers three questions for a browsed cert X (spec: user-facing browse):
1. Renewal interaction — does earning X renew any cert the user holds (UpgradePath
   from=theirs, to=X), or does something they hold renew X (from=X, to=theirs)?
   Edge direction convention: earning `to_cert` acts on `from_cert` (csm -> a-csm).
2. Shared CEU pool — same provider and both governed by CEU rules means activities in the
   provider's currency (CPE/SEU/...) count toward both. Cross-provider equivalence is NOT
   claimed here — that's the CreditRule matrix's job and stays out until it has data.
3. Tier relation — same-provider comparison on the `level` field, keyword-ranked. Only
   emitted when BOTH levels carry a recognizable keyword: no guesses on free text.
"""
from .models import UpgradePath

# Keyword -> rank. Specialty is orthogonal to the ladder, so it is deliberately absent.
_TIER_KEYWORDS = [
    (0, ("foundational", "fundamental", "entry")),
    (1, ("associate", "practitioner", "certified scrum", "foundation")),
    (2, ("professional", "expert", "advanced")),
]


def tier_rank(level):
    """Rank a level string, or None when no keyword matches (free text stays unjudged)."""
    text = (level or "").lower()
    for rank, words in _TIER_KEYWORDS:
        if any(w in text for w in words):
            return rank
    return None


def compatibility(cert, user_certs):
    """Compare `cert` against the user's held certs (UserCertification queryset with
    certification__provider selected). Returns display-ready findings; every list is
    empty when there's nothing true to say.

    Framing rules (product decisions, 2026-07-18):
    - Renewal and tier are ORTHOGONAL axes and never inferred from each other. A CSPO is
      a lower Scrum Alliance tier than a held A-CSM yet earning it renews both held certs
      (separate track, symmetric renewal edges) — so edges say nothing about tier, and
      levels say nothing about renewal. Both statements display side by side when both
      are true.
    - Renewal statements come only from inbound edges (held -> cert: earning `cert` acts
      on the held cert) and merge into ONE statement ("earning this renews your CSM +
      CSPO"), not one card per edge. Outbound renews edges (cert -> held) are not shown
      at all: "something you hold would be renewed by a cert you don't have yet" isn't
      actionable, and reading tier out of it was the bug this rule replaces.
    - Tier statements come only from the `level` field, keyword-ranked, and only when
      both sides rank. Lower-tier findings merge into one "lower level than one you
      already have" statement.
    """
    held = [uc.certification for uc in user_certs]
    held_ids = {c.pk for c in held}

    inbound = (UpgradePath.objects.filter(to_cert=cert, from_cert_id__in=held_ids)
               .select_related("from_cert__provider"))
    outbound = (UpgradePath.objects.filter(from_cert=cert, to_cert_id__in=held_ids)
                .select_related("to_cert__provider"))

    renews_yours = [e.from_cert for e in inbound if e.effect == UpgradePath.Effect.RENEWS]
    waives_fee_for = [e.from_cert for e in inbound
                      if e.effect == UpgradePath.Effect.WAIVES_FEE]
    supersedes_yours = [e.from_cert for e in inbound
                        if e.effect == UpgradePath.Effect.SUPERSEDES]
    # Prerequisites are their own axis (to_cert REQUIRES from_cert):
    # - inbound: the browsed cert requires something they hold -> they qualify.
    # - outbound: something they hold required the browsed cert -> earning it now is
    #   moot (you can't hold A-CSM without having had CSM). Stronger than, and shown
    #   instead of, a plain lower-tier note for that cert.
    prereqs_met = [e.from_cert for e in inbound if e.effect == UpgradePath.Effect.REQUIRES]
    required_by_yours = [e.to_cert for e in outbound
                         if e.effect == UpgradePath.Effect.REQUIRES]
    # Outbound renews edges carry no display; supersedes/waives remain worth a warning
    # ("your X supersedes this one" — don't earn an obsolete cert).
    covered_other = [e for e in outbound
                     if e.effect in (UpgradePath.Effect.WAIVES_FEE,
                                     UpgradePath.Effect.SUPERSEDES)]
    # Partial credit is its own axis, short of a full RENEWS (CompTIA: earning SecurityX
    # grants 25 of Cloud+'s 50 required CEUs — real progress, not full renewal). Same
    # inbound/outbound edges as above, just a different effect filter.
    partial_credit_toward_yours = [{"cert": e.from_cert, "ceu_amount": e.ceu_amount}
                                   for e in inbound
                                   if e.effect == UpgradePath.Effect.PARTIAL_CREDIT]
    partial_credit_for_this = [{"cert": e.to_cert, "ceu_amount": e.ceu_amount}
                               for e in outbound
                               if e.effect == UpgradePath.Effect.PARTIAL_CREDIT]

    same_provider = [c for c in held if c.provider_id == cert.provider_id and c.pk != cert.pk]
    shared_ceu = []
    if cert.current_rule and cert.current_rule.ceu_required:
        shared_ceu = [c for c in same_provider
                      if c.current_rule and c.current_rule.ceu_required]

    # Tier: keyword levels only, independent of any renewal edges. A held cert that
    # REQUIRED the browsed cert gets the prerequisite statement instead of a tier note.
    required_ids = {c.pk for c in required_by_yours}
    my_rank = tier_rank(cert.level)
    lower_level_than = []
    tiers = []
    if my_rank is not None:
        for c in same_provider:
            if c.pk in required_ids:
                continue
            their = tier_rank(c.level)
            if their is None:
                continue
            if my_rank < their:
                lower_level_than.append(c)
            else:
                tiers.append({"cert": c,
                              "relation": "higher" if my_rank > their else "same"})

    return {
        "holds_it": cert.pk in held_ids,
        "renews_yours": renews_yours,          # ONE combined statement in the template
        "waives_fee_for": waives_fee_for,
        "supersedes_yours": supersedes_yours,
        "prereqs_met": prereqs_met,            # browsed cert requires these held certs
        "required_by_yours": required_by_yours,  # held certs that required the browsed one
        "lower_level_than": lower_level_than,  # keyword-derived, prereq-covered excluded
        "covered_other": covered_other,        # held cert waives fee / supersedes this one
        "partial_credit_toward_yours": partial_credit_toward_yours,  # earning this credits held certs
        "partial_credit_for_this": partial_credit_for_this,  # a held cert already credits this one
        "shared_ceu": shared_ceu,              # same provider, both CEU-governed
        "ceu_currency": cert.provider.ceu_currency or "CEU",
        "tiers": tiers,                        # remaining keyword relations (higher/same)
    }
