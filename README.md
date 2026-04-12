# CallVA Claude Code Plugins

Claude Code plugins for the [CallVA](https://callva.io) voice AI platform. Manage agents, prompts, calls, transcripts, automations, variables, custom fields, schedules, and more via the CallVA External API.

## Prerequisites

- Python 3.8+
- A [CallVA](https://callva.io) account with API access
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI

## Install

Add the marketplace:

```bash
claude plugin marketplace add callva-io/claude-code-plugins
```

Install the plugin (available in all projects):

```bash
claude plugin install callva@callva-plugins --scope user
```

## Update

Refresh the marketplace cache, then update the plugin:

```bash
claude plugin marketplace update callva-plugins
```

```bash
claude plugin update callva@callva-plugins
```

Or combined in one line:

```bash
claude plugin marketplace update callva-plugins && claude plugin update callva@callva-plugins
```

## Setup

Set `CALLVA_API_KEY` in one of these locations (first match wins):

1. Environment variable
2. `~/.claude/.env`
3. Project `.env.local`
4. Project `.env`

## Usage

Once installed, you can ask Claude to manage your CallVA resources directly:

```
List my CallVA agents
Show me calls from the last week
Update the default agent's prompt to include appointment confirmation
Get the transcript for call <id>
Show call trends for March
What are my current webhook schedules?
List my automations and their last run status
Deploy this script to my call runner automation
Create a custom field for call priority
```

The plugin activates automatically when Claude detects a CallVA-related request. No slash commands needed.

## Supported Resources

- **Agents** - list, get, update, delete, default agent
- **Assets** - prompts, schemas, payloads (full CRUD)
- **Calls** - list, get, create, update, delete, batch operations
- **Transcripts** - fetch, store, delete, download URLs
- **Outbound calls** - initiate calls to phone numbers
- **Call analytics** - aggregate stats, trends over time
- **Recordings** - stream and download call recordings
- **Custom fields & groups** - define, organize, and manage custom data fields
- **Webhook schedules** - time-based webhook rules with preview and execution history
- **Automations** - Windmill scripts: create, deploy code, trigger runs, view run results and logs, runtime info
- **Variables** - project-scoped secrets and config for automations (create, update, delete)
- **Projects, Settings, Phone numbers, Providers** - platform configuration

## Components

- **API Skill** (`plugin/skills/api/SKILL.md`) - Pure CRUD / I/O adapter for all CallVA resources. Delegates API calls to subagents to keep conversation context clean.
- **Prompt Skill** (`plugin/skills/prompt/SKILL.md`) - Voice agent prompt content engineering — write, optimize, version, and manage prompt text. Uses the API skill for I/O.
- **Automation Skill** (`plugin/skills/automation/SKILL.md`) - Automation code authoring — write, deploy, and test Windmill TypeScript scripts. Uses the API skill for I/O.
- **Script** (`plugin/scripts/callva_api.py`) - Stateless Python CLI (stdlib only, no dependencies). All API interactions go through this script.

## License

MIT
