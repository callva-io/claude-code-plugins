#!/usr/bin/env python3
"""CallVA External API client.

Stateless CLI for managing voice agents, assets (prompts), calls, and transcripts
on the CallVA voice AI platform. Pure CRUD — no local persistence, no side effects.
All output goes to stdout. Pipe or redirect as needed.

Usage:
    callva_api.py agents        list | default | get <id> | update <id> | delete <id>
    callva_api.py assets        list | get <id> | create | update <id> | delete <id>
    callva_api.py calls         list | get <id> | create | update <id> | delete <id> | batch
    callva_api.py transcripts   get <call_id> | store <call_id> | delete <call_id> | url <call_id>
    callva_api.py call          <destination> --agent-id <id>
    callva_api.py stats         aggregate | trends
    callva_api.py recordings    stream <call_id> --url <url> [--output <file>]
    callva_api.py fields        list | create | update <id> | delete <id> | impact <id>
    callva_api.py field-groups  list | create | update <id> | delete <id> | reorder | add-field <id> | remove-field <id> <fid> | reorder-fields <id> | update-field <id> <fid>
    callva_api.py schedules     list | get <id> | create | update <id> | delete <id> | preview <id> | executions <id>
    callva_api.py settings      get
    callva_api.py projects      list | get <id>
    callva_api.py phone-numbers list | get <id>
    callva_api.py providers     list | types

Global flag --json on any command outputs raw JSON instead of formatted text.

API key resolution (first match wins):
  1. CALLVA_API_KEY environment variable
  2. ~/.claude/.env  (global, shared across projects)
  3. <cwd>/.env.local
  4. <cwd>/.env

No external dependencies — stdlib only (Python 3.8+).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("CALLVA_API_URL", "https://api.callva.one/api/v1")
PROJECT_ROOT = os.getcwd()

# Global flag: set by --json on any command
RAW_JSON = False

# ---------------------------------------------------------------------------
# Environment & Auth
# ---------------------------------------------------------------------------


def _scan_env_file(filepath, key_name):
    """Extract a value for key_name from a dotenv file. Returns value or None."""
    if not os.path.isfile(filepath):
        return None
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() == key_name:
                    return value.strip().strip("'\"")
    return None


ENV_SEARCH_PATHS = [
    os.path.join(os.path.expanduser("~"), ".claude", ".env"),
    os.path.join(PROJECT_ROOT, ".env.local"),
    os.path.join(PROJECT_ROOT, ".env"),
]


def _resolve_env(key_name):
    """Resolve an env var: check os.environ first, then dotenv files."""
    if os.environ.get(key_name):
        return os.environ[key_name]
    for filepath in ENV_SEARCH_PATHS:
        value = _scan_env_file(filepath, key_name)
        if value:
            os.environ[key_name] = value
            return value
    return None


def load_env():
    """Load CALLVA_API_KEY and CALLVA_API_URL from environment or dotenv files."""
    global BASE_URL
    _resolve_env("CALLVA_API_KEY")
    url = _resolve_env("CALLVA_API_URL")
    if url:
        BASE_URL = url


def get_api_key():
    load_env()
    key = os.environ.get("CALLVA_API_KEY")
    if not key:
        die("CALLVA_API_KEY not set. Add it to environment, ~/.claude/.env, or project .env")
    return key


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def api(method, path, data=None, query=None):
    """Make an authenticated request to the CallVA API. Returns parsed JSON."""
    key = get_api_key()  # must run first — load_env() may update BASE_URL
    url = f"{BASE_URL}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in query.items() if v is not None}
        )

    headers = {"Authorization": f"Bearer {key}"}
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"success": True}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            err = json.loads(raw)
        except json.JSONDecodeError:
            err = raw
        die(f"HTTP {e.code}: {err}")
    except urllib.error.URLError as e:
        die(f"Connection failed: {e.reason}")


def api_download(path, output_path, query=None):
    """Download binary content (recordings) to a file or stdout."""
    url = f"{BASE_URL}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in query.items() if v is not None}
        )

    headers = {"Authorization": f"Bearer {get_api_key()}"}
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "audio/mpeg")
            length = resp.headers.get("Content-Length", "unknown")

            if output_path:
                with open(output_path, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return {"file": output_path, "content_type": content_type, "size": length}
            else:
                # Write binary to stdout
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    sys.stdout.buffer.write(chunk)
                return None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            err = json.loads(raw)
        except json.JSONDecodeError:
            err = raw
        die(f"HTTP {e.code}: {err}")
    except urllib.error.URLError as e:
        die(f"Connection failed: {e.reason}")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def die(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def out(text):
    print(text)


def out_json(data):
    """Print data as indented JSON."""
    out(json.dumps(data, indent=2, ensure_ascii=False))


def out_result(result, formatter):
    """If --json, dump raw API response. Otherwise, run the formatter."""
    if RAW_JSON:
        out_json(result)
    else:
        formatter(result)


def fmt_duration(seconds):
    if seconds is None:
        return "-"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_dt(iso_str):
    if not iso_str or iso_str == "-":
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, AttributeError):
        return iso_str


# ---------------------------------------------------------------------------
# Content resolution
# ---------------------------------------------------------------------------


def resolve_content(args):
    """Resolve content from --content or --content-file flags."""
    cf = getattr(args, "content_file", None)
    c = getattr(args, "content", None)
    if cf:
        return sys.stdin.read() if cf == "-" else open(cf).read()
    return c


def parse_bool(value):
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean: {value}")


def parse_json_arg(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"Invalid JSON: {e}")


def parse_json_file(value):
    if value == "-":
        return json.loads(sys.stdin.read())
    with open(value) as f:
        return json.load(f)


# ===================================================================
# AGENTS
# ===================================================================


def agents_list(args):
    """List all agents."""
    query = {}
    if getattr(args, "is_active", None) is not None:
        query["is_active"] = str(args.is_active).lower()

    result = api("GET", "/external/agents", query=query)

    def fmt(r):
        agents = r.get("data", [])
        if not agents:
            out("No agents found.")
            return
        out("| ID | Name | Project | Active | Default |")
        out("|----|------|---------|--------|---------|")
        for a in agents:
            out(
                f"| `{a.get('id', '-')}` "
                f"| {a.get('name', '-')} "
                f"| {a.get('project_name') or '-'} "
                f"| {'Yes' if a.get('is_active') else 'No'} "
                f"| {'Yes' if a.get('is_default') else 'No'} |"
            )

    out_result(result, fmt)


def agents_default(_args):
    """Get or create the default agent."""
    result = api("GET", "/external/agents/default")
    out_result(result, lambda r: _print_agent(r.get("data", r)))


def agents_get(args):
    """Get agent by ID."""
    result = api("GET", f"/external/agents/{args.id}")
    out_result(result, lambda r: _print_agent(r.get("data", r)))


def agents_update(args):
    """Update agent fields."""
    data = {}
    if args.json_data:
        data = args.json_data
    else:
        if args.name is not None:
            data["name"] = args.name
        if args.voice is not None:
            data["voice"] = args.voice
        if args.prompt is not None:
            data["prompt"] = args.prompt
        if args.prompt_file is not None:
            data["prompt"] = open(args.prompt_file).read()
        if args.greeting_type is not None:
            data["greeting_type"] = args.greeting_type
        if args.greeting_exact is not None:
            data["greeting_exact"] = args.greeting_exact
        if args.greeting_instruction is not None:
            data["greeting_instruction"] = args.greeting_instruction
        if args.agent_speaks_first is not None:
            data["agent_speaks_first"] = args.agent_speaks_first
        if args.config_json:
            data["config"] = args.config_json

    if not data:
        die("No fields to update. Use flags or --json '{...}'")

    result = api("PATCH", f"/external/agents/{args.id}", data)

    def fmt(r):
        _print_agent(r.get("data", r))
        out("\nAgent updated successfully.")

    out_result(result, fmt)


def agents_delete(args):
    """Delete an agent."""
    result = api("DELETE", f"/external/agents/{args.id}")
    out_result(result, lambda _: out(f"Deleted agent: {args.id}"))


def _print_agent(agent):
    """Print agent details in structured format."""
    out(f"ID:       {agent.get('id', '-')}")
    out(f"Name:     {agent.get('name', '-')}")
    out(f"Voice:    {agent.get('voice') or '-'}")
    out(f"Active:   {agent.get('is_active', '-')}")
    out(f"Default:  {agent.get('is_default', '-')}")
    out(f"System:   {agent.get('is_system', '-')}")

    greeting = agent.get("greeting_type") or "-"
    out(f"Greeting: {greeting}")
    if greeting == "exact":
        out(f"  Text:   {agent.get('greeting_exact', '')[:100]}")
    elif greeting == "instruction":
        out(f"  Instr:  {agent.get('greeting_instruction', '')[:100]}")

    out(f"Speaks first: {agent.get('agent_speaks_first', '-')}")

    phones = agent.get("phone_numbers", [])
    if phones:
        out(f"Phones: {', '.join(p.get('phone_number', '?') for p in phones)}")

    prompt = agent.get("prompt") or ""
    if prompt:
        out(f"\n--- Prompt ({len(prompt)} chars) ---")
        out(prompt[:2000])
        if len(prompt) > 2000:
            out(f"... ({len(prompt) - 2000} more chars, use --json for full output)")

    config = agent.get("config")
    if config:
        out(f"\n--- Config ---")
        out(json.dumps(config, indent=2))


# ===================================================================
# ASSETS
# ===================================================================


def assets_list(args):
    """List assets with optional type filter."""
    query = {}
    if args.type:
        query["type"] = args.type
    if args.per_page:
        query["per_page"] = str(args.per_page)

    result = api("GET", "/external/assets", query=query)

    def fmt(r):
        assets = r.get("data", [])
        if not assets:
            out("No assets found.")
            return
        out("| ID | Name | Type | Active |")
        out("|----|------|------|--------|")
        for a in assets:
            out(
                f"| `{a.get('id', '-')}` "
                f"| {a.get('name', '-')} "
                f"| {a.get('type', '-')} "
                f"| {'Yes' if a.get('is_active') else 'No'} |"
            )

    out_result(result, fmt)


def assets_get(args):
    """Fetch and display an asset."""
    result = api("GET", f"/external/assets/{args.id}")

    def fmt(r):
        data = r.get("data", r)
        out(f"ID:      {data.get('id', '-')}")
        out(f"Name:    {data.get('name', '-')}")
        out(f"Type:    {data.get('type', '-')}")
        out(f"Active:  {data.get('is_active', '-')}")
        out(f"Updated: {fmt_dt(data.get('updated_at'))}")
        content = data.get("content") or ""
        out(f"Chars:   {len(content)}")
        if content:
            out(f"\n--- Content ---")
            out(content)

    out_result(result, fmt)


def assets_create(args):
    """Create a new asset."""
    content = resolve_content(args)
    data = {
        "name": args.name,
        "type": args.type,
        "content": content,
        "is_active": not args.inactive,
    }
    result = api("POST", "/external/assets", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Created: {resp.get('id', '-')}")
        out(f"Name:    {resp.get('name', '-')}")
        out(f"Type:    {resp.get('type', '-')}")

    out_result(result, fmt)


def assets_update(args):
    """Update an existing asset."""
    content = resolve_content(args)
    data = {}
    if args.name is not None:
        data["name"] = args.name
    if content is not None:
        data["content"] = content
    if args.is_active is not None:
        data["is_active"] = args.is_active

    if not data:
        die("No fields to update. Use --name, --content/--content-file, or --is-active")

    result = api("PATCH", f"/external/assets/{args.id}", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Updated: {args.id}")
        out(f"Name:    {resp.get('name', '-')}")

    out_result(result, fmt)


def assets_delete(args):
    """Delete an asset."""
    result = api("DELETE", f"/external/assets/{args.id}")
    out_result(result, lambda _: out(f"Deleted asset: {args.id}"))


# ===================================================================
# CALLS
# ===================================================================


def calls_list(args):
    """List calls with filtering and pagination."""
    query = {"sort": args.sort}
    if args.per_page:
        query["per_page"] = str(args.per_page)
    if args.page:
        query["page"] = str(args.page)
    if args.filter:
        for filt in args.filter:
            k, _, v = filt.partition("=")
            if v:
                query[k] = v

    result = api("GET", "/external/calls", query=query)

    def fmt(r):
        calls = r.get("data", [])
        pagination = r.get("pagination", {})
        if not calls:
            out("No calls found.")
            return

        out("| Call ID | Date/Time | Duration | Status | Result |")
        out("|---------|-----------|----------|--------|--------|")
        for c in calls:
            out(
                f"| `{c.get('id', '-')}` "
                f"| {fmt_dt(c.get('created_at'))} "
                f"| {fmt_duration(c.get('duration'))} "
                f"| {c.get('status', '-')} "
                f"| {c.get('result', '-') or '-'} |"
            )

        total = pagination.get("total", len(calls))
        cur = pagination.get("current_page", 1)
        last = pagination.get("last_page", 1)
        out(f"\nPage {cur}/{last} ({total} total)")

    out_result(result, fmt)


def calls_get(args):
    """Get a single call's details."""
    result = api("GET", f"/external/calls/{args.id}")
    # Calls always output JSON — the custom fields are dynamic
    out_json(result.get("data", result))


