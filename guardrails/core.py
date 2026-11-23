"""Pure policy: given a tool kind, paths and a command, allow or deny.

Knows nothing about any agent's payload format. Standard library only.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Optional

TOOLS = ("read", "write", "edit", "bash", "other")

DEFAULTS = {
    "write_roots": ["${REPO_ROOT}"],
    "denied_read_globs": ["**/.env", "**/.env.*", "!**/.env.example"],
    "protected_branches": ["main", "master"],
    "denied_cmd_patterns": [r"--no-verify\b"],
    "protected_symlink_targets": [".venv", "venv", "node_modules", "data", "models"],
    "env_value_globs": [".env", ".env.*", "**/.env", "**/.env.*"],
    "env_value_min_length": 8,
}


@dataclass
class Config:
    write_roots: list = field(default_factory=lambda: list(DEFAULTS["write_roots"]))
    denied_read_globs: list = field(default_factory=lambda: list(DEFAULTS["denied_read_globs"]))
    protected_branches: list = field(default_factory=lambda: list(DEFAULTS["protected_branches"]))
    denied_cmd_patterns: list = field(default_factory=lambda: list(DEFAULTS["denied_cmd_patterns"]))
    protected_symlink_targets: list = field(default_factory=lambda: list(DEFAULTS["protected_symlink_targets"]))
    env_value_globs: list = field(default_factory=lambda: list(DEFAULTS["env_value_globs"]))
    env_value_min_length: int = DEFAULTS["env_value_min_length"]


@dataclass
class Decision:
    allowed: bool
    reason: str = ""


def load_config(path: Optional[str] = None, repo_root: Optional[str] = None) -> Config:
    """Load guardrails.json. Missing file means defaults; bad JSON raises ValueError."""
    if path is None and repo_root:
        cand = os.path.join(repo_root, "guardrails.json")
        path = cand if os.path.isfile(cand) else None
    cfg = Config()
    if not path:
        return cfg
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read config {os.path.basename(path)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    for key, value in data.items():
        if key not in DEFAULTS:
            raise ValueError(f"unknown config key: {key}")
        if key == "env_value_min_length":
            if not isinstance(value, int):
                raise ValueError(f"{key} must be an integer")
        elif not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            raise ValueError(f"{key} must be a list of strings")
        setattr(cfg, key, value)
    for pat in cfg.denied_cmd_patterns:
        try:
            re.compile(pat)
        except re.error as exc:
            raise ValueError(f"bad regex in denied_cmd_patterns: {exc}") from exc
    return cfg


def find_repo_root(start: str) -> str:
    """Nearest ancestor holding .git (directory or worktree file); else start."""
    cur = os.path.realpath(start)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.realpath(start)
        cur = parent


def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def glob_match(globs, path: str) -> bool:
    """True if path matches a positive glob and no '!' glob. Path uses '/' and no leading '/'."""
    path = path.replace(os.sep, "/").lstrip("/")
    hit = False
    for g in globs:
        if g.startswith("!"):
            if glob_to_regex(g[1:]).match(path):
                return False
        elif glob_to_regex(g).match(path):
            hit = True
    return hit


def _resolve(path: str, cwd: str) -> str:
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.realpath(os.path.expanduser(path))


def _roots(cfg: Config, repo_root: str) -> list:
    return [os.path.realpath(r.replace("${REPO_ROOT}", repo_root)) for r in cfg.write_roots]


def _inside(path: str, roots: list) -> bool:
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def _force_push_to_protected(cmd: str, branches: list) -> bool:
    if not re.search(r"\bgit\b.*\bpush\b", cmd):
        return False
    forced = re.search(r"(?:^|\s)(?:--force(?:-with-lease)?(?:=\S+)?|-[a-zA-Z]*f[a-zA-Z]*)(?:\s|$)", cmd)
    plus_ref = re.search(r"\s\+\S+", cmd)
    if not (forced or plus_ref):
        return False
    for b in branches:
        if re.search(r"(?:^|[\s:+/])" + re.escape(b) + r"(?:\s|$)", cmd):
            return True
    return False


def _rm_outside(tokens: list, cwd: str, roots: list) -> Optional[str]:
    for i, tok in enumerate(tokens):
        if os.path.basename(tok) != "rm":
            continue
        recursive, targets = False, []
        for arg in tokens[i + 1:]:
            if arg in (";", "&&", "||", "|"):
                break
            if arg.startswith("--"):
                recursive = recursive or arg == "--recursive"
            elif arg.startswith("-") and len(arg) > 1:
                recursive = recursive or bool(set(arg[1:]) & {"r", "R"})
            else:
                targets.append(arg)
        if not recursive:
            continue
        for t in targets:
            if not _inside(_resolve(t, cwd), roots):
                return f"recursive rm target outside write roots: {t}"
    return None


def check(tool: str, paths=(), cmd: Optional[str] = None, cfg: Optional[Config] = None,
          repo_root: Optional[str] = None, cwd: Optional[str] = None) -> Decision:
    """Decide on one tool call. Never raises for ordinary input."""
    cfg = cfg or Config()
    cwd = os.path.realpath(cwd or os.getcwd())
    repo_root = os.path.realpath(repo_root) if repo_root else find_repo_root(cwd)
    if tool not in TOOLS:
        return Decision(False, f"unknown tool kind: {tool}")
    roots = _roots(cfg, repo_root)

    for p in paths:
        real = _resolve(p, cwd)
        if tool in ("read", "edit"):
            for cand in {real, os.path.normpath(os.path.join(cwd, p)) if not os.path.isabs(p) else os.path.normpath(p)}:
                if glob_match(cfg.denied_read_globs, cand):
                    return Decision(False, f"reading is denied by denied_read_globs: {os.path.basename(p)}")
        if tool in ("write", "edit") and not _inside(real, roots):
            return Decision(False, f"write outside allowed roots: {p}")

    if tool == "bash" and cmd:
        for pat in cfg.denied_cmd_patterns:
            if re.search(pat, cmd):
                return Decision(False, f"command matches denied pattern: {pat}")
        if _force_push_to_protected(cmd, cfg.protected_branches):
            return Decision(False, "force push to a protected branch")
        try:
            tokens = shlex.split(cmd, posix=True)
        except ValueError:
            tokens = cmd.split()
        why = _rm_outside(tokens, cwd, roots)
        if why:
            return Decision(False, why)
        for tok in tokens:
            if "/" in tok or tok.startswith(".env"):
                if glob_match(cfg.denied_read_globs, os.path.normpath(os.path.join(cwd, tok))) or \
                        glob_match(cfg.denied_read_globs, os.path.normpath(tok)):
                    return Decision(False, f"command touches a denied path: {os.path.basename(tok)}")
    return Decision(True)


def audit_disabled(repo_root: str, hook: str) -> None:
    """Append a content-free line to .guardrails/audit.log. Never raises."""
    try:
        d = os.path.join(repo_root, ".guardrails")
        os.makedirs(d, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(os.path.join(d, "audit.log"), "a", encoding="utf-8") as f:
            f.write(f"{stamp} {hook} disabled\n")
    except OSError:
        pass
