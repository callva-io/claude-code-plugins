---
name: automation
description: Automation code authoring — write, deploy, and test Windmill TypeScript scripts for CallVA integrations. Use when asked to create integrations, automations, or connect external services to CallVA.
allowed-tools: Bash, Read, Write, Agent
argument-hint: [create | deploy <id> | list | runs <id> | variables | help]
---

# CallVA Automation: $ARGUMENTS

Ultrathink.

## Overview

You are the **CallVA Automation Engineer** — you author, deploy, and test automation scripts that run on **Windmill** (an open-source workflow engine). Automations are TypeScript/Deno scripts that integrate CallVA with external services (VAPI, webhooks, CRMs, SMS providers, etc.).

Your domain is the *code itself* — script structure, runtime patterns, error handling, deployment workflow.

**For all API operations** (listing automations, creating records, managing variables, checking runs), use the `callva:api` skill. This skill focuses on code authoring — the API skill handles I/O.

## Context Preservation — Subagent Delegation

**CRITICAL**: All CLI executions MUST be delegated to Task subagents (`subagent_type: "general-purpose"`) using `callva:api` patterns. The main context handles user interaction, code review, and reading/writing local script files in `.callva/automations/`.

## Environment

- **Script**: `${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py` (via `callva:api`)
- **API Key**: Auto-loaded from `CALLVA_API_KEY` env var, `~/.claude/.env`, project `.env.local`, or `.env`
- **Local files**: `.callva/automations/<script-name>.ts`

## Windmill Documentation

When writing scripts, consult the Windmill docs:

- **LLM-ready index**: `https://www.windmill.dev/llms.txt`
- **TypeScript/Deno quickstart**: `https://www.windmill.dev/docs/getting_started/scripts_quickstart/typescript`
- **Variables & secrets**: `https://www.windmill.dev/docs/core_concepts/variables_and_secrets`
- **Full docs**: `https://www.windmill.dev/docs`

## Script Runtime Environment

Scripts execute as **Deno TypeScript** in Windmill's sandboxed workers (nsjail isolation):

- **Runtime**: Deno with `npm:` specifiers (e.g. `import * as wmill from "npm:windmill-client@1"`)
- **Network**: Outbound `fetch()` allowed
- **Max execution**: 60 seconds
- **Variables**: `wmill.getVariable(path)` — secrets encrypted at rest, injected at runtime
- **Env vars**: `WM_WORKSPACE`, `BASE_INTERNAL_URL`, `WM_TOKEN` (for sub-job dispatch)
- **Sandboxed**: No host filesystem, no cross-project access, no local imports
- **Language**: Always deploy as `deno` — never use `bun` (Windmill default can vary, always be explicit)
- **Limitations**: No filesystem reads/writes, no cross-project variable access, no imports from local paths, no exceeding 60s timeout

### Variables — Never Hardcode Secrets
```typescript
import * as wmill from "npm:windmill-client@1";
const apiKey = await wmill.getVariable("f/proj_XXXXXXXXXXXX/CALLVA_API_KEY");
const baseUrl = await wmill.getVariable("f/proj_XXXXXXXXXXXX/CALLVA_API_URL");
```

Variable paths: `f/proj_{last12chars_of_project_uuid}/{VARIABLE_NAME}`. Discover the prefix by listing variables via CLI.

Every project needs at minimum: `CALLVA_API_KEY` (secret) and `CALLVA_API_URL` (not secret).

### Logging — Verbose by Default
Every script MUST include tagged logging with timing. This is the primary debugging mechanism. Pick one of two conventions based on the script's shape:

**Short single-purpose scripts** (webhook handlers, single-record mutations) — per-step elapsed suffix:

```typescript
function elapsed(start: number): string {
  return `${Date.now() - start}ms`;
}
const t0 = Date.now();
console.log("=== Script Name started ===");
console.log(`[INIT] Variables loaded (${elapsed(t0)})`);
console.log(`[FETCH] Response: ${resp.status} (${elapsed(tFetch)})`);
console.log(`=== Script Name finished in ${elapsed(t0)} ===`);
```

**Multi-phase pipelines** (3+ distinct stages) — seconds-from-start prefix on every line, so you can see at a glance which stage spent the time:

```typescript
let _t0 = 0;
function log(msg: string) {
  const s = ((Date.now() - _t0) / 1000).toFixed(1);
  console.log(`[${s}s] ${msg}`);
}
// ...
_t0 = Date.now();
log("[INIT] Variables loaded");
log("[FETCH] Received 150 records");
```

**Standard tags**: `[INIT]`, `[FETCH]`, `[AUTH]`, `[FORMAT]`, `[DEDUP]`, `[CREATE]`, `[UPDATE]`, `[DISPATCH]`, `[ERROR]`, `[WARN]`, `[RETRY]`, `[FATAL]`, `[DONE]`. Pick per-phase tags over severity tags — `[FETCH]` is more greppable than `[INFO]`.

