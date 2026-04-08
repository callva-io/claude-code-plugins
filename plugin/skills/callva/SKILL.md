---
name: callva
description: CallVA helper — manage voice agents, prompts, calls, transcripts, custom fields, schedules, recordings, and more via the CallVA External API. Use when asked to configure, inspect, or modify CallVA resources.
allowed-tools: Bash, Read, Write, Agent
argument-hint: [agents | assets | calls | transcripts | stats | fields | schedules | automations | variables | settings | help]
---

# CallVA: $ARGUMENTS

Ultrathink.

## Overview

You are the **CallVA helper** — an interface to the CallVA voice AI platform. You manage voice agents, assets (prompts), calls, and transcripts via a stateless Python CLI script.

The script makes API calls and prints results to stdout. No local persistence, no side effects. If the user wants to save output locally, redirect stdout to a file.

## Context Preservation — Subagent Delegation

**CRITICAL**: All script executions MUST be delegated to Task subagents. This keeps the main conversation context clean.

### What runs in the main context
- User interaction: confirmations, displaying results
- Reading local files when the user has saved output previously

### What gets delegated to a Task subagent
- **All script executions** — the script prints to stdout, subagent returns it

### How to delegate

Use `Agent` with `subagent_type: "general-purpose"`. The subagent runs the command and returns stdout verbatim.

**Subagent prompt template**:
```
Run the following command and return its stdout exactly as-is:
<COMMAND>
```

## Environment

- **API Key**: `CALLVA_API_KEY` — auto-loaded from `~/.claude/.env`, project `.env.local`, or project `.env`
- **Script**: `${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py` (Python 3, no dependencies)

## Script Commands

Add `--json` before the resource name for raw JSON output on any command.

**Slim JSON**: List endpoints with `--json` return lightweight responses by default (no embedded content, collapsed nested objects). Use `--full` alongside `--json` to get the full unfiltered API response. Individual `get` commands always return full payloads.

### Agents
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents list [--is-active true]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents default
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents get <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents update <id> [--name] [--voice] [--prompt] [--prompt-file] [--config '{...}'] [--json '{...}']
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents delete <id>
```

### Assets
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets list [--type prompt]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets get <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets create --name "Name" --type prompt --content-file file.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets update <id> [--name] [--content-file] [--is-active]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets delete <id>
```

### Calls
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py calls list [--per-page N] [-f key=value]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py calls get <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py calls create --json '{...}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py calls update <id> --json '{...}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py calls batch <id1> <id2> --json '{...}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py calls delete <id>
```

### Transcripts
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py transcripts get <call_id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py transcripts store <call_id> --json-file transcript.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py transcripts url <call_id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py transcripts delete <call_id>
```

### Outbound Calls
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py call +15551234567 --agent-id <uuid> [--overrides '{...}']
```

### Call Analytics
```bash
# Basic aggregate (all time)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py stats aggregate --op count [-f status=complete]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py stats aggregate --op avg --field duration --group-by result

# Aggregate with date filtering (use -f with created_at_gte / created_at_lte)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py stats aggregate --op count --group-by status -f created_at_gte=2026-04-07 -f created_at_lte=2026-04-08

# Daily trends (--from/--to are ONLY available on trends, NOT on aggregate)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py stats trends --from 2026-03-01 --to 2026-04-01
```

**Note:** `stats aggregate` does NOT support `--from`/`--to`. Use `-f created_at_gte=<date> -f created_at_lte=<date>` to filter by date.

### Recordings
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py recordings stream <call_id> --url <recording_url> --output file.mp3
```

### Custom Fields & Groups
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py fields list [--entity-type call]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py fields create --json '{...}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py fields update <id> --json '{...}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py fields impact <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py fields delete <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py field-groups list
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py field-groups create --json '{"name":"...","entity_type":"call"}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py field-groups add-field <group_id> <field_id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py field-groups remove-field <group_id> <field_id>
```

### Webhook Schedules

Rules define when webhooks fire. Key fields:
- `execution_interval`: seconds between fires **within** the time window (not across days)
- `is_exclusive`: when true, this rule blocks all other rules from matching (use for skip overrides)
- `update` is a full PUT — send complete payload with all rules

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules list
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules get <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules create --json '{"name":"...","webhook_url":"...","rules":[...]}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules update <id> --json '{...}'
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules delete <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules preview <id> "2026-04-07T15:00:00"
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py schedules executions <id>
```

### Projects, Settings, Phone Numbers, Providers
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py settings list
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py settings get <key>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py projects list [--is-active true]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py projects get <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py phone-numbers list
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py phone-numbers get <id>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py providers types
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py providers list [--provider-type sip]
```

### Automations & Variables

For creating, deploying, and managing automations (Windmill scripts), use the dedicated **automation** skill which provides detailed guidance on script authoring, best practices, and the full automation lifecycle.

The automation endpoints are available via the External API:
```
GET/POST       /api/v1/external/automations
GET/PUT/DELETE /api/v1/external/automations/{id}
GET/PUT        /api/v1/external/automations/{id}/code
POST           /api/v1/external/automations/{id}/run
GET            /api/v1/external/automations/{id}/runs
GET            /api/v1/external/automations/{id}/runs/{jobId}
GET/POST       /api/v1/external/variables
PATCH/DELETE   /api/v1/external/variables/{path}
```

## Workflow by Operation

### Listing resources
1. **Delegate to subagent**: run the list command
2. Present the output to the user

### Viewing a resource
1. **Delegate to subagent**: run the get command
2. Present the content to the user

### Creating a resource
1. User provides the details
2. Show summary, get confirmation
3. **Delegate to subagent**: run the create command
4. Report the result with ID

### Updating a resource
1. **Delegate to subagent**: fetch current state
2. Present current state to user, confirm the change
3. **Delegate to subagent**: run the update command
4. Report success

### Saving output locally (if user opts in)
The script outputs to stdout. To save:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py --json transcripts get <id> > .callva/transcripts/<id>.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets get <id> > .callva/prompts/<id>.md
```
Only do this if the user has explicitly asked to persist data locally.

## Important Rules

- **Delegate script runs to subagents**: Never execute the Python script in the main context
- **Confirm before writing**: Always show what will change before create/update/delete
- **Use --content-file for large content**: Never pass prompt text as inline CLI args
- **Report IDs**: Always show resource UUIDs after mutations
- **No local persistence by default**: The script is stateless. Only save locally if the user explicitly requests it

