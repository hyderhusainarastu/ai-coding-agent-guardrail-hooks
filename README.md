# ai-coding-agent-guardrail-hooks

Guardrails for AI coding agents and the people who run them: a tool-neutral `guardrails check` CLI, a Claude Code hook adapter, and git hooks that stop your own `.env` values and protected-directory symlinks from being committed. Advisory, not a sandbox.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Works with

| Surface | How (prompt / native skill / CLI / hook / MCP) | Status |
|---|---|---|
| Claude Code | PreToolUse hook (`adapters/claude_code.py`), fail-open | adapter tested with JSON fixtures 2026-11-23 (Python 3.14); not tested inside a live Claude Code session |
| Any agent or human using git | git hooks (`pre-commit`, `pre-push`, `post-merge`), fail-closed | tested 2026-11-23, git on macOS, temp repos |
| Any tool that can run a command | CLI: `python3 -m guardrails check` | tested 2026-11-23 |
| Codex | git hooks, AGENTS.md; no adapter | not tested |
| Cursor | git hooks, AGENTS.md; no adapter | not tested |
| Gemini CLI | git hooks, GEMINI.md pointer; no adapter | not tested |
| Copilot | git hooks, pointer file; no adapter | not tested |
| Aider | git hooks; no adapter | not tested |
| ChatGPT / Claude.ai / Gemini (chat) | no prompt version: these cannot run hooks | not applicable |

Details per agent: [docs/other-agents.md](docs/other-agents.md).

## Quick start

```sh
git clone https://github.com/hyderhusainarastu/ai-coding-agent-guardrail-hooks tools/guardrails
cd tools/guardrails && python3 -m pip install -e .        # optional: gives you the `guardrails` command

# 1. Git hooks for the repository you want to protect (run inside that repo)
/path/to/tools/guardrails/install-git-hooks.sh            # core.hooksPath; or --copy, --uninstall

# 2. Claude Code: merge examples/claude-settings.json into .claude/settings.json
#    and adjust the tools/guardrails path.

# 3. Policy: copy examples/guardrails.json to guardrails.json at your repo root and edit.
```

Requires Python 3.10+ and git. No third-party runtime dependencies.

## Example

```
$ python3 -m guardrails check --tool read --path .env; echo "exit $?"
guardrails: denied: reading is denied by denied_read_globs: .env
exit 2

$ python3 -m guardrails check --tool bash --cmd "git push --force origin main"; echo "exit $?"
guardrails: denied: force push to a protected branch
exit 2

$ python3 -m guardrails check --tool write --path src/app.py; echo "exit $?"
exit 0
```

And a commit blocked by `env_value_guard` (the value itself is never printed):

```
env_value_guard: notes.md:2: contains the value of API_TOKEN
env_value_guard: commit refused. Remove the value from the staged file.
```

## Why the agent hook is fail-open and the git hooks are fail-closed

The Claude Code wiring is `sh -c '[ -f P ] && python3 -I P; exit $?'` with a 5 second timeout. If the file is missing, Python is broken or the adapter crashes, the tool call goes ahead (Claude Code treats any exit other than 2 as non-blocking, per its hooks docs). That is deliberate: a guard that wedges the agent gets deleted. So the agent hook is a speed bump that catches honest mistakes and common slips.

The git hooks are the boundary. They run inside git, see exactly what is about to be committed or pushed, and any error blocks. `GUARDRAILS_DISABLE=1` skips the agent hook only; the git hooks need both `GUARDRAILS_DISABLE=1` and `GUARDRAILS_DISABLE_GIT=1`. Each skip appends one content-free line (UTC time, hook name, `disabled`) to `.guardrails/audit.log`.

## What it checks

| Layer | Rule | Default |
|---|---|---|
| `guardrails check` | read or edit of denied globs | `**/.env`, `**/.env.*`, except `.env.example` |
| | write or edit outside `write_roots` (symlinks resolved) | the repo root |
| | command patterns | `--no-verify` |
| | force push to protected branches | `main`, `master` |
| | `rm -r` targets outside `write_roots` | on |
| | commands naming a denied path (`cat .env`) | on |
| `env_value_guard` (pre-commit) | any staged blob containing a value found in your `.env` files (values of 8+ characters) | on, fail closed |
| `symlink_guard` (pre-commit, pre-push) | symlink named or pointing into `protected_symlink_targets` | `.venv`, `venv`, `node_modules`, `data`, `models` |
| `post-merge` | warns if a protected directory became a symlink | warn only |
| `hooks/notify.py` | content-free completion notice (event name only) to ntfy, webhook or desktop | opt-in via env vars |

Policy lives in `guardrails.json` ([examples/guardrails.json](examples/guardrails.json)). The post-mortem that motivated the symlink guard is in [docs/postmortem-worktree-symlink.md](docs/postmortem-worktree-symlink.md); a recipe for stopping agent-run tests from calling paid APIs is in [docs/pytest-network-guard.md](docs/pytest-network-guard.md).

## Test

```sh
python3 -m pip install pytest
python3 -m pytest -q        # offline; network calls are mocked
```

## How it differs

- [gitleaks](https://github.com/gitleaks/gitleaks), [detect-secrets](https://github.com/Yelp/detect-secrets) and [pre-commit](https://pre-commit.com) find secret-shaped strings or run hook frameworks. `env_value_guard` is narrower: it only matches the exact values already in your own `.env` files, so it has no false positives from patterns and no coverage of secrets that are not in your `.env`. Use gitleaks as well.
- Claude Code's own permission rules and sandbox settings are the first-party way to restrict tools. This repo adds a policy file you can share across agents, plus git-side checks the agent cannot talk its way past.
- OS sandboxes and containers enforce; this repo does not.

## Limits

- Agent hooks see only the tool calls the agent reports. Shell indirection (`eval`, `sh -c "$(...)"`, scripts that call other scripts, variable expansion) can evade command patterns. For enforcement use an OS sandbox or a container.
- Humans and agents can bypass git hooks with `--no-verify`, or by not installing them in a clone. Repeat the same checks in CI.
- `env_value_guard` only catches your own exact `.env` values, single-line, 8+ characters by default. It does not catch other secrets; also run gitleaks. It holds values in memory while it runs and never prints or stores them.
- The symlink guard works on names and link targets, not on what the link resolves to on disk. It cannot undo a merge that already replaced a directory.
- The Claude Code adapter was tested against JSON fixtures that follow the hooks documentation, not inside a live session. File-tool field names (`file_path`, `notebook_path`, `path`) are accepted defensively.
- Glob matching is a small built-in implementation (`*`, `**`, `?`, leading `!` to allow), not full gitignore semantics.

## Related

- [palimnote-tools](https://github.com/hyderhusainarastu) catalog of small developer tools.

## Keywords

ai coding agents, guardrails, claude code hooks, PreToolUse, git hooks, pre-commit, .env protection, secret leak prevention, git worktree symlink, AGENTS.md

---
Part of palimnote-tools - more at https://github.com/hyderhusainarastu
