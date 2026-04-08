# CallVA Claude Code Plugins

Claude Code plugins for the [CallVA](https://callva.io) voice AI platform. Manage agents, prompts, calls, transcripts, custom fields, schedules, and more via the CallVA External API.

## Prerequisites

- Python 3.8+
- A [CallVA](https://callva.io) account with API access
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI

## Install

```bash
# Add the marketplace
claude plugin marketplace add callva-io/callva-plugins

# Install the plugin (available in all projects)
claude plugin install callva@callva-plugins --scope user
```

## Update

```bash
# Refresh the marketplace cache
claude plugin marketplace update callva-plugins

# Update the plugin
claude plugin update callva@callva-plugins
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
- **Projects, Settings, Phone numbers, Providers** - platform configuration

## Components

- **Skill** (`plugin/skills/callva/SKILL.md`) - High-level helper that activates automatically. Delegates API calls to subagents to keep conversation context clean.
- **Agent** (`plugin/agents/callva.md`) - Programmatic interface for isolated API operations.
- **Script** (`plugin/scripts/callva_api.py`) - Stateless Python CLI (stdlib only, no dependencies). All API interactions go through this script.

## License

MIT
