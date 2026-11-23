#!/usr/bin/env python3
"""Fail closed if a staged blob contains one of your own .env values.

Collects values from .env files under the repo (globs from guardrails.json, key
env_value_globs), then scans staged content for those exact strings. Values are held
in memory only; the report names file:line and the variable NAME, never the value.
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))
for _cand in (os.path.join(_HERE, ".."), os.path.join(_HERE, "_lib")):
    if os.path.isdir(os.path.join(_cand, "guardrails")):
        sys.path.insert(0, _cand)
        break
from guardrails import core  # noqa: E402


SKIP_SUFFIXES = (".example", ".sample", ".template", ".dist")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__"}


def git_bytes(*args) -> bytes:
    r = subprocess.run(["git", *args], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed")
    return r.stdout


def parse_env(text: str):
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, _, val = line.partition("=")
        name, val = name.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        elif " #" in val:
            val = val.split(" #", 1)[0].rstrip()
        if name:
            yield name, val


def collect(root: str, globs, min_len: int) -> dict:
    """Map value -> variable name (first wins)."""
    values = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            if rel.endswith(SKIP_SUFFIXES) or not core.glob_match(globs, rel):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8", errors="replace") as f:
                for name, val in parse_env(f.read()):
                    if len(val) >= min_len:
                        values.setdefault(val, name)
    return values


def staged_paths():
    out = git_bytes("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [p.decode("utf-8", "replace") for p in out.split(b"\0") if p]


def scan(root: str, cfg) -> list:
    values = collect(root, cfg.env_value_globs, cfg.env_value_min_length)
    hits = []
    if not values:
        return hits
    encoded = {v.encode(): n for v, n in values.items()}
    for path in staged_paths():
        data = git_bytes("show", ":" + path)
        for enc, name in encoded.items():
            if enc in data:
                for i, line in enumerate(data.split(b"\n"), 1):
                    if enc in line:
                        hits.append((path, i, name))
    return hits


def main() -> int:
    try:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                              text=True, check=True).stdout.strip()
        cfg = core.load_config(None, root)
        hits = scan(root, cfg)
    except Exception as exc:
        sys.stderr.write(f"env_value_guard: error, failing closed: {type(exc).__name__}\n")
        return 1
    for path, line, name in hits:
        sys.stderr.write(f"env_value_guard: {path}:{line}: contains the value of {name}\n")
    if hits:
        sys.stderr.write("env_value_guard: commit refused. Remove the value from the staged file.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
