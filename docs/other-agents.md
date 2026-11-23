# Other agents

The `guardrails check` CLI is tool-neutral: it takes a tool kind, paths and a command, and exits 0 (allow) or 2 (deny). Only the Claude Code adapter in this repo has been written and tested. Everything below is a plan, not a shipped adapter.

| Agent | Git hooks | AGENTS.md rules | Wrap `guardrails check` in the tool's own hook or approval system | Status |
|---|---|---|---|---|
| Claude Code | yes | yes | `adapters/claude_code.py` (PreToolUse) | git hooks and adapter: tested 2026-11-23 (fixtures, no live agent session) |
| Codex | yes | read natively | check the Codex docs for command hooks or approval rules | not tested |
| Cursor | yes | read natively | check the Cursor docs for hooks | not tested |
| Gemini CLI | yes | via GEMINI.md pointer | check the Gemini CLI docs for hooks | not tested |
| Copilot | yes | via `.github/copilot-instructions.md` pointer | none known | not tested |
| Aider | yes | via `CONVENTIONS.md` or a read-only file argument | none known; Aider has a `--git-commit-verify` option that controls whether git commit hooks run | not tested |

## What works for every agent

1. **Git hooks.** The agent commits through git, so `./install-git-hooks.sh` protects all of them, and humans too. This is the strongest layer here because it fails closed.
2. **AGENTS.md rules.** Copy the rules in this repo's `AGENTS.md` into the project's own. Agents that read the file follow it most of the time; nothing enforces it.
3. **CLI wrapper.** If your tool can run a command before a tool call and treat a non-zero exit as a block, call `python3 -m guardrails check --tool bash --cmd "$COMMAND"`, mapping the tool's own payload to `--tool`, `--path` and `--cmd`. Write that mapping as a small adapter and add a fixture test, as `tests/test_adapter.py` does for Claude Code.

## What does not work

Do not assume an agent honours these files because they exist. Test with a harmless denied action (for example, ask it to read a `.env.example`-style decoy named `.env` that holds no real values) and watch what happens.
