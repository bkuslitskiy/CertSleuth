#!/usr/bin/env python3
"""CertSleuth local extraction worker (spec D17, SEC-004).

Pull-only client for the worker API. Run modes:
  claim+fetch : python claude_worker.py fetch --api https://certsleuth.com --n 10
                -> writes jobs/NNN.html snapshots + jobs.jsonl manifest
  submit      : python claude_worker.py submit results.jsonl --api https://certsleuth.com

Between fetch and submit, extraction happens via Claude Code (see CLAUDE.md in this
directory) or any process that emits results.jsonl lines matching schema v1
(worker/schema.py — mirrored from apps/research/schemas.py; keep in sync).

Token comes from env CERTSLEUTH_WORKER_TOKEN (create in admin -> Worker tokens).
The token is scoped to claim/submit only; treat compromise as low-impact but rotate anyway.
"""
import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # allow `import crawl`
import crawl  # noqa: E402  (worker/crawl.py — deterministic frontier helpers, SEC-017)
import extractors  # noqa: E402  (worker/extractors.py — per-provider cert-name rules)
import render  # noqa: E402  (worker/render.py — optional headless rendering, SEC-019)

TOKEN = os.environ.get("CERTSLEUTH_WORKER_TOKEN", "")
CRAWL_DELAY_SECONDS = 1.0  # politeness between fetches
# Provider sites (e.g. scrumalliance.org) 403 a bare/absent User-Agent. Identify as a
# normal browser so public policy pages are reachable.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/126.0 Safari/537.36 CertSleuthBot/1.0 (+https://certsleuth.com)")


