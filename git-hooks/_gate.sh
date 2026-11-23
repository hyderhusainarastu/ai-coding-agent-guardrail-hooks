# Sourced by the hooks. Sets GUARDRAILS_SKIP=1 only when both kill-switch variables are set.
GUARDRAILS_SKIP=0
if [ "${GUARDRAILS_DISABLE:-}" = "1" ] && [ "${GUARDRAILS_DISABLE_GIT:-}" = "1" ]; then
  GUARDRAILS_SKIP=1
  _root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  mkdir -p "$_root/.guardrails" 2>/dev/null
  printf '%s %s disabled\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$GUARDRAILS_HOOK" >> "$_root/.guardrails/audit.log" 2>/dev/null
fi
