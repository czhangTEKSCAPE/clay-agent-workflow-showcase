#!/usr/bin/env python3
"""Shared helpers for building Clay workflows through the CLI.

Imported by per-campaign builder scripts (not included in this extract). Each builder makes two passes:
create every node without edges (ids cached in tools/workflow_code/<name>_nodes.json so re-runs are
idempotent), then update each node with incomingEdges, inputSchema pins and the tool's inputMappingConfig.
"""
import json, os, subprocess, sys

from clay_cli import find_clay

CODE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow_code")
PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")

ZB = ("validate-email", "8f0d2dc0-a6b4-4b84-9aad-a330b4a4586a", "aa_YOUR_CONNECTION_ID")
TRESTLE = ("trestle-validate-number-v2", "a9a43f95-a65f-4a01-bed4-748359d21efa", "aa_YOUR_CONNECTION_ID")
# Carrier = a free utility that echoes its input, used to join exclusive branches. 2026-10-14: Clay's text-utilities
# package (find-urls-and-emails-in-text, 4299091f…) failed every call (ERROR_LAMBDA_FUNCTION); normalize-company-name
# returns the input unchanged in result.original_name, so it carries text and emails just as well.
CARRIER = ("normalize-company-name", "6c973999-fb78-4a5a-8d99-d2fee5b73878")
CARRIER_PARAM = "companyName"
CARRIER_OUT = "$.result.original_name"
NORMALIZE = ("normalize-phone-number", "6c973999-fb78-4a5a-8d99-d2fee5b73878")
HS = ("a2584689-b965-4a25-847d-17b7abcddca3", "aa_YOUR_CONNECTION_ID")   # your HubSpot connection in Clay
CPJ = "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2"
HG = "b7f3454a-5095-4cb2-b91b-79cdb54e0dd2"
HUBSPOT_OWNER = "YOUR_HUBSPOT_OWNER_ID"
# (key, actionKey, packageId, appAccountId, mapping{param: prep-field or ("email", output-field)}, output path)
EMAIL = [
    ("prospeo", "prospeo-find-work-email-v2", "48a31bbb-63e6-4461-8a62-d88bb2cd6b0f", "aa_YOUR_CONNECTION_ID",
     {"full_name": "full_name", "company_domain": "domain"}, "$.result.email"),
    ("dropcontact", "dropcontact-find-work-email", "6ddf27b7-ad83-4419-be62-c83f9c9e34a7", "aa_YOUR_CONNECTION_ID",
     {"full_name": "full_name", "website": "domain", "company": "company_name"}, "$.result.email[0].email"),
    ("datagma", "datagma-find-work-email-v3", "f240a97e-3d3e-4ffa-a85e-8d70afe348a5", "aa_YOUR_CONNECTION_ID",
     {"full_name": "full_name", "company_domain": "domain"}, "$.result.email"),
    ("findymail", "findymail-find-work-email", "9515bb04-4267-4074-94eb-653545c3c38f", "aa_YOUR_CONNECTION_ID",
     {"full_name": "full_name", "company_domain": "domain"}, "$.result.email"),
    ("hunter", "find-email-v2", "9cfc7721-5c91-423b-a0b0-4cc1f42c6089", "aa_YOUR_CONNECTION_ID",
     {"full_name": "full_name", "domain": "domain"}, "$.result.email"),
    ("fullenrich", "fullenrich-find-work-email", "a1f0f6b6-f98a-42e3-bfe0-ddfc333d0df1", "aa_YOUR_CONNECTION_ID",
     {"linkedin_url": "linkedin_url", "full_name": "full_name", "domain": "domain", "company_name": "company_name"},
     "$.result.most_probable_email"),
]
MOBILE = [
    ("bettercontact", "bettercontact-find-mobile-phone", "0371b274-8f45-4a0a-944a-e88c81dfa7eb", "aa_YOUR_CONNECTION_ID",
     {"social_url": "linkedin_url", "name": "full_name", "company": "company_name", "domain": "domain"},
     "$.result.data[0].contact_phone_number"),
    ("fullenrich", "fullenrich-find-mobile-phone", "a1f0f6b6-f98a-42e3-bfe0-ddfc333d0df1", "aa_YOUR_CONNECTION_ID",
     {"linkedin_url": "linkedin_url", "full_name": "full_name", "company_name": "company_name", "domain": "domain"},
     "$.result.most_probable_phone"),
    ("datagma", "datagma-find-mobile-number", "f240a97e-3d3e-4ffa-a85e-8d70afe348a5", "aa_YOUR_CONNECTION_ID",
     {"email": ("email", "work_email"), "personal_linkedin_url": "linkedin_url"}, "$.result.displayInternational"),
]


