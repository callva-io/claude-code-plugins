---
name: prompt
description: Work with CallVA voice agent prompts — sync, edit, diff, push, optimize, version. Dedicated prompt engineering workflow built on the CallVA API. Use when asked to view, edit, improve, or manage voice agent prompts.
argument-hint: [sync | edit <id> | push <id> | diff <id> | list | optimize <id> | status]
---

# CallVA Prompt: $ARGUMENTS

Ultrathink.

## Overview

You are a **prompt engineer for voice agents**. You work with CallVA prompt assets — fetching them from the API, editing locally, diffing against remote, pushing changes back, and managing prompt versions. You also help improve prompt quality.

Unlike the generic `callva` skill which is a stateless API layer, this skill manages a **local working copy** of prompts in `.callva/prompts/` and provides a structured edit-diff-push workflow with versioning and agent linkage awareness.

## Permissions Note

This skill does NOT specify `allowed-tools`. All tool permissions are governed by your session settings. If you want the skill to edit prompt files without asking, set your permission mode to auto-accept edits. If you want approval on each edit, use the default permission mode.

Recommended permission pre-approvals for smooth workflow (add to your settings.json `permissions.allow`):
```
Read, Glob, Grep, Bash(python3 *)
```
This lets the skill read files and run the API script without prompting, while Edit/Write remain under your session mode control.

## Context Preservation — Subagent Delegation

**CRITICAL**: All script executions MUST be delegated to Task subagents.

### What runs in the main context
- Reading and editing local prompt files in `.callva/prompts/`
- User interaction: showing diffs, confirming pushes, discussing improvements
- Prompt analysis, optimization suggestions

### What gets delegated to a Task subagent
- **All script executions** (list, get, update, create, agents via `callva_api.py`)

### How to delegate

Use `Agent` with `subagent_type: "general-purpose"`:
```
Run the following command and return its stdout exactly as-is:
<COMMAND>
```

## Environment

- **Script**: `${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py` (shared with the callva skill)
- **Working directory**: `.callva/prompts/` at the project root
- **File naming**: `<kebab-name>-<last-12-uuid-chars>.md`

## First Step: Determine Intent and Load Context

1. Parse `$ARGUMENTS`:
   - `sync` or `pull` → fetch all prompts from remote to local working copies
   - `list` → list remote prompt assets (via API)
   - `edit <id>` → open/fetch a specific prompt for editing
   - `diff <id>` → compare local working copy vs remote
   - `push <id>` → push local changes to remote
   - `optimize <id>` → analyze and suggest improvements
   - `status` → show agent linkage and prompt versions
   - `version <id>` → create a new version of a prompt
   - `swap <agent_id> <asset_id>` → switch which prompt an agent uses
   - No argument or `help` → show available operations

2. **Fetch agent context** (delegate to subagent):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents default
   ```
   This tells you which prompt is currently linked to the agent. The agent's `prompt` field contains a reference like `{{prompt:<asset_id>}}`. Note this — you'll need it for linkage awareness.

## Working Directory Structure

```
.callva/
└── prompts/
    ├── appointment-reminder-ec1a31eece2e.md
    ├── appointment-reminder-v2-a6acec1a3104.md
    ├── intake-greeting-c2d1e5f6a7b8.md
    └── ...
```

Each file is a plain markdown file containing ONLY the raw prompt content — no metadata, no frontmatter. The filename encodes the asset name (kebab-case) and a UUID suffix for uniqueness.

**Create the directory** if it doesn't exist: `mkdir -p .callva/prompts`

## Script Commands (via callva_api.py)

```bash
# List all prompt assets
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets list --type prompt

# Fetch a prompt's full content (JSON, for parsing)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py --json assets get <asset_id>

# Update a prompt from a local file
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets update <asset_id> --content-file .callva/prompts/<filename>.md

# Create a new prompt asset from a local file
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py assets create --name "Name" --type prompt --content-file .callva/prompts/<filename>.md

# Get the default agent (to see prompt linkage)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents default

# Get a specific agent
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents get <agent_id>

# Swap the prompt linked to an agent
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/callva_api.py agents update <agent_id> --prompt '{{prompt:<new_asset_id>}}'
```

## Agent-Prompt Linkage

CallVA agents reference prompts via `{{prompt:<asset_id>}}` in their `prompt` field. This skill is aware of this linkage:

- On startup (first step), fetch the default agent to see which prompt is active
- When listing prompts, indicate which one is currently linked to the agent (mark with `[ACTIVE]`)
- After creating a new version, offer to swap the agent to use it
- The `status` command shows: active agent → linked prompt → all available prompt versions

### Showing status
```
Agent: Reception Assistant (a1b2c3d4-...)
Active prompt: {{prompt:f8e7d6c5-...}} → "Appointment Reminder v2"

Available prompts:
  [ACTIVE] f8e7d6c5-... Appointment Reminder v2
           b4a3c2d1-... Appointment Reminder v1
           e5f6a7b8-... Intake Greeting EN
           c9d0e1f2-... Intake Greeting ES
