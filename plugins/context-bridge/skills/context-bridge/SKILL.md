---
name: context-bridge
description: Use Context Bridge to save, find, attach, and explicitly merge selected context across Codex threads and projects. Do not recreate Codex's native Projects, threads, or parallel agents.
---

# Context Bridge

Context Bridge is a context ledger, not a replacement for Codex Projects or Codex's native parallel-agent workflow.

Use it when the user wants to:

- preserve a confirmed fact, decision, constraint, or research finding for another thread;
- find a prior task or context capsule by an explicit ID or search phrase;
- attach selected context to a task without changing project memory;
- promote a reviewed result into a project or personal scope;
- keep project, personal, and temporary context separate.

Do not use it merely because Codex can already run a parallel task or create another thread. Codex should own execution; Context Bridge should own explicit context portability and provenance.

## Scope rules

Use an explicit scope whenever possible:

- `codex-project:<name>` for context belonging to the current Codex project;
- `personal` for user-level context that should not enter a project;
- `temporary` for context that should be easy to find during the current workflow but should not be treated as durable memory;
- `cross-project:<name>` only when the user explicitly requests a bridge between projects.

Never copy a whole conversation when a short, structured context capsule is sufficient. A capsule should contain only the useful facts, decisions, constraints, assumptions, and provenance.

## Default safety behavior

1. Reading or attaching context is read-only.
2. Do not promote or merge anything into a durable scope without explicit user intent such as “保存到项目记忆”, “合并到项目”, or “promote this”.
3. Do not silently import project-private context into a different project.
4. If the user refers to an unknown task ID, list matching tasks or ask for clarification; do not guess.
5. If a task is still running, report its status. Context Bridge does not interrupt or inject into a Codex turn that is already running.

## Suggested workflow

When a turn produces durable value:

1. Extract a concise capsule.
2. Call `cb_save_context` with the chosen scope, title, content, kind, and source task ID when known.
3. Return the generated context ID to the user.

When the user says “引用 X1” or `@task X1`:

1. Call `cb_get_task` or `cb_search_context`.
2. Present the stored result or attach it to the current task with `cb_attach_context`.
3. Keep the attachment read-only unless the user explicitly asks to merge it.

When the user asks to merge a result:

1. Retrieve the source context.
2. Summarize exactly what will be promoted.
3. Call `cb_promote_context` only after the user's instruction is explicit.

## Tool intent

- `cb_create_task`: register a logical task/reference; it does not launch another Codex agent.
- `cb_list_tasks`: show tasks in a scope.
- `cb_get_task`: retrieve one task and its output.
- `cb_complete_task`: store a task result supplied by the current agent.
- `cb_save_context`: save a structured context capsule.
- `cb_search_context`: find capsules by scope and text.
- `cb_attach_context`: attach a capsule to a task without changing its scope.
- `cb_promote_context`: explicitly copy a capsule into another scope with provenance.

## Response conventions

Use human-readable IDs such as `brand-x1` or `brand-context-001` when creating records. Tell the user whether a result was only attached, or actually promoted into durable project memory.
