# Context Bridge

Context Bridge is a Codex Plugin and local MCP server for carrying **selected, explicit context** across Codex threads and projects.

It is intentionally not a replacement for Codex Projects, threads, or parallel agents:

- Codex owns task execution and native project boundaries.
- Context Bridge stores context capsules, task references, provenance, and explicit promotion.
- Nothing is automatically merged into a durable scope.
- It does not interrupt or inject messages into a Codex turn that is already running.

## What it adds

- Save facts, decisions, constraints, assumptions, and research as context capsules.
- Search and attach capsules to a logical task without copying an entire conversation.
- Promote a reviewed capsule into another scope with provenance.
- Keep `codex-project:*`, `personal`, and `temporary` context separate.
- Store data in a local SQLite database outside the repository by default.

## MCP tools

| Tool | Purpose |
| --- | --- |
| `cb_create_task` | Register a readable task reference such as `brand-x1`; does not launch an Agent. |
| `cb_list_tasks` | List task references by scope or status. |
| `cb_get_task` | Read a task, its output, and attached capsules. |
| `cb_complete_task` | Store a result supplied by the current agent. |
| `cb_save_context` | Save an explicit context capsule. |
| `cb_search_context` | Search saved capsules. |
| `cb_attach_context` | Attach a capsule to a task without merging it. |
| `cb_promote_context` | Explicitly copy a capsule into another scope. |

## Typical use

```text
Save the confirmed budget and target audience as context in codex-project:brand-ai.
```

```text
Search Context Bridge for the competitor analysis in codex-project:brand-ai,
then use it as read-only context for this answer.
```

```text
Promote the reviewed user-persona capsule from codex-project:brand-ai
to codex-project:personal-brand, preserving provenance.
```

The Skill in `skills/context-bridge/SKILL.md` provides the behavioral rules for these calls.

## Local data

The default database is:

```text
~/.context-bridge/context-bridge.sqlite3
```

Set `CONTEXT_BRIDGE_DATA_DIR` to use a different local directory. The plugin does not write into a Codex repository unless you explicitly configure it to do so.

## Development

The MCP server uses only Python's standard library. Run the smoke test:

```bash
python3 tests/test_store.py
```

Run the protocol manually:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 mcp-server/server.py
```

## Scope

This first version is a context bridge. It does not pretend to provide a second Codex scheduler or a live second input box. Those behaviors belong to the Codex host.

## Install from GitHub

After the repository is pushed, add the Git Marketplace from the branch that contains the plugin:

```bash
codex plugin marketplace add drink-water-everday/context-bridge \
  --ref codex/context-bridge \
  --sparse .agents/plugins/marketplace.json \
  --sparse plugins/context-bridge

codex plugin add context-bridge@context-bridge-marketplace
```

Start a new Codex thread after installation so the Skill and MCP tools are loaded.
