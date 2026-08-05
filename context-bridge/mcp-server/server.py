#!/usr/bin/env python3
"""Context Bridge MCP server.

This is intentionally dependency-free. It implements the small MCP stdio
surface needed by the plugin and stores records in SQLite outside the repo by
default, so installing the plugin does not modify a Codex project.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SERVER_NAME = "context-bridge"
SERVER_VERSION = "0.1.0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_data_dir() -> Path:
    configured = os.environ.get("CONTEXT_BRIDGE_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".context-bridge"


class Store:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "context-bridge.sqlite3"
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                title TEXT NOT NULL,
                question TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'registered',
                output TEXT,
                parent_task_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(parent_task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS contexts (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source_task_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(source_task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS task_contexts (
                task_id TEXT NOT NULL,
                context_id TEXT NOT NULL,
                relation TEXT NOT NULL DEFAULT 'attached',
                created_at TEXT NOT NULL,
                PRIMARY KEY(task_id, context_id),
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(context_id) REFERENCES contexts(id) ON DELETE CASCADE
            );
            """
        )
        self.db.commit()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        value = dict(row)
        for key in ("metadata_json",):
            if key in value:
                value[key[:-5]] = json.loads(value.pop(key) or "{}")
        return value

    def create_task(
        self,
        scope: str,
        title: str,
        question: str,
        task_id: str | None = None,
        parent_task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_id = task_id or f"task-{uuid.uuid4().hex[:10]}"
        timestamp = now()
        self.db.execute(
            """INSERT INTO tasks
            (id, scope, title, question, parent_task_id, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, scope, title, question, parent_task_id,
             json.dumps(metadata or {}, ensure_ascii=False), timestamp, timestamp),
        )
        self.db.commit()
        return self.get_task(task_id)  # type: ignore[return-value]

    def list_tasks(self, scope: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        clauses: list[str] = []
        params: list[str] = []
        if scope:
            clauses.append("scope = ?")
            params.append(scope)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        return [self._row(row) for row in self.db.execute(query, params)]  # type: ignore[list-item]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        task = self._row(row)
        if task:
            task["contexts"] = [
                self._row(context)
                for context in self.db.execute(
                    """SELECT c.* FROM contexts c
                    JOIN task_contexts tc ON tc.context_id = c.id
                    WHERE tc.task_id = ? ORDER BY c.created_at""",
                    (task_id,),
                )
            ]
        return task

    def complete_task(self, task_id: str, output: str, status: str = "completed") -> dict[str, Any]:
        timestamp = now()
        cursor = self.db.execute(
            "UPDATE tasks SET output = ?, status = ?, updated_at = ? WHERE id = ?",
            (output, status, timestamp, task_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Unknown task: {task_id}")
        self.db.commit()
        return self.get_task(task_id)  # type: ignore[return-value]

    def save_context(
        self,
        scope: str,
        title: str,
        content: str,
        kind: str = "note",
        context_id: str | None = None,
        source_task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context_id = context_id or f"context-{uuid.uuid4().hex[:10]}"
        timestamp = now()
        self.db.execute(
            """INSERT INTO contexts
            (id, scope, title, kind, content, source_task_id, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (context_id, scope, title, kind, content, source_task_id,
             json.dumps(metadata or {}, ensure_ascii=False), timestamp),
        )
        self.db.commit()
        return self.get_context(context_id)  # type: ignore[return-value]

    def get_context(self, context_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM contexts WHERE id = ?", (context_id,)).fetchone()
        return self._row(row)

    def search_context(self, query: str, scope: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM contexts WHERE (title LIKE ? OR content LIKE ?)"
        needle = f"%{query}%"
        params: list[str] = [needle, needle]
        if scope:
            sql += " AND scope = ?"
            params.append(scope)
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY created_at DESC"
        return [self._row(row) for row in self.db.execute(sql, params)]  # type: ignore[list-item]

    def attach_context(self, task_id: str, context_id: str, relation: str = "attached") -> dict[str, Any]:
        if not self.get_task(task_id):
            raise ValueError(f"Unknown task: {task_id}")
        if not self.get_context(context_id):
            raise ValueError(f"Unknown context: {context_id}")
        self.db.execute(
            "INSERT OR REPLACE INTO task_contexts (task_id, context_id, relation, created_at) VALUES (?, ?, ?, ?)",
            (task_id, context_id, relation, now()),
        )
        self.db.commit()
        return self.get_task(task_id)  # type: ignore[return-value]

    def promote_context(
        self,
        context_id: str,
        target_scope: str,
        title: str | None = None,
        kind: str = "promoted",
    ) -> dict[str, Any]:
        source = self.get_context(context_id)
        if not source:
            raise ValueError(f"Unknown context: {context_id}")
        metadata = dict(source.get("metadata") or {})
        metadata["promoted_from"] = context_id
        metadata["source_scope"] = source["scope"]
        return self.save_context(
            scope=target_scope,
            title=title or source["title"],
            content=source["content"],
            kind=kind,
            source_task_id=source.get("source_task_id"),
            metadata=metadata,
        )


TOOLS = [
    {
        "name": "cb_create_task",
        "description": "Register a logical cross-thread task reference. This does not launch a Codex agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "description": "Scope such as codex-project:brand-ai, personal, or temporary."},
                "title": {"type": "string"},
                "question": {"type": "string"},
                "task_id": {"type": "string", "description": "Optional readable ID such as brand-x1."},
                "parent_task_id": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["scope", "title", "question"],
        },
    },
    {
        "name": "cb_list_tasks",
        "description": "List registered task references in a scope.",
        "inputSchema": {"type": "object", "properties": {"scope": {"type": "string"}, "status": {"type": "string"}}},
    },
    {
        "name": "cb_get_task",
        "description": "Retrieve a task, its stored output, and attached context capsules.",
        "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "include_output": {"type": "boolean"}}, "required": ["task_id"]},
    },
    {
        "name": "cb_complete_task",
        "description": "Store a result supplied by the current agent for a registered task.",
        "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "output": {"type": "string"}, "status": {"type": "string"}}, "required": ["task_id", "output"]},
    },
    {
        "name": "cb_save_context",
        "description": "Save a concise, explicit context capsule without changing durable project memory elsewhere.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string"}, "title": {"type": "string"}, "content": {"type": "string"},
                "kind": {"type": "string", "description": "fact, decision, constraint, assumption, research, or note"},
                "context_id": {"type": "string"}, "source_task_id": {"type": "string"}, "metadata": {"type": "object"},
            },
            "required": ["scope", "title", "content"],
        },
    },
    {
        "name": "cb_search_context",
        "description": "Search saved context capsules by text and optional scope.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "scope": {"type": "string"}, "kind": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "cb_attach_context",
        "description": "Attach a context capsule to a task for read-only use; it does not promote or merge it.",
        "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "context_id": {"type": "string"}, "relation": {"type": "string"}}, "required": ["task_id", "context_id"]},
    },
    {
        "name": "cb_promote_context",
        "description": "Explicitly copy a context capsule into another scope with provenance.",
        "inputSchema": {"type": "object", "properties": {"context_id": {"type": "string"}, "target_scope": {"type": "string"}, "title": {"type": "string"}, "kind": {"type": "string"}}, "required": ["context_id", "target_scope"]},
    },
]