CLAY = find_clay()  # None when the CLI is absent, so the module stays importable; cli() fails with a clear message


def cli(*args, inp=None, flag="--input", retries=3):
    """Run a clay CLI command and parse its JSON. Transient server errors (HTTP 504, "Terracotta could not complete this request",
    seen 2026-10-20) are retried up to `retries` times with a short backoff; any other error exits."""
    import time as _time
    if not CLAY:
        sys.exit("clay CLI not found: install it and run `clay whoami`")
    cmd = [CLAY, *args] + ([flag, "-"] if inp is not None else [])
    for attempt in range(retries + 1):
        out = subprocess.run(cmd, input=json.dumps(inp) if inp is not None else None, capture_output=True, text=True)
        try:
            d = json.loads(out.stdout or out.stderr)
        except Exception:
            sys.exit(f"{' '.join(args)} failed: {out.stdout[:400]} {out.stderr[:400]}")
        err = d.get("error") if isinstance(d, dict) else None
        if err and err.get("code") == "server_error" and attempt < retries:
            print(f"retry {attempt + 1}/{retries} after server_error on {' '.join(args[:3])}: {err.get('message')}", file=sys.stderr, flush=True)
            _time.sleep(3 * (attempt + 1))
            continue
        if err:
            sys.exit(f"{' '.join(args)} error: {json.dumps(err)[:600]}")
        return d


def pin(src, path, typ="string"):
    return {"type": typ, "sourceNodeId": src, "sourcePath": path}


def schema(props, required=None):
    return {"type": "object", "required": required if required is not None else list(props), "properties": props}


def ref(v):
    return {"type": "reference", "expression": "{{%s}}" % v}


def static(v):
    return {"type": "static", "value": v}


def coalesce(*cands):
    return {"type": "coalesce", "candidates": list(cands)}


def flat(desc):
    return {k: {"type": "string", "description": v} for k, v in desc.items()}


def read(path):
    return open(path).read()


class Builder:
    """Node factory with cached ids. `create` is a no-op for keys already in the ids file."""

    def __init__(self, wf, ids_path):
        self.wf, self.ids_path = wf, ids_path
        self.ids = json.load(open(ids_path)) if os.path.exists(ids_path) else {}

    def create(self, key, payload):
        if key in self.ids:
            return self.ids[key]
        d = cli("workflows", "nodes", "create", self.wf, inp=payload)
        self.ids[key] = d["nodeId"]
        json.dump(self.ids, open(self.ids_path, "w"), indent=1)
        print(f"created {key:<18} {d['nodeId']}", flush=True)
        return self.ids[key]

    def upd(self, key, payload):
        cli("workflows", "nodes", "update", self.wf, self.ids[key], inp=payload)
        print(f"wired   {key}", flush=True)

    def code(self, key, name, code_file, out_file):
        return self.create(key, {"nodeType": "code", "name": name, "code": read(os.path.join(CODE_DIR, code_file)),
                                 "outputSchema": json.load(open(os.path.join(CODE_DIR, out_file)))})

    def refresh_code(self, key, code_file, out_file):
        self.upd(key, {"code": read(os.path.join(CODE_DIR, code_file)),
                       "outputSchema": json.load(open(os.path.join(CODE_DIR, out_file)))})

    def tool(self, key, name, action, pkg, acct=None):
        t = {"toolType": "clay_action", "actionKey": action, "actionPackageId": pkg, "inputMappingConfig": {}}
        if acct:
            t["appAccountId"] = acct
        return self.create(key, {"nodeType": "tool", "name": name, "tools": [t]})

    def rules(self, key, name, rule_id, rule_name, items, mode="And", end_on_no_match=False):
        cfg = {"rules": [{"id": rule_id, "name": rule_name,
                          "condition": {"type": "GroupOp", "combinationMode": mode, "items": items}}]}
        if end_on_no_match:
            cfg["endRunOnNoMatch"] = True
        return self.create(key, {"nodeType": "conditional", "name": name, "conditionalMode": "rules",
                                 "inputSchema": {"type": "object", "properties": {}}, "rulesConditionalConfig": cfg})

    def agent(self, key, name, agent_name, prompt, model, out_desc):
        return self.create(key, {"nodeType": "agent", "name": name, "agentName": agent_name, "agentPrompt": prompt,
                                 "agentModel": model, "outputSchema": flat(out_desc)})

    def toolcfg(self, action, pkg, mapping, acct=None):
        t = {"toolType": "clay_action", "actionKey": action, "actionPackageId": pkg, "inputMappingConfig": mapping}
        if acct:
            t["appAccountId"] = acct
        return [t]

    def carrier(self, key, edges, text):
        self.upd(key, {"incomingEdges": edges,
                       "tools": self.toolcfg(CARRIER[0], CARRIER[1], {CARRIER_PARAM: static(text)})})


