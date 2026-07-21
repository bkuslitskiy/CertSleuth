#!/usr/bin/env python3
"""Standalone mirror of apps/research/schemas.py (keep in sync — CI checks drift).
Usage: python schema.py results.jsonl  -> validates every line, exits nonzero on error."""
import json
import sys

KINDS = {"renewal_rule", "upgrade_path", "credit_rule", "free_offer", "certification"}
CONF = {"confirmed", "commonly_accepted", "inferred"}


def validate_line(obj):
    assert isinstance(obj.get("job_id"), int), "job_id must be int"
    assert obj.get("kind") in KINDS, f"kind must be one of {KINDS}"
    assert isinstance(obj.get("payload"), dict), "payload must be object"
    assert isinstance(obj.get("extractor"), str) and obj["extractor"], "extractor required"
    p = obj["payload"]
    if obj["kind"] == "renewal_rule":
        assert p.get("provider_slug") and p.get("certification_slug"), "slugs required"
        assert p.get("confidence", "commonly_accepted") in CONF
    if obj["kind"] == "upgrade_path":
        assert p.get("effect") in {"renews", "waives_fee", "supersedes", "requires",
                                    "partial_credit"}
    if obj["kind"] == "credit_rule":
        assert p.get("provider_slug") and p.get("category"), "provider/category required"
        assert p.get("confidence", "commonly_accepted") in CONF
    if obj["kind"] == "certification":
        assert p.get("provider_slug") and p.get("slug") and p.get("name")
        assert p.get("status") in (None, "active", "retired"), "bad lifecycle status"
    if obj["kind"] == "free_offer":
        assert p.get("title") and p.get("url")


if __name__ == "__main__":
    errors = 0
    for i, line in enumerate(open(sys.argv[1]), 1):
        if not line.strip():
            continue
        try:
            validate_line(json.loads(line))
        except (AssertionError, json.JSONDecodeError) as e:
            print(f"line {i}: {e}")
            errors += 1
    sys.exit(1 if errors else 0)
