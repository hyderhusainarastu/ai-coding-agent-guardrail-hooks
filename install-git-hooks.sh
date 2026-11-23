#!/bin/sh
# Install the git hooks into the current repository.
#   ./install-git-hooks.sh              set core.hooksPath to this checkout's git-hooks/
#   ./install-git-hooks.sh --copy       copy hooks (and the guardrails package) into .git/hooks
#   ./install-git-hooks.sh --uninstall  undo either
#   --force                             overwrite foreign hooks or a different hooksPath
set -eu
HERE=$(cd "$(dirname "$0")" && pwd -P)
SRC="$HERE/git-hooks"
LIB="$HERE/guardrails"
MODE=path; FORCE=0
for a in "$@"; do
  case "$a" in
    --copy) MODE=copy ;; --uninstall) MODE=uninstall ;; --force) FORCE=1 ;;
    *) echo "usage: $0 [--copy|--uninstall] [--force]" >&2; exit 64 ;;
  esac
done
ROOT=$(git rev-parse --show-toplevel)
HOOKS=$(cd "$ROOT" && git rev-parse --path-format=absolute --git-path hooks)
MARK="guardrails-managed"
HOOK_NAMES="pre-commit pre-push post-merge"
SUPPORT="_gate.sh env_value_guard.py symlink_guard.py"

case "$MODE" in
  path)
    cur=$(git -C "$ROOT" config --local --get core.hooksPath || true)
    if [ -n "$cur" ] && [ "$cur" != "$SRC" ] && [ "$FORCE" != 1 ]; then
      echo "core.hooksPath is already set elsewhere; use --force to replace it" >&2; exit 1
    fi
    git -C "$ROOT" config --local core.hooksPath "$SRC"
    echo "core.hooksPath set to $SRC" ;;
  copy)
    mkdir -p "${HOOKS:?}/_lib"
    for h in $HOOK_NAMES; do
      if [ -e "${HOOKS:?}/$h" ] && ! grep -q "$MARK" "${HOOKS:?}/$h" 2>/dev/null && [ "$FORCE" != 1 ]; then
        echo "foreign hook exists: $h (use --force to overwrite)" >&2; exit 1
      fi
    done
    for h in $HOOK_NAMES; do
      { head -1 "$SRC/$h"; echo "# $MARK"; tail -n +2 "$SRC/$h"; } > "${HOOKS:?}/$h"
      chmod +x "${HOOKS:?}/$h"
    done
    for f in $SUPPORT; do cp "$SRC/$f" "${HOOKS:?}/$f"; done
    chmod +x "${HOOKS:?}/env_value_guard.py" "${HOOKS:?}/symlink_guard.py"
    cp -R "$LIB" "${HOOKS:?}/_lib/"
    echo "copied hooks to $HOOKS" ;;
  uninstall)
    cur=$(git -C "$ROOT" config --local --get core.hooksPath || true)
    if [ "$cur" = "$SRC" ]; then git -C "$ROOT" config --local --unset core.hooksPath; echo "unset core.hooksPath"; fi
    for h in $HOOK_NAMES; do
      if grep -q "$MARK" "${HOOKS:?}/$h" 2>/dev/null; then rm -f "${HOOKS:?}/${h:?}"; echo "removed $h"; fi
    done
    if [ ! -e "${HOOKS:?}/pre-commit" ] && [ ! -e "${HOOKS:?}/pre-push" ] && [ ! -e "${HOOKS:?}/post-merge" ]; then
      for f in $SUPPORT; do rm -f "${HOOKS:?}/${f:?}"; done
      rm -r "${HOOKS:?}/_lib/guardrails" 2>/dev/null || true
      rmdir "${HOOKS:?}/_lib" 2>/dev/null || true
    fi ;;
esac