def bin_op(path, op, value=None):
    d = {"type": "BinOp", "dataPath": [path], "operator": op}
    if value is not None:
        d["value"] = value
    return d


PREP_FIELDS = ["domain", "company_name", "website", "full_name", "first_name", "last_name", "title", "linkedin_url",
               "contact_location", "hubspot_contact_id", "band", "rep_name", "territory"]


def build_email_mobile_waterfalls(b, trig, trigger_fields, prep_code, prep_out, output_code, output_out,
                                  phones_items=None, phones_pins=None, prep_out_fields=None, prep_required=("domain",)):
    """Create + wire: Prep Contact → email waterfall → Email Result → phones gate → mobile waterfall →
    Enrichment Output. Returns the ids dict.
    phones_items / phones_pins: rule items and extra pins for the "Include phones?" gate (defaults: include_phones True).
    prep_out_fields: Prep Contact fields passed through to Enrichment Output (default PREP_FIELDS)."""
    # ---- pass 1: create ----
    b.code("prep", "Prep Contact", prep_code, prep_out)
    b.rules("g_hs", "Has HubSpot email?", "has_hs", "HubSpot email present", [bin_op("has_hs_email", "True")])
    b.tool("c_hubspot", "Carry Email (HubSpot)", *CARRIER)
    for i, (k, action, pkg, acct, _m, _o) in enumerate(EMAIL, 1):
        b.tool(f"f_{k}", f"Find Work Email {i} ({k})", action, pkg, acct)
        b.rules(f"fg_{k}", f"Found Email? {i} ({k})", f"found_{k}", "Email found", [bin_op("found_email", "Contain", "@")])
        b.tool(f"v_{k}", f"Validate Email {i} (ZeroBounce)", *ZB)
        b.rules(f"vg_{k}", f"Email Valid? {i} ({k})", f"valid_{k}", "ZeroBounce valid, not greylisted",
                [bin_op("zb_status", "Equal", "valid"), bin_op("zb_sub_status", "NotEqual", "greylisted")])
        b.tool(f"c_{k}", f"Carry Email {i} ({k})", *CARRIER)
    b.tool("c_noemail", "No Email (pass)", *CARRIER)
    b.code("email_result", "Email Result", "p2_email_result.py", "p2_email_outputs.json")
    b.rules("g_phones", "Include phones?", "phones", "Mobile waterfall on",
            phones_items or [bin_op("include_phones", "True")])
    for j, (k, action, pkg, acct, _m, _o) in enumerate(MOBILE, 1):
        b.tool(f"m_{k}", f"Find Mobile {j} ({k})", action, pkg, acct)
        b.rules(f"mg_{k}", f"Found Mobile? {j} ({k})", f"mfound_{k}", "Mobile found",
                [bin_op("found_phone", "ContainAny", list("0123456789"))])
        b.tool(f"t_{k}", f"Validate Mobile {j} (Trestle)", *TRESTLE)
        b.rules(f"tg_{k}", f"Mobile Valid? {j} ({k})", f"mvalid_{k}", "Trestle valid mobile",
                [bin_op("tv_valid", "True"), bin_op("tv_line_type", "ContainAny", ["Mobile", "mobile"])])
        b.tool(f"mc_{k}", f"Carry Mobile {j} ({k})", *NORMALIZE)
    b.tool("c_nomobile", "No Mobile (pass)", *CARRIER)
    b.code("output", "Enrichment Output", output_code, output_out)

    # ---- pass 2: wire ----
    ids = b.ids
    P = ids["prep"]

    def prep_pins(fields):
        return {f: pin(P, f"$.{f}") for f in fields}

    b.upd("prep", {"incomingEdges": [{"sourceNode": trig}],
                   "inputSchema": schema({f: pin(trig, f"$.{f}") for f in trigger_fields}, required=list(prep_required))})
    b.upd("g_hs", {"incomingEdges": [{"sourceNode": P}], "inputSchema": schema({"has_hs_email": pin(P, "$.has_hs_email", "boolean")})})
    b.upd("c_hubspot", {"incomingEdges": [{"sourceNode": ids["g_hs"], "ruleId": "has_hs"}],
                        "inputSchema": schema({"addr": pin(P, "$.hubspot_email")}),
                        "tools": b.toolcfg(CARRIER[0], CARRIER[1], {CARRIER_PARAM: ref("addr")})})
    prev_defaults = [{"sourceNode": ids["g_hs"], "isDefaultRoute": True}]
    for i, (k, action, pkg, acct, mapping, outpath) in enumerate(EMAIL, 1):
        mp = {p: ref(f) for p, f in mapping.items()}
        b.upd(f"f_{k}", {"incomingEdges": prev_defaults, "inputSchema": schema(prep_pins(sorted(set(mapping.values()))), required=[]),
                         "tools": b.toolcfg(action, pkg, mp, acct)})
        b.upd(f"fg_{k}", {"incomingEdges": [{"sourceNode": ids[f"f_{k}"]}], "inputSchema": schema({"found_email": pin(ids[f"f_{k}"], outpath)}, required=[])})
        b.upd(f"v_{k}", {"incomingEdges": [{"sourceNode": ids[f"fg_{k}"], "ruleId": f"found_{k}"}],
                         "inputSchema": schema({"email": pin(ids[f"f_{k}"], outpath)}),
                         "tools": b.toolcfg(ZB[0], ZB[1], {"email": ref("email")}, ZB[2])})
        b.upd(f"vg_{k}", {"incomingEdges": [{"sourceNode": ids[f"v_{k}"]}],
                          "inputSchema": schema({"zb_status": pin(ids[f"v_{k}"], "$.result.status"), "zb_sub_status": pin(ids[f"v_{k}"], "$.result.sub_status")}, required=[])})  # empty validator response → default route (next provider)
        b.upd(f"c_{k}", {"incomingEdges": [{"sourceNode": ids[f"vg_{k}"], "ruleId": f"valid_{k}"}],
                         "inputSchema": schema({"addr": pin(ids[f"v_{k}"], "$.result.address")}),
                         "tools": b.toolcfg(CARRIER[0], CARRIER[1], {CARRIER_PARAM: ref("addr")})})
        prev_defaults = [{"sourceNode": ids[f"fg_{k}"], "isDefaultRoute": True}, {"sourceNode": ids[f"vg_{k}"], "isDefaultRoute": True}]
    b.carrier("c_noemail", prev_defaults, "no email found")
    carriers = ["c_hubspot"] + [f"c_{k}" for k, *_ in EMAIL] + ["c_noemail"]
    email_pins = {"email_hubspot": pin(ids["c_hubspot"], CARRIER_OUT)}
    email_pins.update({f"email_{k}": pin(ids[f"c_{k}"], CARRIER_OUT) for k, *_ in EMAIL})
    b.upd("email_result", {"incomingEdges": [{"sourceNode": ids[c]} for c in carriers], "inputSchema": schema(email_pins, required=[])})
    E = ids["email_result"]
    gp = {"include_phones": pin(P, "$.include_phones", "boolean")}
    for k, (src, path, typ) in (phones_pins or {}).items():
        gp[k] = pin({"prep": P, "email": E}[src], path, typ)
    b.upd("g_phones", {"incomingEdges": [{"sourceNode": E}], "inputSchema": schema(gp, required=["include_phones"])})
    prev_defaults = [{"sourceNode": ids["g_phones"], "isDefaultRoute": True}]
    for j, (k, action, pkg, acct, mapping, outpath) in enumerate(MOBILE, 1):
        pins, mp = {}, {}
        for p, f in mapping.items():
            if isinstance(f, tuple):
                pins[f[1]] = pin(E, f"$.{f[1]}"); mp[p] = ref(f[1])
            else:
                pins[f] = pin(P, f"$.{f}"); mp[p] = ref(f)
        edges = [{"sourceNode": ids["g_phones"], "ruleId": "phones"}] if j == 1 else prev_defaults
        b.upd(f"m_{k}", {"incomingEdges": edges, "inputSchema": schema(pins, required=[]), "tools": b.toolcfg(action, pkg, mp, acct)})
        b.upd(f"mg_{k}", {"incomingEdges": [{"sourceNode": ids[f"m_{k}"]}], "inputSchema": schema({"found_phone": pin(ids[f"m_{k}"], outpath)}, required=[])})
        b.upd(f"t_{k}", {"incomingEdges": [{"sourceNode": ids[f"mg_{k}"], "ruleId": f"mfound_{k}"}],
                         "inputSchema": schema({"phone": pin(ids[f"m_{k}"], outpath)}),
                         "tools": b.toolcfg(TRESTLE[0], TRESTLE[1], {"phone": ref("phone")}, TRESTLE[2])})
        b.upd(f"tg_{k}", {"incomingEdges": [{"sourceNode": ids[f"t_{k}"]}],
                          "inputSchema": schema({"tv_valid": pin(ids[f"t_{k}"], "$.result.is_valid", "boolean"), "tv_line_type": pin(ids[f"t_{k}"], "$.result.line_type")}, required=[])})  # Trestle miss → default route, not a run failure
        b.upd(f"mc_{k}", {"incomingEdges": [{"sourceNode": ids[f"tg_{k}"], "ruleId": f"mvalid_{k}"}],
                          "inputSchema": schema({"phone": pin(ids[f"t_{k}"], "$.result.phone_number")}),
                          "tools": b.toolcfg(NORMALIZE[0], NORMALIZE[1], {"phoneNumber": ref("phone"), "countryCode": static("US")})})
        prev_defaults = [{"sourceNode": ids[f"mg_{k}"], "isDefaultRoute": True}, {"sourceNode": ids[f"tg_{k}"], "isDefaultRoute": True}]
    b.carrier("c_nomobile", [{"sourceNode": ids["g_phones"], "isDefaultRoute": True}] + prev_defaults, "no mobile found")
    out_pins = {f: pin(P, f"$.{f}") for f in (prep_out_fields or PREP_FIELDS)}
    out_pins.update({f: pin(E, f"$.{f}") for f in ["work_email", "email_provider", "email_status"]})
    out_pins.update({f"mobile_{k}": pin(ids[f"mc_{k}"], "$.result.number.e164") for k, *_ in MOBILE})
    b.upd("output", {"incomingEdges": [{"sourceNode": ids[f"mc_{k}"]} for k, *_ in MOBILE] + [{"sourceNode": ids["c_nomobile"]}],
                     "inputSchema": schema(out_pins, required=[])})
    return ids