def calls_create(args):
    """Create a call record from JSON."""
    data = args.json_data or {}
    result = api("POST", "/external/calls", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Created call: {resp.get('id', '-')}")
        out_json(resp)

    out_result(result, fmt)


def calls_update(args):
    """Update a call record."""
    data = args.json_data or {}
    if not data:
        die("Provide fields as --json '{...}'")
    result = api("PATCH", f"/external/calls/{args.id}", data)

    def fmt(r):
        out(f"Updated call: {args.id}")
        out_json(r.get("data", r))

    out_result(result, fmt)


def calls_delete(args):
    """Delete a call record."""
    result = api("DELETE", f"/external/calls/{args.id}")
    out_result(result, lambda _: out(f"Deleted call: {args.id}"))


def calls_batch(args):
    """Batch update calls."""
    data = {"ids": args.ids, "updates": args.json_data or {}}
    if not data["updates"]:
        die("Provide updates as --json '{...}'")
    result = api("PATCH", "/external/calls/batch", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Updated {resp.get('updated_count', '?')} calls")

    out_result(result, fmt)


# ===================================================================
# TRANSCRIPTS
# ===================================================================


def transcripts_get(args):
    """Fetch a call transcript."""
    result = api("GET", f"/external/calls/{args.call_id}/transcript")

    def fmt(r):
        messages = r.get("data", {}).get("messages", [])
        if not messages:
            out(f"No transcript found for call {args.call_id}")
            return
        labels = {"assistant": "Agent", "user": "Customer", "system": "System"}
        for msg in messages:
            role = msg.get("role", "unknown")
            label = labels.get(role, role.capitalize())
            content = msg.get("content", "")
            out(f"**{label}:** {content}\n")

    out_result(result, fmt)


def transcripts_store(args):
    """Store/update a transcript."""
    data = args.json_data
    if not data:
        die("Provide transcript as --json-file <path> or --json '{\"messages\":[...]}'")
    result = api("POST", f"/external/calls/{args.call_id}/transcript", data)
    out_result(result, lambda r: out(f"Stored transcript for call {args.call_id}"))


def transcripts_delete(args):
    """Delete a transcript."""
    result = api("DELETE", f"/external/calls/{args.call_id}/transcript")
    out_result(result, lambda _: out(f"Deleted transcript for call {args.call_id}"))


def transcripts_url(args):
    """Get a presigned download URL for a transcript."""
    result = api("GET", f"/external/calls/{args.call_id}/transcript/url")

    def fmt(r):
        data = r.get("data", r)
        out(data.get("url", "-"))

    out_result(result, fmt)


# ===================================================================
# OUTBOUND CALL
# ===================================================================


def call_initiate(args):
    """Initiate an outbound call."""
    data = {
        "destination": args.destination,
        "agent_id": args.agent_id,
    }
    if args.phone_number_id:
        data["phone_number_id"] = args.phone_number_id
    if args.call_id:
        data["call_id"] = args.call_id
    if args.overrides:
        data["agent_overrides"] = args.overrides

    result = api("POST", "/external/call", data)

    def fmt(r):
        resp = r.get("data", r)
        call_data = resp.get("call", {})
        out(f"Call initiated:")
        out(f"  Call ID:     {call_data.get('id', '-')}")
        out(f"  Status:      {call_data.get('status', '-')}")
        out(f"  Destination: {call_data.get('phone', '-')}")
        out(f"  Direction:   {call_data.get('direction', '-')}")
        room = resp.get("room", {})
        if room:
            out(f"  Room SID:    {room.get('sid', '-')}")

    out_result(result, fmt)


# ===================================================================
# STATS (Call Analytics)
# ===================================================================


def stats_aggregate(args):
    """Run aggregate query on calls."""
    query = {"operation": args.op}
    if args.field:
        query["field"] = args.field
    if args.group_by:
        query["group_by"] = args.group_by
    if args.interval:
        query["interval"] = args.interval
    if args.filter:
        for filt in args.filter:
            k, _, v = filt.partition("=")
            if v:
                query[k] = v

    result = api("GET", "/external/calls/aggregate", query=query)

    def fmt(r):
        data = r.get("data", r)
        op = data.get("operation", "-")
        field = data.get("field", "-")
        groups = data.get("groups")
        if groups:
            out(f"Aggregate: {op}({field}) grouped by {data.get('group_by', '?')}\n")
            out("| Group | Value |")
            out("|-------|-------|")
            for g in groups:
                out(f"| {g.get('key', '-')} | {g.get('value', '-')} |")
        else:
            out(f"{op}({field}): {data.get('value', '-')}")

    out_result(result, fmt)


def stats_trends(args):
    """Get daily call trend data."""
    query = {"date_from": args.date_from, "date_to": args.date_to}

    result = api("GET", "/external/calls/trends", query=query)

    def fmt(r):
        data = r.get("data", r)
        points = data.get("data", [])
        total = data.get("total", "-")
        out(f"Trends: {data.get('date_from', '?')} to {data.get('date_to', '?')} ({total} total)\n")
        if not points:
            out("No data.")
            return
        out("| Date | Count | Label |")
        out("|------|-------|-------|")
        for p in points:
            out(f"| {p.get('date', '-')} | {p.get('count', 0)} | {p.get('label', '-')} |")

    out_result(result, fmt)


# ===================================================================
# RECORDINGS
# ===================================================================


def recordings_stream(args):
    """Download a call recording."""
    if not args.url:
        die("--url is required (the recording URL from the call's recording_url field)")

    query = {"url": args.url}
    output = args.output

    if output:
        info = api_download(f"/external/calls/{args.call_id}/recording", output, query=query)
        if info:
            out(f"Saved: {info['file']}")
            out(f"Type:  {info['content_type']}")
            out(f"Size:  {info['size']} bytes")
    else:
        # Stream to stdout (binary)
        api_download(f"/external/calls/{args.call_id}/recording", None, query=query)


# ===================================================================
# CUSTOM FIELDS
# ===================================================================


def fields_list(args):
    """List custom field definitions."""
    query = {}
    if args.entity_type:
        query["entity_type"] = args.entity_type

    result = api("GET", "/external/custom-fields", query=query)

    def fmt(r):
        fields = r.get("data", [])
        if not fields:
            out("No custom fields found.")
            return
        out("| ID | Key | Label | Type | Required | Filterable |")
        out("|----|-----|-------|------|----------|------------|")
        for f_ in fields:
            out(
                f"| `{f_.get('id', '-')}` "
                f"| {f_.get('field_key', '-')} "
                f"| {f_.get('field_label', '-')} "
                f"| {f_.get('field_type', '-')} "
                f"| {'Yes' if f_.get('is_required') else 'No'} "
                f"| {'Yes' if f_.get('is_filterable') else 'No'} |"
            )

    out_result(result, fmt)


def fields_create(args):
    """Create a custom field definition."""
    data = args.json_data or {}
    if not data:
        die("Provide field definition as --json '{...}'")
    result = api("POST", "/external/custom-fields", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Created field: {resp.get('id', '-')}")
        out(f"Key:   {resp.get('field_key', '-')}")
        out(f"Label: {resp.get('field_label', '-')}")
        out(f"Type:  {resp.get('field_type', '-')}")

    out_result(result, fmt)


def fields_update(args):
    """Update a custom field definition."""
    data = args.json_data or {}
    if not data:
        die("Provide fields to update as --json '{...}'")
    result = api("PUT", f"/external/custom-fields/{args.id}", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Updated field: {args.id}")
        out(f"Key:   {resp.get('field_key', '-')}")
        out(f"Label: {resp.get('field_label', '-')}")

    out_result(result, fmt)


def fields_delete(args):
    """Delete a custom field definition."""
    result = api("DELETE", f"/external/custom-fields/{args.id}")
    out_result(result, lambda _: out(f"Deleted field: {args.id}"))


def fields_impact(args):
    """Preview deletion impact for a custom field."""
    result = api("GET", f"/external/custom-fields/{args.id}/delete-impact")

    def fmt(r):
        data = r.get("data", r)
        out(f"Field:          {args.id}")
        out(f"Affected records: {data.get('affected_count', data.get('count', '-'))}")
        out_json(data)

    out_result(result, fmt)


# ===================================================================
# CUSTOM FIELD GROUPS
# ===================================================================


def field_groups_list(_args):
    """List custom field groups with their fields."""
    result = api("GET", "/external/custom-field-groups")

    def fmt(r):
        groups = r.get("data", [])
        if not groups:
            out("No field groups found.")
            return
        for g in groups:
            out(f"## {g.get('name', '-')} (`{g.get('id', '-')}`)")
            out(f"   Entity: {g.get('entity_type', '-')} | Show title: {g.get('show_title', '-')}")
            fields = g.get("fields", [])
            if fields:
                for f_ in fields:
                    out(f"   - {f_.get('field_key', '?')}: {f_.get('field_label', '?')} ({f_.get('field_type', '?')})")
            else:
                out("   (no fields)")
            out("")

    out_result(result, fmt)


def field_groups_create(args):
    """Create a custom field group."""
    data = args.json_data or {}
    if not data:
        die("Provide group definition as --json '{...}'")
    result = api("POST", "/external/custom-field-groups", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Created group: {resp.get('id', '-')}")
        out(f"Name: {resp.get('name', '-')}")

    out_result(result, fmt)


def field_groups_update(args):
    """Update a custom field group."""
    data = args.json_data or {}
    if not data:
        die("Provide fields to update as --json '{...}'")
    result = api("PUT", f"/external/custom-field-groups/{args.id}", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Updated group: {args.id}")
        out(f"Name: {resp.get('name', '-')}")

    out_result(result, fmt)


def field_groups_delete(args):
    """Delete a custom field group."""
    result = api("DELETE", f"/external/custom-field-groups/{args.id}")
    out_result(result, lambda _: out(f"Deleted group: {args.id}"))


def field_groups_reorder(args):
    """Reorder custom field groups."""
    data = args.json_data or {}
    if not data:
        die("Provide order as --json '{\"groups\": [{\"id\": \"...\", \"sort_order\": 0}, ...]}'")
    result = api("POST", "/external/custom-field-groups/reorder", data)
    out_result(result, lambda _: out("Groups reordered."))


def field_groups_add_field(args):
    """Add a field to a group."""
    data = {"custom_field_id": args.field_id}
    result = api("POST", f"/external/custom-field-groups/{args.id}/fields", data)
    out_result(result, lambda _: out(f"Added field {args.field_id} to group {args.id}"))


def field_groups_remove_field(args):
    """Remove a field from a group."""
    result = api("DELETE", f"/external/custom-field-groups/{args.id}/fields/{args.field_id}")
    out_result(result, lambda _: out(f"Removed field {args.field_id} from group {args.id}"))


def field_groups_reorder_fields(args):
    """Reorder fields within a group."""
    data = args.json_data or {}
    if not data:
        die("Provide order as --json '{\"fields\": [{\"id\": \"...\", \"sort_order\": 0}, ...]}'")
    result = api("POST", f"/external/custom-field-groups/{args.id}/fields/reorder", data)
    out_result(result, lambda _: out(f"Fields reordered in group {args.id}"))


def field_groups_update_field(args):
    """Update field display settings within a group."""
    data = args.json_data or {}
    if not data:
        die("Provide display settings as --json '{\"display_mode\": \"...\", ...}'")
    result = api("PATCH", f"/external/custom-field-groups/{args.id}/fields/{args.field_id}", data)
    out_result(result, lambda _: out(f"Updated field {args.field_id} settings in group {args.id}"))


# ===================================================================
# WEBHOOK SCHEDULES
# ===================================================================


def schedules_list(_args):
    """List webhook schedules with rules."""
    result = api("GET", "/external/webhook-schedule")

    def fmt(r):
        schedules = r.get("data", [])
        if not schedules:
            out("No schedules found.")
            return
        out("| ID | Name | Method | Active | Rules |")
        out("|----|------|--------|--------|-------|")
        for s in schedules:
            rules = s.get("rules", [])
            out(
                f"| `{s.get('id', '-')}` "
                f"| {s.get('name', '-')} "
                f"| {s.get('webhook_method', '-')} "
                f"| {'Yes' if s.get('is_active') else 'No'} "
                f"| {len(rules)} |"
            )

    out_result(result, fmt)


def schedules_get(args):
    """Get a schedule with its rules."""
    result = api("GET", f"/external/webhook-schedule/{args.id}")

    def fmt(r):
        s = r.get("data", r)
        out(f"ID:       {s.get('id', '-')}")
        out(f"Name:     {s.get('name', '-')}")
        out(f"URL:      {s.get('webhook_url', '-')}")
        out(f"Method:   {s.get('webhook_method', '-')}")
        out(f"Active:   {s.get('is_active', '-')}")
        out(f"Retries:  {s.get('max_retries', '-')}")
        out(f"Timeout:  {s.get('timeout_seconds', '-')}s")
        rules = s.get("rules", [])
        if rules:
            out(f"\n--- Rules ({len(rules)}) ---")
            for rule in rules:
                days = rule.get("days_of_week", [])
                out(f"  {rule.get('name', '?')}: {rule.get('action', '?')} "
                    f"| {rule.get('time_from', '?')}-{rule.get('time_to', '?')} "
                    f"| days={days} | interval={rule.get('execution_interval', '?')}s "
                    f"| active={'Yes' if rule.get('is_active') else 'No'}")

    out_result(result, fmt)


def schedules_create(args):
    """Create a webhook schedule."""
    data = args.json_data or {}
    if not data:
        die("Provide schedule definition as --json '{...}'")
    result = api("POST", "/external/webhook-schedule", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Created schedule: {resp.get('id', '-')}")
        out(f"Name: {resp.get('name', '-')}")

    out_result(result, fmt)


def schedules_update(args):
    """Update a webhook schedule (syncs rules)."""
    data = args.json_data or {}
    if not data:
        die("Provide fields to update as --json '{...}'")
    result = api("PUT", f"/external/webhook-schedule/{args.id}", data)

    def fmt(r):
        resp = r.get("data", r)
        out(f"Updated schedule: {args.id}")
        out(f"Name: {resp.get('name', '-')}")

    out_result(result, fmt)


def schedules_delete(args):
    """Delete a webhook schedule."""
    result = api("DELETE", f"/external/webhook-schedule/{args.id}")
    out_result(result, lambda _: out(f"Deleted schedule: {args.id}"))


def schedules_preview(args):
    """Preview which rule matches at a given datetime."""
    data = {"datetime": args.datetime}
    result = api("POST", f"/external/webhook-schedule/{args.id}/preview", data)
    out_result(result, lambda r: out_json(r.get("data", r)))


def schedules_executions(args):
    """Get execution history for a schedule."""
    query = {}
    if args.per_page:
        query["per_page"] = str(args.per_page)

    result = api("GET", f"/external/webhook-schedule/{args.id}/execution", query=query)

    def fmt(r):
        execs = r.get("data", [])
        if not execs:
            out("No executions found.")
            return
        out("| ID | Status | Executed At | Response |")
        out("|----|--------|-------------|----------|")
        for ex in execs:
            out(
                f"| `{ex.get('id', '-')}` "
                f"| {ex.get('status', '-')} "
                f"| {fmt_dt(ex.get('executed_at'))} "
                f"| {ex.get('response_status_code', '-')} |"
            )

    out_result(result, fmt)


# ===================================================================
# SETTINGS
# ===================================================================


def settings_get(_args):
    """Get project-level settings."""
    result = api("GET", "/external/settings/project")
    out_result(result, lambda r: out_json(r.get("data", r)))


# ===================================================================
# PROJECTS
# ===================================================================


def projects_list(args):
    """List projects."""
    query = {}
    if getattr(args, "is_active", None) is not None:
        query["is_active"] = str(args.is_active).lower()
    if args.per_page:
        query["per_page"] = str(args.per_page)

    result = api("GET", "/external/projects", query=query)

    def fmt(r):
        projects = r.get("data", [])
        if not projects:
            out("No projects found.")
            return
        out("| ID | Name | Active |")
        out("|----|------|--------|")
        for p in projects:
            out(
                f"| `{p.get('id', '-')}` "
                f"| {p.get('name', '-')} "
                f"| {'Yes' if p.get('is_active') else 'No'} |"
            )

    out_result(result, fmt)


def projects_get(args):
    """Get project details."""
    result = api("GET", f"/external/projects/{args.id}")
    out_result(result, lambda r: out_json(r.get("data", r)))


# ===================================================================
# PHONE NUMBERS
# ===================================================================


def phone_numbers_list(args):
    """List provisioned phone numbers."""
    query = {}
    if getattr(args, "is_active", None) is not None:
        query["is_active"] = str(args.is_active).lower()
    if args.per_page:
        query["per_page"] = str(args.per_page)

    result = api("GET", "/external/phone-numbers", query=query)

    def fmt(r):
        numbers = r.get("data", [])
        if not numbers:
            out("No phone numbers found.")
            return
        out("| ID | Number | Type | Status |")
        out("|----|--------|------|--------|")
        for n in numbers:
            out(
                f"| `{n.get('id', '-')}` "
                f"| {n.get('phone_number', '-')} "
                f"| {n.get('number_type', '-')} "
                f"| {n.get('status', '-')} |"
            )

    out_result(result, fmt)


def phone_numbers_get(args):
    """Get phone number details."""
    result = api("GET", f"/external/phone-numbers/{args.id}")
    out_result(result, lambda r: out_json(r.get("data", r)))


# ===================================================================
# PHONE PROVIDERS
# ===================================================================


def providers_list(args):
    """List phone provider credentials."""
    query = {}
    if getattr(args, "is_active", None) is not None:
        query["is_active"] = str(args.is_active).lower()
    if args.provider_type:
        query["provider_type"] = args.provider_type
    if args.per_page:
        query["per_page"] = str(args.per_page)

    result = api("GET", "/external/phone-providers", query=query)

    def fmt(r):
        providers = r.get("data", [])
        if not providers:
            out("No providers found.")
            return
        out("| ID | Name | Type | Active | Numbers |")
        out("|----|------|------|--------|---------|")
        for p in providers:
            out(
                f"| `{p.get('id', '-')}` "
                f"| {p.get('name', '-')} "
                f"| {p.get('provider_type', '-')} "
                f"| {'Yes' if p.get('is_active') else 'No'} "
                f"| {p.get('phone_numbers_count', '-')} |"
            )

    out_result(result, fmt)


def providers_types(_args):
    """Get supported provider types and required credential fields."""
    result = api("GET", "/external/phone-providers/types")
    out_result(result, lambda r: out_json(r.get("data", r)))


# ===================================================================
# CLI Parser
# ===================================================================


def build_parser():
    parser = argparse.ArgumentParser(
        prog="callva_api",
        description="CallVA External API client — manage agents, assets, calls, and transcripts.",
    )
    parser.add_argument("--json", dest="raw_json", action="store_true",
                        help="Output raw JSON instead of formatted text")

    subs = parser.add_subparsers(dest="resource", required=True)

    # --- agents ---
    ag = subs.add_parser("agents", help="Manage voice agents")
    ag_sub = ag.add_subparsers(dest="action", required=True)

    ag_ls = ag_sub.add_parser("list", help="List all agents")
    ag_ls.add_argument("--is-active", type=parse_bool, default=None, help="Filter by active status")

    ag_sub.add_parser("default", help="Get or create the default agent")

    ag_get = ag_sub.add_parser("get", help="Get agent by ID")
    ag_get.add_argument("id", help="Agent UUID")

    ag_upd = ag_sub.add_parser("update", help="Update agent")
    ag_upd.add_argument("id", help="Agent UUID")
    ag_upd.add_argument("--name", help="Agent name")
    ag_upd.add_argument("--voice", help="Voice identifier")
    ag_upd.add_argument("--prompt", help="Prompt text (inline)")
    ag_upd.add_argument("--prompt-file", help="Read prompt from file")
    ag_upd.add_argument("--greeting-type", choices=["prompt", "exact", "instruction"])
    ag_upd.add_argument("--greeting-exact", help="Exact greeting text")
    ag_upd.add_argument("--greeting-instruction", help="Greeting instruction")
    ag_upd.add_argument("--agent-speaks-first", type=parse_bool, default=None)
    ag_upd.add_argument("--config", dest="config_json", type=parse_json_arg, help="Config JSON (partial merge)")
    ag_upd.add_argument("--json", dest="json_data", type=parse_json_arg, help="Full update payload as JSON")

    ag_del = ag_sub.add_parser("delete", help="Delete agent")
    ag_del.add_argument("id", help="Agent UUID")

    # --- assets ---
    ast = subs.add_parser("assets", help="Manage assets (prompts, schemas, payloads)")
    ast_sub = ast.add_subparsers(dest="action", required=True)

    ast_ls = ast_sub.add_parser("list", help="List assets")
    ast_ls.add_argument("--type", choices=["prompt", "schema", "payload"], help="Filter by type")
    ast_ls.add_argument("--per-page", type=int, help="Results per page")

    ast_get = ast_sub.add_parser("get", help="Get asset by ID")
    ast_get.add_argument("id", help="Asset UUID")

    ast_cr = ast_sub.add_parser("create", help="Create asset")
    ast_cr.add_argument("--name", required=True, help="Asset name")
    ast_cr.add_argument("--type", required=True, choices=["prompt", "schema", "payload"])
    ast_cr.add_argument("--content", help="Content inline")
    ast_cr.add_argument("--content-file", help="Read content from file (- for stdin)")
    ast_cr.add_argument("--inactive", action="store_true")

    ast_upd = ast_sub.add_parser("update", help="Update asset")
    ast_upd.add_argument("id", help="Asset UUID")
    ast_upd.add_argument("--name", help="New name")
    ast_upd.add_argument("--content", help="New content inline")
    ast_upd.add_argument("--content-file", help="Read content from file (- for stdin)")
    ast_upd.add_argument("--is-active", type=parse_bool, default=None)

    ast_del = ast_sub.add_parser("delete", help="Delete asset")
    ast_del.add_argument("id", help="Asset UUID")

    # --- calls ---
    cl = subs.add_parser("calls", help="Manage call records")
    cl_sub = cl.add_subparsers(dest="action", required=True)

    cl_ls = cl_sub.add_parser("list", help="List calls")
    cl_ls.add_argument("--per-page", type=int, help="Results per page")
    cl_ls.add_argument("--page", type=int, help="Page number")
    cl_ls.add_argument("--sort", default="-created_at", help="Sort field (use = for desc, e.g. --sort=-created_at)")
    cl_ls.add_argument("--filter", "-f", action="append", help="Filter as key=value (repeatable)")

    cl_get = cl_sub.add_parser("get", help="Get call details (always JSON — dynamic fields)")
    cl_get.add_argument("id", help="Call UUID")

    cl_cr = cl_sub.add_parser("create", help="Create call record")
    cl_cr.add_argument("--json", dest="json_data", type=parse_json_arg, help="Call fields as JSON")

    cl_upd = cl_sub.add_parser("update", help="Update call")
    cl_upd.add_argument("id", help="Call UUID")
    cl_upd.add_argument("--json", dest="json_data", type=parse_json_arg, help="Fields to update as JSON")

    cl_del = cl_sub.add_parser("delete", help="Delete call")
    cl_del.add_argument("id", help="Call UUID")

    cl_batch = cl_sub.add_parser("batch", help="Batch update calls")
    cl_batch.add_argument("ids", nargs="+", help="Call UUIDs")
    cl_batch.add_argument("--json", dest="json_data", type=parse_json_arg, help="Update fields as JSON")

    # --- transcripts ---
    tr = subs.add_parser("transcripts", help="Manage call transcripts")
    tr_sub = tr.add_subparsers(dest="action", required=True)

    tr_get = tr_sub.add_parser("get", help="Get transcript (formatted conversation)")
    tr_get.add_argument("call_id", help="Call UUID")

    tr_store = tr_sub.add_parser("store", help="Store/update transcript")
    tr_store.add_argument("call_id", help="Call UUID")
    tr_store.add_argument("--json", dest="json_data", type=parse_json_arg, help="Transcript JSON")
    tr_store.add_argument("--json-file", dest="json_data", type=parse_json_file, help="Read from JSON file")

    tr_del = tr_sub.add_parser("delete", help="Delete transcript")
    tr_del.add_argument("call_id", help="Call UUID")

    tr_url = tr_sub.add_parser("url", help="Get presigned download URL")
    tr_url.add_argument("call_id", help="Call UUID")

    # --- call (outbound) ---
    oc = subs.add_parser("call", help="Initiate outbound call")
    oc.add_argument("destination", help="Phone number in E.164 format (e.g. +15551234567)")
    oc.add_argument("--agent-id", required=True, help="Agent UUID")
    oc.add_argument("--phone-number-id", help="Phone number UUID (optional)")
    oc.add_argument("--call-id", help="Existing call UUID to reuse (optional)")
    oc.add_argument("--overrides", type=parse_json_arg, help="Agent overrides as JSON")

    # --- stats ---
    st = subs.add_parser("stats", help="Call analytics and trends")
    st_sub = st.add_subparsers(dest="action", required=True)

    st_agg = st_sub.add_parser("aggregate", help="Aggregate operations on calls")
    st_agg.add_argument("--op", required=True, choices=["count", "sum", "avg", "min", "max"], help="Operation")
    st_agg.add_argument("--field", help="Field to aggregate (required for sum/avg/min/max)")
    st_agg.add_argument("--group-by", help="Group results by field")
    st_agg.add_argument("--interval", choices=["day", "week", "month"], help="Time interval for grouping")
    st_agg.add_argument("--filter", "-f", action="append", help="Filter as key=value (repeatable)")

    st_tr = st_sub.add_parser("trends", help="Daily call trend data")
    st_tr.add_argument("--from", dest="date_from", required=True, help="Start date (ISO format)")
    st_tr.add_argument("--to", dest="date_to", required=True, help="End date (ISO format, max 365 days)")

    # --- recordings ---
    rec = subs.add_parser("recordings", help="Download call recordings")
    rec_sub = rec.add_subparsers(dest="action", required=True)

    rec_dl = rec_sub.add_parser("stream", help="Download recording to file or stdout")
    rec_dl.add_argument("call_id", help="Call UUID")
    rec_dl.add_argument("--url", required=True, help="Recording URL (from call's recording_url field)")
    rec_dl.add_argument("--output", help="Output file path (omit for stdout)")

    # --- fields (custom field definitions) ---
    fld = subs.add_parser("fields", help="Manage custom field definitions")
    fld_sub = fld.add_subparsers(dest="action", required=True)

    fld_ls = fld_sub.add_parser("list", help="List custom fields")
    fld_ls.add_argument("--entity-type", default=None, help="Filter by entity type (default: all)")

    fld_cr = fld_sub.add_parser("create", help="Create custom field")
    fld_cr.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                        help="Field definition as JSON")

    fld_upd = fld_sub.add_parser("update", help="Update custom field")
    fld_upd.add_argument("id", help="Field UUID")
    fld_upd.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                         help="Fields to update as JSON")

    fld_del = fld_sub.add_parser("delete", help="Delete custom field")
    fld_del.add_argument("id", help="Field UUID")

    fld_imp = fld_sub.add_parser("impact", help="Preview deletion impact")
    fld_imp.add_argument("id", help="Field UUID")

    # --- field-groups ---
    fg = subs.add_parser("field-groups", help="Manage custom field groups")
    fg_sub = fg.add_subparsers(dest="action", required=True)

    fg_sub.add_parser("list", help="List field groups with fields")

    fg_cr = fg_sub.add_parser("create", help="Create field group")
    fg_cr.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                       help="Group definition as JSON")

    fg_upd = fg_sub.add_parser("update", help="Update field group")
    fg_upd.add_argument("id", help="Group UUID")
    fg_upd.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                        help="Fields to update as JSON")

    fg_del = fg_sub.add_parser("delete", help="Delete field group")
    fg_del.add_argument("id", help="Group UUID")

    fg_reorder = fg_sub.add_parser("reorder", help="Reorder groups")
    fg_reorder.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                            help='Order as JSON: {"groups": [{"id": "...", "sort_order": 0}]}')

    fg_af = fg_sub.add_parser("add-field", help="Add field to group")
    fg_af.add_argument("id", help="Group UUID")
    fg_af.add_argument("field_id", help="Custom field UUID to add")

    fg_rf = fg_sub.add_parser("remove-field", help="Remove field from group")
    fg_rf.add_argument("id", help="Group UUID")
    fg_rf.add_argument("field_id", help="Custom field UUID to remove")

    fg_rof = fg_sub.add_parser("reorder-fields", help="Reorder fields within group")
    fg_rof.add_argument("id", help="Group UUID")
    fg_rof.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                        help='Order as JSON: {"fields": [{"id": "...", "sort_order": 0}]}')

    fg_uf = fg_sub.add_parser("update-field", help="Update field display settings in group")
    fg_uf.add_argument("id", help="Group UUID")
    fg_uf.add_argument("field_id", help="Custom field UUID")
    fg_uf.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                       help="Display settings as JSON")

    # --- schedules ---
    sch = subs.add_parser("schedules", help="Manage webhook schedules")
    sch_sub = sch.add_subparsers(dest="action", required=True)

    sch_sub.add_parser("list", help="List schedules with rules")

    sch_get = sch_sub.add_parser("get", help="Get schedule with rules")
    sch_get.add_argument("id", help="Schedule UUID")

    sch_cr = sch_sub.add_parser("create", help="Create schedule")
    sch_cr.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                        help="Schedule definition as JSON")

    sch_upd = sch_sub.add_parser("update", help="Update schedule (syncs rules)")
    sch_upd.add_argument("id", help="Schedule UUID")
    sch_upd.add_argument("--json", dest="json_data", type=parse_json_arg, required=True,
                         help="Fields to update as JSON")

    sch_del = sch_sub.add_parser("delete", help="Delete schedule")
    sch_del.add_argument("id", help="Schedule UUID")

    sch_prev = sch_sub.add_parser("preview", help="Preview rule evaluation at datetime")
    sch_prev.add_argument("id", help="Schedule UUID")
    sch_prev.add_argument("datetime", help="ISO datetime to evaluate")

    sch_exec = sch_sub.add_parser("executions", help="Get execution history")
    sch_exec.add_argument("id", help="Schedule UUID")
    sch_exec.add_argument("--per-page", type=int, help="Results per page")

    # --- settings ---
    subs.add_parser("settings", help="Get project-level settings")

    # --- projects ---
    proj = subs.add_parser("projects", help="List and inspect projects")
    proj_sub = proj.add_subparsers(dest="action", required=True)

    proj_ls = proj_sub.add_parser("list", help="List projects")
    proj_ls.add_argument("--is-active", type=parse_bool, default=None, help="Filter by active status")
    proj_ls.add_argument("--per-page", type=int, help="Results per page")

    proj_get = proj_sub.add_parser("get", help="Get project details")
    proj_get.add_argument("id", help="Project UUID")

    # --- phone-numbers ---
    pn = subs.add_parser("phone-numbers", help="List and inspect phone numbers")
    pn_sub = pn.add_subparsers(dest="action", required=True)

    pn_ls = pn_sub.add_parser("list", help="List phone numbers")
    pn_ls.add_argument("--is-active", type=parse_bool, default=None, help="Filter by active status")
    pn_ls.add_argument("--per-page", type=int, help="Results per page")

    pn_get = pn_sub.add_parser("get", help="Get phone number details")
    pn_get.add_argument("id", help="Phone number UUID")

    # --- providers ---
    prov = subs.add_parser("providers", help="List phone providers and types")
    prov_sub = prov.add_subparsers(dest="action", required=True)

    prov_ls = prov_sub.add_parser("list", help="List provider credentials")
    prov_ls.add_argument("--is-active", type=parse_bool, default=None, help="Filter by active status")
    prov_ls.add_argument("--provider-type", help="Filter by provider type")
    prov_ls.add_argument("--per-page", type=int, help="Results per page")

    prov_sub.add_parser("types", help="Get supported provider types")

    return parser


