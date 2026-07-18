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


def _post_report(api, job_id, report):
    """Send fetch metadata + discovered links to the server (SEC-017: app adds to queue)."""
    try:
        _req(f"{api}/api/worker/jobs/{job_id}/fetch-report", data=json.dumps(report).encode())
    except Exception as e:
        print(f"job {job_id}: fetch-report failed: {e}", file=sys.stderr)


def _fetch_one(url, prior):
    """Fetch one page (conditional, polite). Returns (server_report, snapshot_bytes|None)."""
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
        return {"http_status": e.code}, None
    except Exception:
        return {"http_status": "error"}, None
    text = content.decode("utf-8", "replace")
    return ({"http_status": 200, "etag": etag, "last_modified": last_mod,
             "snapshot_hash": hashlib.sha256(content).hexdigest(),
             "canonical": crawl.extract_canonical(text, url),
             "discovered_links": crawl.scan_links(text, url),
             "text_len": crawl.visible_text_len(text)}, content)


def fetch(api, n):
    jobs = _req(f"{api}/api/worker/jobs/claim?n={n}")["jobs"]
    outdir = pathlib.Path("jobs")
    outdir.mkdir(exist_ok=True)
    manifest = []
    snapped = 0
    for i, j in enumerate(jobs):
        if i:
            time.sleep(CRAWL_DELAY_SECONDS)
        report, content = _fetch_one(j["source_url"], j)
        entry = {**j, **report}
        if content is not None:
            snap = outdir / f"{j['job_id']}.html"
            snap.write_bytes(content)
            entry["snapshot"] = str(snap)
            snapped += 1
        elif report.get("http_status") not in (None,) and not report.get("unchanged"):
            print(f"job {j['job_id']}: {report.get('http_status')}", file=sys.stderr)
        _post_report(api, j["job_id"], report)          # app adds discovered links to queue
        manifest.append(entry)
    (outdir / "jobs.jsonl").write_text("\n".join(json.dumps(m) for m in manifest))
    total_links = sum(len(m.get("discovered_links", [])) for m in manifest)
    print(f"claimed {len(jobs)}, snapshotted {snapped}, discovered {total_links} "
          f"same-domain links (queued for review) -> jobs/jobs.jsonl")


def submit(api, results_path):
    by_job = {}
    for line in pathlib.Path(results_path).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            by_job.setdefault(r["job_id"], []).append(r)
    for job_id, results in by_job.items():
        out = _req(f"{api}/api/worker/jobs/{job_id}/result",
                   data=json.dumps(results).encode())
        print(f"job {job_id}: staged {out.get('staged')}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["fetch", "submit"])
    p.add_argument("results", nargs="?", default="results.jsonl")
    p.add_argument("--api", required=True)
    p.add_argument("--n", type=int, default=10)
    a = p.parse_args()
    if not TOKEN:
        sys.exit("Set CERTSLEUTH_WORKER_TOKEN")
    fetch(a.api, a.n) if a.mode == "fetch" else submit(a.api, a.results)