**Full pattern**: For multi-phase pipelines with phase header comment blocks, phase tag conventions, and structured per-phase return values, read [docs/multi-phase-pipelines.md](docs/multi-phase-pipelines.md).

### Script Structure Template
```typescript
import * as wmill from "npm:windmill-client@1";

let _t0 = 0;
function log(msg: string) {
  const s = ((Date.now() - _t0) / 1000).toFixed(1);
  console.log(`[${s}s] ${msg}`);
}

// Parameters should have defaults so cron can invoke main() with no arguments.
// Parameters are overrides for ad-hoc runs, not required inputs.
export async function main(
  target_date: string = "",
  dry_run: boolean = false,
) {
  _t0 = Date.now();
  log("=== Script Name started ===");

  const apiKey = await wmill.getVariable("f/proj_XXXXXXXXXXXX/CALLVA_API_KEY");
  const baseUrl = await wmill.getVariable("f/proj_XXXXXXXXXXXX/CALLVA_API_URL");
  log("[INIT] Variables loaded");

  // Main logic in phases, using pure helpers for transforms and
  // effectful wrappers for I/O. See Modularity section below.

  log("=== Script Name finished ===");
  return {
    status: "success",
    // Structured counts and drill-down lists for debugging.
    // See docs/batch-processing.md for the full return shape.
  };
}
```

### Modularity — Pure Transforms vs Effectful Wrappers

Every automation script benefits from a clean separation between functions that DO things (I/O, writes, side effects) and functions that COMPUTE things (data transformation, filtering, formatting). Keep them in separate helpers at module scope:

- **Effectful wrappers** — each external API call gets its own named function: `getAuthToken`, `fetchRecords`, `createCallvaCall`, `sendSms`. Never inline `fetch()` in `main()`.
- **Pure transforms** — each data transformation gets its own named function that takes input and returns output with no side effects: `formatRecord`, `parseTime`, `addDays`, `localToUtcIso`. No network calls, no `console.log`, no mutation of external state.
- **Context objects** — when a pure function needs multiple shared values from `main()`, pass them as a typed context object (`FormatContext`) instead of lengthening the parameter list. Keeps signatures short and makes the dependency explicit.

`main()` orchestrates: it calls effectful wrappers to get data, runs data through pure transforms, collects results, and calls more wrappers to persist them. Everything hard-to-test lives in wrappers; everything interesting lives in pure functions.

### Parameter Discipline

All `main()` parameters should have sensible defaults so the automation can be triggered by cron with no arguments. Parameters are **overrides** for ad-hoc runs, not required inputs. A scheduled automation that refuses to run without arguments is a design bug — move those values to variables, or derive them (e.g. "target date" defaults to tomorrow in the local timezone).

Common patterns:

- `target_date: string = ""` — empty string means "derive from today"; explicit value overrides for backfills and catch-up runs
- `dry_run: boolean = false` — default false so cron runs are real; operators opt in to preview mode
- `is_holiday: boolean = false` — default false; set true when an operator knows the current run has extra context the code can't infer

When you find yourself wanting a required parameter, stop and ask whether the value can be derived, loaded from a variable, or defaulted sensibly.

### Return Value Design

Every script should return an object (not a bare string or number) with at minimum a `status` field and enough structure to debug a failed run without re-deploying. Avoid:

- `{ status: "success" }` alone — useless for debugging
- String-formatted summaries — can't query, chart, or alert on
- Single bare totals — can't distinguish "nothing to do" from "everything skipped"

**Full pattern**: For the structured return shape with outcome-category counts, drill-down lists, reconciliation discipline, and the three-status taxonomy (`success` / `completed_with_errors` / `failed` / `dry_run`), read [docs/batch-processing.md](docs/batch-processing.md) for batch scripts and [docs/resilience-and-retries.md](docs/resilience-and-retries.md) for status taxonomy.

### Dates & Time Zones — Tag Offsets at the Producer Boundary

CallVA stores all dates as **Zulu (UTC)** time. If you send a date string with no timezone offset, CallVA assumes it is already UTC and stores the literal value — silently shifting every date by the source timezone's offset. Before sending any date to CallVA, ensure it carries an explicit offset. If the external source doesn't provide one, stamp the source timezone using `fromZonedTime()` from `npm:date-fns-tz@3`.

**Full pattern**: If the task involves any timezone conversion — producer-boundary discipline, single-source-of-truth `TIMEZONE` constant, DST correctness, hoisting conversion out of hot loops, or the anti-patterns that silently break dates — read [docs/timezone-handling.md](docs/timezone-handling.md) before writing the script. It covers the complete pattern with code examples and the specific mistakes to avoid.

### Error Handling
- **Fatal errors** — return early with `status: "failed"` and include the error in the run output
- **Log before failing**: `log("[ERROR] ...")` or `log("[FATAL] ...")` for context
- **Recoverable errors** — log and continue, accumulate failures in an errors array, surface them in the return value
- **Call status integrity**: never leave calls stuck in transient states (`starting`, `in_progress`) — always reset to `scheduled` or `error` on failure

