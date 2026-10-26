#!/usr/bin/env python3
"""Launch a list of leads through the campaign workflow and poll to completion.

Usage: batch_run.py <leads.json> [workflowId]

leads.json format:
  [{"name": "Jane Doe (CFO, Acme)", "url": "https://www.linkedin.com/in/janedoe/"}, ...]
"""
import glob
import json
import os
import subprocess
import sys
import time

WF = sys.argv[2] if len(sys.argv) > 2 else "wf_YOUR_WORKFLOW_ID"


def newest_clay() -> str:
    candidates = glob.glob(os.path.expanduser(
        "~/.claude/plugins/cache/clay-plugins/clay/*/bin/clay"))
    if not candidates:
        sys.exit("no clay launcher found in plugin cache")
    return max(candidates, key=os.path.getmtime)


CLAY = newest_clay()

leads = json.load(open(sys.argv[1]))
runs = {}
for lead in leads:
    out = subprocess.run([CLAY, "workflows", "runs", "test", WF, "--input", "-"],
                         input=json.dumps({"linkedin_url": lead["url"]}),
                         capture_output=True, text=True)
    try:
        rid = json.loads(out.stdout).get("runId")
    except Exception:
        rid = None
    runs[lead["name"]] = {"runId": rid, "url": lead["url"]}
    print(f"launched {lead['name']} -> {rid}", flush=True)
    time.sleep(3)

deadline = time.time() + 50 * 60
while time.time() < deadline:
    pending = False
    for name, info in runs.items():
        if info.get("status") in ("completed", "failed") or not info.get("runId"):
            continue
        st = subprocess.run([CLAY, "workflows", "runs", "get", WF, info["runId"]],
                            capture_output=True, text=True)
        try:
            d = json.loads(st.stdout)
        except Exception:
            continue
        if d.get("status") in ("completed", "failed"):
            info["status"] = d.get("status")
            info["error"] = (d.get("error") or "")[:150]
            info["credits"] = round((d.get("dataCreditsUsed") or 0)
                                    + (d.get("actionCreditsUsed") or 0), 1)
            info["steps"] = (d.get("progress") or {}).get("completed")
            print(f"DONE {name}: {info['status']} steps={info['steps']} "
                  f"credits={info['credits']} {info['error']}", flush=True)
        else:
            pending = True
    if not pending:
        break
    time.sleep(45)

print("BATCH SUMMARY:")
print(json.dumps(runs, indent=1))