def _req(url, data=None):
    r = urllib.request.Request(url, data=data, method="POST",
                               headers={"Authorization": f"Bearer {TOKEN}",
                                        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)


def _robots_fetch(robots_url):
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return None  # missing/unreadable robots -> fail open


# Deterministic extractor output lands here, separate from the operator's results.jsonl so
# rewriting one never clobbers the other. `submit` picks up both by default.
AUTO_RESULTS = "auto_results.jsonl"
AUTO_EXTRACTOR = "worker-deterministic-v1"
DEFAULT_RESULTS = "results.jsonl"


def _auto_facts(job_id, url, text, snapshot_hash):
    """Certification facts the per-provider rules can read straight off the page.

    Deterministic and provider-scoped: no LLM sees the page, so untrusted content cannot
    steer what gets emitted (SEC-006). Output is a staged fact like any other (SEC-005) —
    an approver still reviews it before it reaches the catalog. Returns [] for pages the
    rules don't cover, which is most of them; Claude Code handles the rest.
    """
    cert = extractors.extract_certification(url, text)
    if not cert:
        return []
    return [{"job_id": job_id, "kind": "certification",
             # provider's own cert page, read from its own og:title
             "payload": {**cert, "confidence": "confirmed"},
             "extractor": AUTO_EXTRACTOR, "snapshot_hash": snapshot_hash}]


def _post_report(api, job_id, report):
    """Send fetch metadata + discovered links to the server (SEC-017: app adds to queue)."""
    try:
        _req(f"{api}/api/worker/jobs/{job_id}/fetch-report", data=json.dumps(report).encode())
    except Exception as e:
        print(f"job {job_id}: fetch-report failed: {e}", file=sys.stderr)


def _fetch_one(url, prior, renderer=None):
    """Fetch one page (conditional, polite), rendering it when a renderer is supplied.
    Returns (server_report, snapshot_bytes|None).

    The cheap conditional GET runs first so an unchanged page costs a 304 and never reaches
    the browser. Only a live 200 is re-loaded in Chromium; if that fails we keep the raw
    HTML and report rendered=False rather than losing the page.
    """
    if not crawl.robots_allows(url, fetcher=_robots_fetch):
        print(f"robots.txt disallows {url}", file=sys.stderr)
        return {"http_status": "robots_disallowed"}, None
    headers = {"User-Agent": USER_AGENT}
    if prior.get("etag"):
        headers["If-None-Match"] = prior["etag"]
    if prior.get("last_modified"):
        headers["If-Modified-Since"] = prior["last_modified"]
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            etag, last_mod = resp.headers.get("ETag", ""), resp.headers.get("Last-Modified", "")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return {"unchanged": True}, None            # conditional-fetch hit
        # Bot-gates (Akamai/Cloudflare) 403/429 a bare HTTP client but pass a real
        # browser: retry in Chromium before declaring the page dead (PMI, Tableau,
        # Cisco all present this wall). Same SEC-019 posture — the renderer was going
        # to execute this page's JS anyway had the raw fetch succeeded.
        if e.code in (403, 429) and renderer is not None:
            status, html, _ = renderer.render(url, headers={"User-Agent": USER_AGENT})
            # Any 2xx with content counts: some CDNs answer the rendered document
            # request with 202 while still serving the full page (scrum.org).
            if status and 200 <= status < 300 and html:
                content = html.encode("utf-8", "replace")
                text = content.decode("utf-8", "replace")
                return ({"http_status": status, "etag": "", "last_modified": "",
                         "snapshot_hash": hashlib.sha256(content).hexdigest(),
                         "canonical": crawl.extract_canonical(text, url),
                         "discovered_links": crawl.scan_links(text, url),
                         "rendered": True,
                         "text_len": crawl.visible_text_len(text),
                         "main_text_len": crawl.main_text_len(text)}, content)
        return {"http_status": e.code}, None
    except Exception:
        return {"http_status": "error"}, None
    rendered = False
    if renderer is not None:
        status, html, _ = renderer.render(url, headers={"User-Agent": USER_AGENT})
        if status and 200 <= status < 300 and html:
            content, rendered = html.encode("utf-8", "replace"), True
    text = content.decode("utf-8", "replace")
    return ({"http_status": 200, "etag": etag, "last_modified": last_mod,
             "snapshot_hash": hashlib.sha256(content).hexdigest(),
             "canonical": crawl.extract_canonical(text, url),
             "discovered_links": crawl.scan_links(text, url),
             "rendered": rendered,
             "text_len": crawl.visible_text_len(text),
             # content outside site chrome — the signal that separates a shell from a real
             # page (full-page counts do not; see crawl.main_text_len)
             "main_text_len": crawl.main_text_len(text)}, content)


def fetch(api, n, use_render=True):
    jobs = _req(f"{api}/api/worker/jobs/claim?n={n}")["jobs"]
    outdir = pathlib.Path("jobs")
    outdir.mkdir(exist_ok=True)
    if use_render and not render.available():
        print(f"warning: {render.unavailable_reason()}", file=sys.stderr)
        use_render = False
    # One browser for the whole batch; contextlib.nullcontext keeps the loop identical when
    # rendering is off or unavailable.
    browser_cm = (render.Renderer(USER_AGENT) if use_render
                  else contextlib.nullcontext())
    with browser_cm as renderer:
        return _fetch_loop(api, jobs, outdir, renderer)


def _fetch_loop(api, jobs, outdir, renderer):
    manifest = []
    snapped = 0
    auto = []
    for i, j in enumerate(jobs):
        if i:
            time.sleep(CRAWL_DELAY_SECONDS)
        report, content = _fetch_one(j["source_url"], j, renderer)
        entry = {**j, **report}
        if content is not None:
            snap = outdir / f"{j['job_id']}.html"
            snap.write_bytes(content)
            entry["snapshot"] = str(snap)
            snapped += 1
            auto.extend(_auto_facts(j["job_id"], j["source_url"],
                                    content.decode("utf-8", "replace"),
                                    report.get("snapshot_hash", "")))
        elif report.get("http_status") not in (None,) and not report.get("unchanged"):
            print(f"job {j['job_id']}: {report.get('http_status')}", file=sys.stderr)
        _post_report(api, j["job_id"], report)          # app adds discovered links to queue
        manifest.append(entry)
    (outdir / "jobs.jsonl").write_text("\n".join(json.dumps(m) for m in manifest))
    (outdir / AUTO_RESULTS).write_text("\n".join(json.dumps(a) for a in auto))
    total_links = sum(len(m.get("discovered_links", [])) for m in manifest)
    n_rendered = sum(1 for m in manifest if m.get("rendered"))
    print(f"claimed {len(jobs)}, snapshotted {snapped} ({n_rendered} rendered), "
          f"discovered {total_links} same-domain links (queued for review) -> jobs/jobs.jsonl")
    print(f"auto-extracted {len(auto)} certification fact(s) -> jobs/{AUTO_RESULTS}")


def _result_paths(results_path):
    """The operator's results file plus the deterministic extractor's, when present.
    An explicitly-named path is used alone — only the default sweeps up both."""
    paths = [pathlib.Path(results_path)]
    if results_path == DEFAULT_RESULTS:
        auto = pathlib.Path("jobs") / AUTO_RESULTS
        if auto.exists():
            paths.append(auto)
    return [p for p in paths if p.exists()]


def submit(api, results_path):
    by_job = {}
    paths = _result_paths(results_path)
    if not paths:
        sys.exit(f"no results to submit ({results_path} not found)")
    for path in paths:
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                by_job.setdefault(r["job_id"], []).append(r)
    print(f"submitting from {', '.join(str(p) for p in paths)}")
    for job_id, results in by_job.items():
        out = _req(f"{api}/api/worker/jobs/{job_id}/result",
                   data=json.dumps(results).encode())
        print(f"job {job_id}: staged {out.get('staged')}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["fetch", "submit"])
    p.add_argument("results", nargs="?", default=DEFAULT_RESULTS)
    p.add_argument("--api", required=True)
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--no-render", action="store_true",
                   help="skip headless rendering (faster; JS-built pages come back empty)")
    a = p.parse_args()
    if not TOKEN:
        sys.exit("Set CERTSLEUTH_WORKER_TOKEN")
    fetch(a.api, a.n, use_render=not a.no_render) if a.mode == "fetch" \
        else submit(a.api, a.results)
