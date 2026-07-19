"""Extraction schema v1 — the JSONL contract shared by all extractors (spec 3.5).
Pydantic here; worker/ mirrors it standalone so the worker has no Django dependency."""
from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


class RenewalRulePayload(BaseModel):
    provider_slug: str
    certification_slug: str
    certification_name: str
    ceu_required: int | None = None
    ceu_categories: dict[str, int] = {}
    annual_fee_usd: float | None = None      # for providers with yearly maintenance fees
    renewal_fee_usd: float | None = None     # per-cycle fee (e.g. Scrum Alliance $100/2yr)
    cycle_years: int | None = None
    grace_period_days: int | None = None
    effective_date: str | None = None  # ISO date
    confidence: Literal["confirmed", "commonly_accepted", "inferred"] = "commonly_accepted"


class UpgradePathPayload(BaseModel):
    provider_slug: str
    from_certification_slug: str
    to_certification_slug: str
    effect: Literal["renews", "waives_fee", "supersedes", "requires"]
    confidence: Literal["confirmed", "commonly_accepted", "inferred"] = "commonly_accepted"


class CreditRulePayload(BaseModel):
    provider_slug: str
    category: str
    activity_kinds: list[str] = []
    credits_per_hour: float = 1
    confidence: Literal["confirmed", "commonly_accepted", "inferred"] = "commonly_accepted"


class FreeOfferPayload(BaseModel):
    title: str
    url: HttpUrl
    provider_slug: str | None = None
    starts: str | None = None
    ends: str | None = None
    description: str = ""


class CertificationPayload(BaseModel):
    provider_slug: str
    name: str
    slug: str
    level: str = ""
    exam_cost_usd: float | None = None
    validity_years: int | None = None
    external_ids: dict[str, str] = {}


class ExtractionResult(BaseModel):
    """One line of results.jsonl."""
    job_id: int
    kind: Literal["renewal_rule", "upgrade_path", "credit_rule", "free_offer", "certification"]
    payload: dict
    extractor: str = Field(pattern=r"^[a-z0-9\-_.]+$", max_length=80)
    snapshot_hash: str = ""

    def validated_payload(self):
        model = {"renewal_rule": RenewalRulePayload, "upgrade_path": UpgradePathPayload,
                 "credit_rule": CreditRulePayload, "free_offer": FreeOfferPayload,
                 "certification": CertificationPayload}.get(self.kind)
        return model(**self.payload).model_dump(mode="json") if model else self.payload
