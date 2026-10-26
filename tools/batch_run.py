#!/usr/bin/env python3
"""Launch a list of leads through a Clay workflow and poll to completion.

Usage:
  batch_run.py <leads.json> <workflow_id>

leads.json format:
  [{"name": "Jane Doe (CFO, Acme)", "url": "https://www.linkedin.com/in/janedoe/"}, ...]

Prints one line per lead as it finishes, then a JSON summary with status and credits used.
"""
import argparse
import json
import subprocess
import sys
import time

from clay_cli import require_clay

TERMINAL = ("completed", "failed")


def launch(clay, workflow, lead):
    """Start one run and return its runId, or None if Clay did not return one."""
    out = subprocess.run([clay, "workflows", "runs", "test", workflow, "--input", "-"],
                         input=json.dumps({"linkedin_url": lead["url"]}),
                         capture_output=True, text=True)
    try:
        return json.loads(out.stdout).get("runId")
    except (ValueError, AttributeError):
        return None


def summarize(run):
    """Reduce a `runs get` response to the fields we report."""
    return {
        "status": run.get("status"),
        "error": (run.get("error") or "")[:150],
        "credits": round((run.get("dataCreditsUsed") or 0) + (run.get("actionCreditsUsed") or 0), 1),
        "steps": (run.get("progress") or {}).get("completed"),
    }


def poll(clay, workflow, runs, timeout_s=50 * 60, interval_s=45):
    """Poll every launched run until all reach a terminal state or the deadline passes."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pending = False
        for name, info in runs.items():
            if info.get("status") in TERMINAL or not info.get("runId"):
                continue
            res = subprocess.run([clay, "workflows", "runs", "get", workflow, info["runId"]],
                                 capture_output=True, text=True)
            try:
                data = json.loads(res.stdout)
            except ValueError:
                continue
            if data.get("status") in TERMINAL:
                info.update(summarize(data))
                print(f"DONE {name}: {info['status']} steps={info['steps']} "
                      f"credits={info['credits']} {info['error']}", flush=True)
            else:
                pending = True
        if not pending:
            break
        time.sleep(interval_s)
    return runs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("leads", help="path to leads.json")
    ap.add_argument("workflow", help="Clay workflow id (wf_...)")
    args = ap.parse_args(argv)

    clay = require_clay()
    with open(args.leads) as f:
        leads = json.load(f)

    runs = {}
    for lead in leads:
        run_id = launch(clay, args.workflow, lead)
        runs[lead["name"]] = {"runId": run_id, "url": lead["url"]}
        print(f"launched {lead['name']} -> {run_id}", flush=True)
        time.sleep(3)

    poll(clay, args.workflow, runs)
    print("BATCH SUMMARY:")
    print(json.dumps(runs, indent=1))


if __name__ == "__main__":
    sys.exit(main())
