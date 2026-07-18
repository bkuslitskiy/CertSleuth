"""Deterministic cert extraction wired into the worker fetch->submit flow.

worker/extractors.py existed but nothing called it — the recovered ISACA/AWS/CompTIA/GIAC
catalogs came from a one-off script, so every fresh crawl re-earned the promo-h1 bug these
rules already fix. These tests pin the wiring: fetch emits schema-valid facts to a separate
provenance file, and the default submit sweeps both files up.
"""
import importlib.util
import json
import pathlib

_WORKER = pathlib.Path(__file__).resolve().parent.parent / "worker"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"worker_{name}", _WORKER / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cw = _load("claude_worker")
schema = _load("schema")


def _page(og):
    return f'<html><head><meta property="og:title" content="{og}"></head></html>'


def test_auto_facts_emits_schema_valid_certification():
    facts = cw._auto_facts(7, "https://www.giac.org/certifications/strategic-osint-analyst-gsoa",
                           _page("GIAC Strategic OSINT Analyst (GSOA)"), "abc123")
    assert len(facts) == 1
    schema.validate_line(facts[0])          # must satisfy the shared v1 contract
    assert facts[0]["job_id"] == 7
    assert facts[0]["snapshot_hash"] == "abc123"
    assert facts[0]["extractor"] == cw.AUTO_EXTRACTOR
    assert facts[0]["payload"]["provider_slug"] == "giac"
    assert facts[0]["payload"]["confidence"] == "confirmed"


def test_auto_facts_empty_for_uncovered_page():
    # unknown provider and category pages produce nothing — Claude Code handles those
    assert cw._auto_facts(1, "https://example.com/x", _page("Something"), "h") == []
    assert cw._auto_facts(2, "https://www.giac.org/certifications/",
                          _page("Find a Certification"), "h") == []


def test_auto_facts_uses_og_title_not_promo_h1():
    # the regression the one-off script fixed, now guarded in the live flow
    page = ('<html><head><meta property="og:title" content="CISM Certification | '
            'Certified Information Security Manager"></head>'
            '<body><h1>CISM Wins at SC Awards North America!</h1></body></html>')
    facts = cw._auto_facts(3, "https://www.isaca.org/credentialing/cism", page, "h")
    assert facts[0]["payload"]["name"] == "Certified Information Security Manager"


def test_default_submit_includes_auto_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results.jsonl").write_text("{}")
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / cw.AUTO_RESULTS).write_text("{}")
    names = [p.name for p in cw._result_paths(cw.DEFAULT_RESULTS)]
    assert names == ["results.jsonl", cw.AUTO_RESULTS]


def test_explicit_path_does_not_sweep_in_auto_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mine.jsonl").write_text("{}")
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / cw.AUTO_RESULTS).write_text("{}")
    assert [p.name for p in cw._result_paths("mine.jsonl")] == ["mine.jsonl"]


def test_missing_auto_results_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results.jsonl").write_text("{}")
    assert [p.name for p in cw._result_paths(cw.DEFAULT_RESULTS)] == ["results.jsonl"]


def test_auto_results_alone_is_submittable(tmp_path, monkeypatch):
    # a crawl round with no operator extraction still submits its deterministic facts
    monkeypatch.chdir(tmp_path)
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / cw.AUTO_RESULTS).write_text(json.dumps({"job_id": 1}))
    assert [p.name for p in cw._result_paths(cw.DEFAULT_RESULTS)] == [cw.AUTO_RESULTS]
