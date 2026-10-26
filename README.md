# Clay Agent Workflow

A GTM workbench for running AI-assisted outbound on [Clay](https://clay.com), driven from the
Clay CLI and Claude Code. This repo is a sanitized extract of the tooling: the reusable builders,
runners and API notes, without any customer or prospect data.

The pattern it implements:

```
signal source ─▶ qualify account ─▶ find the right contacts ─▶ enrich (email, mobile, HQ phone)
      ─▶ research agent ─▶ sequence writer ─▶ human review ─▶ CRM upsert ─▶ sales-engagement flow
```

## Design principles

- **Gate before you spend.** Free filters and qualification run first, so paid research and enrichment only touch survivors.
- **Waterfall enrichment with validation.** Several providers in sequence, each result validated before it is accepted.
- **Humans approve what sends.** Samples are reviewed before any contact is enrolled, and spend is approved per batch.
- **Dedupe against the CRM before every write**, and honor opt-outs everywhere.

## What's here

| Path | Purpose |
|---|---|
| `tools/clay_build.py` | Shared workflow builder: node factory, email and mobile waterfalls, CRM write nodes |
| `tools/wf_batch.py` | Generic CSV-to-workflow batch runner with field mapping |
| `tools/batch_run.py` | Launch and poll a list of leads through a workflow |
| `tools/clay_mcp_call.py` | stdio JSON-RPC bridge to Clay's local MCP server, for scripting its tools |
| `tools/code_test_local.py` | Run a workflow code node locally when the CLI's daily test cap is hit |
| `searches/` | Example saved ICP people-search filters |
| `docs/clay-workflow-api-learnings.md` | How the Clay workflow-editor API actually behaves, including failure modes that cost credits |

IDs in `clay_build.py` (connections, owner) are placeholders. Replace them with your own workspace's values.

## Quickstart

```bash
clay whoami && clay credits balance
clay search filters-mode create --source-type people --filters "$(cat searches/icp-new-exec-hires.json)"
python3 tools/batch_run.py leads.json wf_YOUR_WORKFLOW_ID
```

## Requirements

Python 3, the [Clay CLI](https://clay.com), and a Clay workspace.
