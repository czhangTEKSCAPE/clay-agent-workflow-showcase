#!/usr/bin/env python3
"""Run CSV rows through a Clay workflow's manual trigger and poll to completion.

Usage: wf_batch.py <rows.csv> --workflow wf_... [--inputs col,col,...] [--limit N] [--skip-suppressed]
                   [--extra key=value ...] [--out exports/<name>-runs-<date>.json] [--key domain]
Every listed input column is sent as a string; missing columns are sent as "". run_date is added.
Writes {key: {runId, status, credits, steps}} for the collect scripts.
"""
import argparse, csv, re, datetime as dt, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clay_cli import require_clay


def start_run(clay, workflow, payload, approve_runs=False):
    """Start a run; when Clay answers approval_required and the human has approved this batch (--approve-runs),
    approve the request (which runs the action) and return the runId. Returns (runId, note)."""
    out = subprocess.run([clay, "workflows", "runs", "test", workflow, "--inputs", "-"], input=json.dumps(payload), capture_output=True, text=True)
    try:
        d = json.loads(out.stdout or out.stderr or "{}")
    except Exception:
        return None, (out.stdout or out.stderr)[:160]
    if d.get("runId"):
        return d["runId"], ""
    err = d.get("error") or {}
    req = ((err.get("details") or {}).get("actionApprovalRequestId"))
    if err.get("code") == "approval_required" and req:
        det = err.get("details") or {}
        if det.get("action") != "workflows.run" or (det.get("input") or {}).get("workflowId") != workflow:
            return None, f"refusing to approve {req}: not a run of {workflow}"
        if not approve_runs:
            return None, f"approval required ({req}); re-run with --approve-runs after the human approves"
        ap = subprocess.run([clay, "approvals", "approve", req], capture_output=True, text=True)
        txt = ap.stdout or ap.stderr
        m = re.search(r"wfr_[A-Za-z0-9]+", txt)
        return (m.group(0) if m else None), ("" if m else f"approved {req} but no runId in: {txt[:160]}")
    return None, json.dumps(err)[:160]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--inputs", help="comma-separated columns to send (default: all CSV columns)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-suppressed", action="store_true", help="skip rows whose 'suppressed' column is yes")
    ap.add_argument("--extra", nargs="*", default=[], help="key=value constants added to every run")
    ap.add_argument("--map", nargs="*", default=[], help="csvcol=inputname renames, e.g. description=description_hint")
    ap.add_argument("--key", default="domain")
    ap.add_argument("--out")
    ap.add_argument("--name", default="runs")
    ap.add_argument("--approve-runs", action="store_true", help="the human approved this batch: approve Clay's per-run spend requests")
    a = ap.parse_args()
    CLAY = require_clay()
    rows = list(csv.DictReader(open(a.csv)))
    if a.skip_suppressed:
        rows = [r for r in rows if (r.get("suppressed") or "").lower() != "yes"]
    if a.limit:
        rows = rows[:a.limit]
    cols = a.inputs.split(",") if a.inputs else list(rows[0].keys())
    extra = dict(kv.split("=", 1) for kv in a.extra)
    today = dt.date.today().isoformat()
    runs = {}
    for r in rows:
        payload = {k: str(r.get(k, "") or "").lstrip("'") for k in cols}   # strip the spreadsheet-safety apostrophe
        for kv in a.map:
            src, dst = kv.split("=", 1); payload[dst] = str(r.get(src, "") or "").lstrip("'"); payload.pop(src, None)
        payload.update(extra); payload.setdefault("run_date", today)
        rid, note = start_run(CLAY, a.workflow, payload, a.approve_runs)
        key = payload.get(a.key) or str(len(runs))
        runs[key] = {"runId": rid, "company": payload.get("company_name", "") or payload.get("contact_name", "")}
        print(f"started {runs[key]['company'][:40]:<40} {key:<26} -> {rid or note}", flush=True)
        time.sleep(2)
    deadline = time.time() + 45 * 60
    while time.time() < deadline:
        pending = False
        for k, info in runs.items():
            if not info.get("runId") or info.get("status") in ("completed", "failed"):
                continue
            st = subprocess.run([CLAY, "workflows", "runs", "get", a.workflow, info["runId"]], capture_output=True, text=True)
            try:
                g = json.loads(st.stdout)
            except Exception:
                pending = True; continue
            if g.get("status") in ("completed", "failed"):
                info["status"] = g["status"]
                info["credits"] = round((g.get("dataCreditsUsed") or 0) + (g.get("actionCreditsUsed") or 0), 1)
                info["steps"] = (g.get("progress") or {}).get("completed")
                print(f"{info['status']:<9} {info['company'][:40]:<40} credits={info['credits']} steps={info['steps']}", flush=True)
            else:
                pending = True
        if not pending:
            break
        time.sleep(8)
    out_path = a.out or os.path.join(os.path.dirname(__file__), "..", "exports", f"{a.name}-{today}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(runs, open(out_path, "w"), indent=1)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
