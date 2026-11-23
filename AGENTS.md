# ai-coding-agent-guardrail-hooks

Guardrail policy, a Claude Code hook adapter and git hooks for AI coding agents. Advisory, not a sandbox.

## Using this in your project

Rules for any agent working in a repository that uses these guardrails (copy them into your own AGENTS.md):

- Never read `.env` files (`.env.example` is fine). If you need a secret, ask the user to run the prompt or command themselves.
- Never use `--no-verify` or any option that skips git hooks.
- Never run `git add -A` or `git add .` inside a git worktree. Add files by name.
- Write only under the allowed roots (by default the repository root).
- Never force-push to a protected branch (`main`, `master`).
- If `guardrails` denies an action, stop and report the denial text to the user. Do not look for another way to do the same thing.
- Do not set `GUARDRAILS_DISABLE` or `GUARDRAILS_DISABLE_GIT` yourself.

Commands:

- `python3 -m guardrails check --tool {read,write,edit,bash,other} [--path P]... [--cmd STR] [--config guardrails.json]`
- Exit codes: 0 allow, 2 deny (reason on stderr), 64 usage or config error.
- Git hooks: `./install-git-hooks.sh` (core.hooksPath), `--copy`, `--uninstall`. They exit 1 to block.
- No PROMPT.md: CLI and hooks.

## Working on this repo

- Setup: `python3 -m pip install -e . pytest`
- Test: `python3 -m pytest -q` (runs offline; network calls are mocked).
- Python 3.10+, standard library only. Do not print `.env` values in code, tests or logs. Build secret-like test fixtures at runtime.
- Do not write generated files into `.guardrails/`; it holds only the audit log.

<!-- cc-only -->
Claude Code: the PreToolUse adapter is `adapters/claude_code.py`; wiring is in `examples/claude-settings.json`.
<!-- /cc-only -->