def result(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}]}


def error(message: str) -> dict[str, Any]:
    return {"isError": True, "content": [{"type": "text", "text": message}]}


def call_tool(store: Store, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "cb_create_task":
        return result(store.create_task(**args))
    if name == "cb_list_tasks":
        return result(store.list_tasks(**args))
    if name == "cb_get_task":
        task = store.get_task(args["task_id"])
        if not task:
            return error(f"Unknown task: {args['task_id']}")
        if not args.get("include_output", True):
            task.pop("output", None)
        return result(task)
    if name == "cb_complete_task":
        return result(store.complete_task(args["task_id"], args["output"], args.get("status", "completed")))
    if name == "cb_save_context":
        return result(store.save_context(**args))
    if name == "cb_search_context":
        return result(store.search_context(**args))
    if name == "cb_attach_context":
        return result(store.attach_context(**args))
    if name == "cb_promote_context":
        return result(store.promote_context(**args))
    return error(f"Unknown tool: {name}")


def handle(store: Store, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            params = message.get("params") or {}
            return {"jsonrpc": "2.0", "id": request_id, "result": call_tool(store, params["name"], params.get("arguments") or {})}
        except Exception as exc:  # MCP must return a structured tool error, not die.
            return {"jsonrpc": "2.0", "id": request_id, "result": error(str(exc))}
    if request_id is not None:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return None


def main() -> None:
    store = Store()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle(store, message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