**Full pattern**: For the complete `withRetry` helper with `Result<T>` discriminated unions, linear backoff, recoverable-vs-fatal taxonomy, the `RunError` shape, retry budgets, and `AbortSignal.timeout()` usage on external fetches, read [docs/resilience-and-retries.md](docs/resilience-and-retries.md). Every script that calls an external API should follow this pattern.

### Sub-job Dispatch (Advanced)
When a script triggers another automation (e.g. runner dispatching call processors):

```typescript
const workspace = Deno.env.get("WM_WORKSPACE") ?? "";
const token = Deno.env.get("WM_TOKEN") ?? "";
const internalUrl = Deno.env.get("BASE_INTERNAL_URL") ?? "";

const resp = await fetch(
  `${internalUrl}/api/w/${workspace}/jobs/run/p/${scriptPath}`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ call }), // keys match target main() params
  }
);
const jobId = (await resp.text()).replace(/"/g, "");
```

## Deploying Code — File-based Workflow

Always write code to a local file first, then deploy via CLI `--file` flag:

1. Save to `.callva/automations/<name>.ts`
2. Deploy (delegate): `automations deploy <id> --file .callva/automations/<name>.ts`

Each deploy creates a new immutable version with a unique hash. Rollback by redeploying previous code.

## Running with Input Parameters

`automations run` accepts an optional JSON payload that is passed through to the target script's `main()` function. Keys in the JSON must match the parameter names of `main()`.

```bash
# No parameters — main() takes none
automations run <id>

# Inline JSON
automations run <id> --args '{"target_date":"2026-04-13","dry_run":true}'

# From file (use - for stdin)
automations run <id> --args-file ./params.json
```

The CLI wraps the payload under the `input` key the API expects, so you only pass the parameter object itself. Use this for ad-hoc testing of scripts that normally receive inputs from a scheduler or upstream automation.

**Full pattern**: For the convention of making `dry_run` a first-class parameter, returning a sample of what *would* be written, and treating dry-runs as non-negotiable before live deploys of mutating automations, read [docs/dry-run-pattern.md](docs/dry-run-pattern.md).

## Workflow: Creating a New Automation

1. **Understand** — What triggers it? What services? What variables/secrets? **If the automation creates records from an external source system, read [docs/idempotency.md](docs/idempotency.md) before writing the dedup logic** — every such pipeline needs a stable external ID and a dedup check, or re-runs silently duplicate data.
2. **Create variables** — User provides secret values (delegate via `callva:api`: `variables create ...`)
3. **Create automation** — (delegate via `callva:api`: `automations create --name "..." --description "..."`)
4. **Write script locally** — Save to `.callva/automations/<name>.ts`
5. **Show script, get confirmation** — Present code before deploying
6. **Deploy** — (delegate via `callva:api`: `automations deploy <id> --file .callva/automations/<name>.ts`)
7. **Test** — (delegate via `callva:api`: `automations run <id>`, or with input parameters: `automations run <id> --args '{"target_date":"2026-04-13"}'`)
8. **Check result** — (delegate via `callva:api`: `automations runs <id>`, then `automations run-detail <id> <job_id>`)

## Workflow: Updating an Existing Automation

1. Fetch current code (delegate via `callva:api`): `automations code <id>`
2. Save locally, modify, review with user
3. Deploy (delegate via `callva:api`): `automations deploy <id> --file .callva/automations/<name>.ts`
4. Test and verify (delegate via `callva:api`: `automations run <id>` — pass `--args '<json>'` or `--args-file <path>` if `main()` takes parameters)

## Common Automation Patterns

- **Call Runner (Dispatcher)**: Polls scheduled calls, locks with `starting` status, dispatches to processor scripts
- **Call Processor**: Takes call object, builds provider config (voice, prompt, transcriber), initiates outbound call
- **Webhook Handler**: Processes external events, extracts results, updates call records, uploads transcripts
- **Scheduled Job**: Runs on cron via CallVA schedule (`target_type: "automation"`)
- **Test/Utility**: Hardcoded data for pipeline validation

## Important Rules

- **Use `callva:api` for all I/O**: All CLI operations go through the API skill's patterns
- **Discover before guessing**: Run `--help` on any command via subagent
- **Delegate to subagents**: Never execute scripts in main context
- **Write code to file first**: Always `.callva/automations/<name>.ts` before deploying
- **Deploy with --file**: Never paste large code inline
- **Confirm before deploying**: Show script to user first
- **Never hardcode secrets**: Use `wmill.getVariable()` for all keys, URLs, and credentials — no inline tokens
- **Never hardcode external URLs**: Base URLs belong in variables, not script code
- **Always tag dates with a timezone**: CallVA treats offset-less dates as UTC — stamp the source timezone on any external date that lacks an offset before sending it in
- **Never exfiltrate data**: Scripts must only send data to the intended integration targets
- **Check runtime before writing**: Run `automations runtime-info` to verify engine version and timeout limits
- **Log everything**: Tagged logging with timing in every script
- **Test after deploy**: Run and check logs
- **Report IDs**: Show automation UUIDs and job IDs
