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
import urllib.request

TOKEN = os.environ.get("CERTSLEUTH_WORKER_TOKEN", "")


def _req(url, data=None):
    r = urllib.request.Request(url, data=data, method="POST",
                               headers={"Authorization": f"Bearer {TOKEN}",
                                        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)


def fetch(api, n):
    jobs = _req(f"{api}/api/worker/jobs/claim?n={n}")["jobs"]
    outdir = pathlib.Path("jobs")
    outdir.mkdir(exist_ok=True)
    manifest = []
    for j in jobs:
        try:
            with urllib.request.urlopen(j["source_url"], timeout=30) as resp:
                content = resp.read()
        except Exception as e:
            print(f"job {j['job_id']}: fetch failed: {e}", file=sys.stderr)
            continue
        h = hashlib.sha256(content).hexdigest()
        snap = outdir / f"{j['job_id']}.html"
        snap.write_bytes(content)
        manifest.append({**j, "snapshot": str(snap), "snapshot_hash": h})
    (outdir / "jobs.jsonl").write_text("\n".join(json.dumps(m) for m in manifest))
    print(f"claimed {len(jobs)}, snapshotted {len(manifest)} -> jobs/jobs.jsonl")


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