# ===================================================================
# Dispatch
# ===================================================================

DISPATCH = {
    "agents": {
        "list": agents_list,
        "default": agents_default,
        "get": agents_get,
        "update": agents_update,
        "delete": agents_delete,
    },
    "assets": {
        "list": assets_list,
        "get": assets_get,
        "create": assets_create,
        "update": assets_update,
        "delete": assets_delete,
    },
    "calls": {
        "list": calls_list,
        "get": calls_get,
        "create": calls_create,
        "update": calls_update,
        "delete": calls_delete,
        "batch": calls_batch,
    },
    "transcripts": {
        "get": transcripts_get,
        "store": transcripts_store,
        "delete": transcripts_delete,
        "url": transcripts_url,
    },
    "call": call_initiate,
    "stats": {
        "aggregate": stats_aggregate,
        "trends": stats_trends,
    },
    "recordings": {
        "stream": recordings_stream,
    },
    "fields": {
        "list": fields_list,
        "create": fields_create,
        "update": fields_update,
        "delete": fields_delete,
        "impact": fields_impact,
    },
    "field-groups": {
        "list": field_groups_list,
        "create": field_groups_create,
        "update": field_groups_update,
        "delete": field_groups_delete,
        "reorder": field_groups_reorder,
        "add-field": field_groups_add_field,
        "remove-field": field_groups_remove_field,
        "reorder-fields": field_groups_reorder_fields,
        "update-field": field_groups_update_field,
    },
    "schedules": {
        "list": schedules_list,
        "get": schedules_get,
        "create": schedules_create,
        "update": schedules_update,
        "delete": schedules_delete,
        "preview": schedules_preview,
        "executions": schedules_executions,
    },
    "settings": settings_get,
    "projects": {
        "list": projects_list,
        "get": projects_get,
    },
    "phone-numbers": {
        "list": phone_numbers_list,
        "get": phone_numbers_get,
    },
    "providers": {
        "list": providers_list,
        "types": providers_types,
    },
}


def main():
    global RAW_JSON

    parser = build_parser()
    args = parser.parse_args()

    RAW_JSON = getattr(args, "raw_json", False)

    resource = args.resource
    handler = DISPATCH.get(resource)

    if callable(handler):
        handler(args)
    elif isinstance(handler, dict):
        action = getattr(args, "action", None)
        fn = handler.get(action)
        if fn:
            fn(args)
        else:
            die(f"Unknown action: {resource} {action}")
    else:
        die(f"Unknown resource: {resource}")


if __name__ == "__main__":
    main()
