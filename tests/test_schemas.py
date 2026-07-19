"""Extraction schema round-trip (D21): every sample line must validate in BOTH validators
(Django-side pydantic and the standalone worker mirror) — CI catches drift."""
import json
import pathlib
import subprocess
import sys
import pytest
from apps.research.schemas import ExtractionResult

SAMPLES = [
    {"job_id": 1, "kind": "renewal_rule", "extractor": "claude-code-local",
     "payload": {"provider_slug": "isc2", "certification_slug": "cissp",
                 "certification_name": "CISSP", "ceu_required": 120,
                 "ceu_categories": {"Group A": 90, "Group B": 30},
                 "annual_fee_usd": 135, "cycle_years": 3, "confidence": "confirmed"}},
    {"job_id": 2, "kind": "upgrade_path", "extractor": "api-haiku",
     "payload": {"provider_slug": "scrum-alliance", "from_certification_slug": "csm",
                 "to_certification_slug": "a-csm", "effect": "renews"}},
    {"job_id": 3, "kind": "certification", "extractor": "claude-code-local",
     "payload": {"provider_slug": "aws", "slug": "saa", "name": "Solutions Architect Associate",
                 "exam_cost_usd": 150, "validity_years": 3}},
    {"job_id": 4, "kind": "upgrade_path", "extractor": "claude-code-local",
     "payload": {"provider_slug": "scrum-alliance", "from_certification_slug": "csm",
                 "to_certification_slug": "a-csm", "effect": "requires"}},
    {"job_id": 5, "kind": "credit_rule", "extractor": "claude-code-local",
     "payload": {"provider_slug": "isaca", "category": "Certification-aligned",
                 "activity_kinds": ["course", "conference", "webinar"],
                 "credits_per_hour": 1, "confidence": "confirmed"}},
]


@pytest.mark.parametrize("sample", SAMPLES)
def test_pydantic_roundtrip(sample):
    res = ExtractionResult(**sample)
    assert res.validated_payload()


def test_worker_mirror_agrees(tmp_path):
    f = tmp_path / "results.jsonl"
    f.write_text("\n".join(json.dumps(s) for s in SAMPLES))
    proc = subprocess.run([sys.executable, "worker/schema.py", str(f)],
                          capture_output=True, cwd=pathlib.Path(__file__).parent.parent)
    assert proc.returncode == 0, proc.stdout.decode()


def test_bad_confidence_rejected():
    bad = dict(SAMPLES[0])
    bad["payload"] = {**bad["payload"], "confidence": "vibes"}
    with pytest.raises(Exception):
        ExtractionResult(**bad).validated_payload()


def test_retired_certification_round_trips():
    sample = {"job_id": 6, "kind": "certification", "extractor": "claude-code-local",
              "payload": {"provider_slug": "comptia", "slug": "old-cert",
                          "name": "Old Cert", "status": "retired",
                          "retired_date": "2026-01-01"}}
    assert ExtractionResult(**sample).validated_payload()["status"] == "retired"