def start_run(wf, payload, approve=False):
    """Start a manual-trigger test run. When the workspace requires spend approval and approve=True (the human authorized this
    batch), approve ONLY the request that this call just created, and only if it is a workflows.run of `wf`. → (runId, info)."""
    out = subprocess.run([CLAY, "workflows", "runs", "test", wf, "--inputs", "-"], input=json.dumps(payload), capture_output=True, text=True)
    try:
        d = json.loads(out.stdout or out.stderr)
    except Exception:
        return None, (out.stdout + out.stderr)[:200]
    if d.get("runId"):
        return d["runId"], "started"
    err = d.get("error") or {}
    if err.get("code") != "approval_required":
        return None, json.dumps(err)[:200]
    det = err.get("details") or {}
    rid = det.get("actionApprovalRequestId")
    if not approve:
        return None, "approval required (%s); re-run with --approve once the human authorizes this batch" % rid
    if det.get("action") != "workflows.run" or (det.get("input") or {}).get("workflowId") != wf:
        return None, "refusing to approve %s: not a run of %s" % (rid, wf)
    a = subprocess.run([CLAY, "approvals", "approve", rid], capture_output=True, text=True)
    try:
        g = json.loads(subprocess.run([CLAY, "approvals", "get", rid], capture_output=True, text=True).stdout)
        run_id = (((g.get("result") or {}).get("body") or {}).get("workflowRun") or {}).get("id")
    except Exception:
        run_id = None
    return run_id, "approved %s" % rid
