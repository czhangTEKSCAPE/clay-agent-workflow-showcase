# Clay Workflow Editor API — Field Notes

Behavior of the Clay workflow MCP surface (`edit_node` / `validate_workflow` /
run engine), discovered across ~20 test runs while building the Managed AI
Services campaign (plugin 2.1.13 → 2.1.21, July–August 2026). The docs don't
tell you most of this.

## Node creation & schemas

- **Conditional rule conditions MUST be wrapped in a `GroupOp`** — a bare
  top-level `BinOp` is rejected with "Invalid node config".
- **A node's engine `nodeConfig.inputSchema` is effectively immutable after
  creation.** Updates via `edit_node` change `inputRefs`, but the stored schema
  (and its `required` list) persists. Changing the linked Claygent (new
  `agentName`) regenerates the *agent's* variables but NOT the node schema.
  To truly change an agent node's inputs: **create a fresh node and rewire
  every dependent** (edges, conditional variables, downstream pins).
- **Conditionals need an `inputSchema`** or validation fails
  (`conditional_rules_no_input_schema`). Use FULL FORM with `required: []`
  whenever the pinned value can be missing — the ≥2.1.21 runtime enforces
  required-input checks *before* soft variable resolution and hard-fails the run.
- Conditional node-level `inputRefs` don't overwrite on same-name update:
  clear first (`inputSchema: null`) then re-set. The clear can silently no-op
  ("operation: noop") — re-issue it and verify via a snapshot.

## Data passing

- **Agent pins work at runtime** (they persist even though `read` doesn't render
  them), but every `{{var}}` in the prompt becomes a REQUIRED input. Pin only
  from sources that always execute and always emit the field.
- **Agent `structuredOutputs` silently drop empty-string fields** → downstream
  refs resolve undefined → required-input crash. Use a `'none'` sentinel
  instead of empty strings (and tell downstream prompts what `'none'` means).
- **Conditionals output only their routing decision** (`conditionalEvaluation`).
  An agent directly after a conditional receives NOTHING via automap.
- **Automap fills only DECLARED prompt variables**, from the immediate
  predecessor's output. A prompt with no `{{vars}}` receives nothing, even
  though the node-level `inputs` context shows the data.
- **The carrier-convergence pattern** (the reliable way to join exclusive
  branches): each branch's gate routes to a free tool node ("carrier", e.g.
  `find-urls-and-emails-in-text`, `normalize-phone-number`, `normalize-url`)
  pinned to that branch's data, and all carriers feed ONE downstream node.
  Tool-node pins to never-executed nodes resolve softly; unresolved template
  refs remain as literal `{{x}}` text (extraction-type carriers filter those out).
- `reference` expressions in `inputMappingConfig` support multi-variable
  templates with literal text (whole prompts can be templates).
- Tool-node outputs live at `$.toolResult.result.<field>` in pin paths, even
  though run traces render them as top-level `{result, success, textPreview}`.

## Rules & operators

- **`NotEmpty` matches undefined** (stringifies to `"undefined"`). Gate on
  content instead: `Contain "@"` for emails, `ContainAny ["0".."9"]` for phones.
- **`ContainAny` is substring matching** — bare acronyms false-positive
  ("Direc**TO**r" matches "CTO"). Use full phrases in rules and normalize/expand
  acronyms upstream in a prep agent.

## Tools & actions

- **`inputMappingConfig` is shared per actionKey across all nodes using it.**
  Two nodes needing different configs must make the mapping parametric:
  reference variables whose values are per-node pinned constants emitted by
  upstream agents (e.g. `hs_object_type` = "0-2" vs "0-1").
- **`use-ai` can no longer be created or edited as a tool node** (≥2.1.21:
  "Use a Claygent node instead"). Existing ones are grandfathered but frozen.
- Required action params fed by refs that resolve undefined fail the node
  (≥2.1.21). Guard every provider→consumer hop with a found-gate conditional.
- HubSpot lookup accepts pipe-flattened inputs (`fields|domain`) and
  `fieldsToFilterBy` as a plain string.
- Don't hardcode Trestle `country_code` — international numbers error with
  "Phone number and country code do not match".

- Node `retryConfig` is stored as `{"maxToolCallFailures": N}` (0 = fail the run on the first tool error). Any
  other key you send is accepted but normalized away; set it explicitly on provider nodes that hiccup (news, social).

- **Carrier outage (2026-10-14):** the whole text-utilities package (`find-urls-and-emails-in-text`,
  `normalize-and-deduplicate-list`, pkg `4299091f…`) failed every call with `ERROR_LAMBDA_FUNCTION` / "Action
  execution failed", killing any run at a carrier node. `normalize-company-name` (pkg `6c973999…`) echoes its input
  unchanged in `result.original_name`, so it is now the carrier in `tools/clay_build.py` (`CARRIER`, `CARRIER_PARAM`,
  `CARRIER_OUT`). A campaign workflow built with the old carrier still uses the old carrier; re-run its builder
  (now a wrapper over clay_build) before using it again. Test a free action with `clay workflows actions test` first
  when a run fails at a utility node.

## Run engine

- **Join deadlock:** a node with parents {regular node, conditional-default}
  hangs forever in `waiting` when reached via the regular parent. Restructure
  with exclusive carriers so all parents are regular nodes.
- Enrichment providers returning `success` with empty `result: {}` are normal
  (misses, refunded). Design prep agents to tolerate `{}` explicitly ("never
  fail, never ask for data").
- `runs test` + `runs get --verbose` show per-node inputs/mappedParameters/
  outputs — the primary debugging tool.
- PDL occasionally returns a profile without `job_title` — a simple retry can
  succeed.
- New workflows (≥2.1.21) start with NO trigger node; create one via
  `surfaces_edit_trigger` (`clay_table` triggers are UI-only).

## Claude Code plugin quirks

- The plugin's MCP tools don't register in Claude Code sessions (reported
  2026-07-14). Workaround: drive `clay mcp` over stdio (`tools/clay_mcp_call.py`).
- The plugin pins the CLI version; `clay update` refuses — update the plugin
  (`claude plugin update clay@clay-plugins`).
