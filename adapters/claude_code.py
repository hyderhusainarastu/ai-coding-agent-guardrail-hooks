#!/usr/bin/env python3
"""Claude Code PreToolUse adapter: maps the hook JSON on stdin onto guardrails.core.check.

Hook contract (docs: https://code.claude.com/docs/en/hooks, read 2026-11-23):
  stdin JSON has cwd, hook_event_name, tool_name, tool_input.
  Exit 2 blocks the tool call and stderr is shown to the model; any other
  non-zero exit is a non-blocking error and the call proceeds.
The tool_input field names for file tools (file_path, notebook_path, path) were not
re-read from the docs in that pass; this adapter accepts all three and ignores others.

Fail-open by design: any internal error exits 0. This is a speed bump, not a boundary.
Kill switch: GUARDRAILS_DISABLE=1 skips the check and appends a content-free audit line.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

TOOL_KIND = {
    "Read": "read", "Glob": "read", "Grep": "read",
    "Write": "write",
    "Edit": "edit", "MultiEdit": "edit", "NotebookEdit": "edit",
    "Bash": "bash",
}


def extract(payload: dict):
    """Return (kind, paths, cmd, cwd) from a PreToolUse payload."""
    kind = TOOL_KIND.get(payload.get("tool_name", ""), "other")
    ti = payload.get("tool_input") or {}
    paths = [ti[k] for k in ("file_path", "notebook_path", "path") if isinstance(ti.get(k), str)]
    cmd = ti.get("command") if isinstance(ti.get("command"), str) else None
    return kind, paths, cmd, payload.get("cwd") or os.getcwd()


def run(stdin_text: str) -> int:
    try:
        from guardrails import core
        payload = json.loads(stdin_text)
        kind, paths, cmd, cwd = extract(payload)
        root = core.find_repo_root(cwd)
        if os.environ.get("GUARDRAILS_DISABLE") == "1":
            core.audit_disabled(root, "claude_code")
            return 0
        cfg = core.load_config(os.environ.get("GUARDRAILS_CONFIG"), root)
        d = core.check(kind, paths, cmd, cfg, root, cwd)
    except Exception as exc:  # fail open
        sys.stderr.write(f"guardrails adapter error (allowing): {type(exc).__name__}\n")
        return 0
    if d.allowed:
        return 0
    sys.stderr.write(f"guardrails: denied: {d.reason}\n")
    return 2


if __name__ == "__main__":
    sys.exit(run(sys.stdin.read()))