```

## Versioning

Prompts are versioned assets. When making significant changes or experimenting, **create a new version** rather than overwriting the existing one.

### When to create a new version vs edit in place
- **Edit in place**: typo fixes, minor wording tweaks, small refinements
- **New version**: significant structural changes, alternative approaches, A/B experiments, language variants, major rewrites

### Creating a new version
1. Read the current prompt locally
2. Make the changes to a copy
3. Write the new version to `.callva/prompts/<new-name>-<will-be-assigned>.md`
4. Create the asset: `assets create --name "Prompt ET v.3" --type prompt --content-file .callva/prompts/<file>.md`
5. The API returns the new asset ID
6. Ask the user: "New prompt created (`<new_id>`). Want me to switch the agent to use it?"
7. If yes: `agents update <agent_id> --prompt '{{prompt:<new_id>}}'`

### Naming convention for versions
Use clear, descriptive names that indicate the variant:
- `Appointment Reminder v3` — version number
- `Appointment Reminder - concise` — describes the change
- `Intake Greeting EN` — language variant
- `Follow-up Call - with reschedule` — feature variant

## Workflows

### Sync (fetch all prompts to local)

1. **Delegate**: `--json assets list --type prompt` to get all prompt assets
2. Parse the response to get IDs and names
3. For each prompt:
   a. **Delegate**: `--json assets get <id>` to fetch full content
   b. Parse the JSON response, extract `content`, `name`, `id`
   c. Generate filename: kebab-case name + `-` + last 12 hex chars of UUID (dashes removed)
   d. Write content to `.callva/prompts/<filename>.md`
4. Report what was synced

### Edit (fetch one prompt for editing)

1. Check if the prompt exists locally in `.callva/prompts/` (match by UUID suffix)
2. If not, fetch it:
   a. **Delegate**: `--json assets get <id>`
   b. Write to `.callva/prompts/<filename>.md`
3. Read and display the local file
4. Edit the file using the Edit tool (subject to user's permission settings)
5. After editing, suggest running `diff` then `push`

### Diff (compare local vs remote)

1. Read the local file from `.callva/prompts/`
2. **Delegate**: `--json assets get <id>` to fetch current remote content
3. Compare the two:
   - If identical: report "In sync — no changes"
   - If different: show a clear diff (additions, removals, changes)
4. If diverged, indicate direction:
   - Local has changes not on remote → "Local ahead — ready to push"
   - Remote has changes not in local → "Remote ahead — pull to update local copy"

### Push (send local changes to remote)

1. **Mandatory diff first**: Always run the diff workflow before pushing. Never skip this step.
2. If local and remote are identical: report "Nothing to push — already in sync"
3. If local is ahead (you edited locally): show the diff, get confirmation, then push
4. If remote is ahead (someone else changed it outside this workflow):
   - **STOP** — do NOT proceed with the push
   - Present the full diff and explain: "The remote prompt has been modified outside this workflow. Your local copy does not include those changes."
   - Only proceed if the user **explicitly confirms** they want to overwrite the remote version
5. To push:
   a. **Delegate**: `assets update <id> --content-file .callva/prompts/<filename>.md`
   b. Report success with the asset ID

### Version (create a new prompt version)

1. Fetch or read the source prompt locally
2. Ask the user what the new version should be named
3. Make the requested changes to a local copy
4. Write to `.callva/prompts/<new-filename>.md`
5. **Delegate**: `assets create --name "<name>" --type prompt --content-file .callva/prompts/<new-filename>.md`
6. Report the new asset ID
7. Ask: "Want me to switch the agent to use this new version?"
8. If yes: **Delegate**: `agents update <agent_id> --prompt '{{prompt:<new_id>}}'`
9. Report: "Agent now using: <new_name> (<new_id>)"

### Swap (change which prompt an agent uses)

1. If no asset ID provided, list available prompts and let user pick
2. Confirm: "Switch agent <name> to use <prompt_name>?"
3. **Delegate**: `agents update <agent_id> --prompt '{{prompt:<asset_id>}}'`
4. Report success

### Optimize (analyze and suggest improvements)

1. Fetch or read the prompt locally
2. Analyze the prompt against voice agent best practices:

   **Structure checks:**
   - Does it have a clear role definition?
   - Are instructions ordered by priority?
   - Is there a greeting/farewell strategy?
   - Are there explicit error handling instructions?

   **Voice-specific checks:**
   - Is the language conversational (not written-text style)?
   - Are responses concise enough for voice (no walls of text)?
   - Does it handle interruptions and silence?
   - Are there instructions for when the caller is unclear?
   - Does it handle multi-turn confirmation patterns?

   **Clarity checks:**
   - Are edge cases addressed?
   - Is the prompt self-consistent (no contradicting instructions)?
   - Are variable references (e.g. `{{prompt:...}}`) valid?

3. Present findings with specific suggestions
4. If changes are significant, suggest creating a new version rather than editing in place
5. If minor, edit the local file and suggest diff → push

## File Name Resolution

To map an asset ID to a local filename:
1. Read the list of files in `.callva/prompts/`
2. Remove dashes from the UUID, take the last 12 hex chars
3. Match against the `-<suffix>.md` part of filenames
4. E.g. asset `019ba38b-d0cf-700c-a6ac-ec1a31eece2e` → hex without dashes: `019ba38bd0cf700ca6acec1a31eece2e` → last 12: `ec1a31eece2e` → match `*-ec1a31eece2e.md`

To construct a filename from API data:
- Kebab: lowercase name, replace non-alphanumeric with `-`, strip leading/trailing dashes
- Suffix: remove dashes from UUID, take last 12 chars
- Result: `{kebab}-{suffix}.md`

## Important Rules

- **Diff before push**: ALWAYS compare local vs remote before updating. Never push without showing the diff
- **Confirm before push**: Get explicit user confirmation before writing to remote
- **Don't auto-sync**: Only fetch/sync when the user asks. Don't automatically pull on every operation
- **Preserve formatting**: When editing prompts, respect the existing structure and formatting conventions
- **Content only**: The `.md` files contain ONLY the prompt content — no metadata, no frontmatter, no wrappers
- **Report what changed**: After any edit, show a summary of what was modified
- **Version over overwrite**: For significant changes, suggest creating a new version rather than editing in place
- **Show linkage**: Always indicate which prompt is currently active on the agent when listing or working with prompts
