#!/usr/bin/env python3
"""Refuse symlinks that point into protected targets (fail closed).

Modes:
  symlink_guard.py --staged            check the index (pre-commit)
  symlink_guard.py --range A..B        check commits in a range (pre-push)
  symlink_guard.py --post-merge        warn if protected dirs in the work tree are symlinks
A symlink is refused if its own name is protected, or any component of its target is.
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



def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed")
    return r.stdout


def toplevel() -> str:
    return git("rev-parse", "--show-toplevel").strip()


def target_is_protected(link_path: str, target: str, protected) -> str:
    """Return the protected name hit, or ''."""
    prot = set(protected)
    if os.path.basename(link_path) in prot:
        return os.path.basename(link_path)
    for part in target.replace("\\", "/").split("/"):
        if part in prot:
            return part
    return ""


def blob_text(sha: str) -> str:
    return git("cat-file", "-p", sha).rstrip("\n")


def staged_links():
    out = git("ls-files", "-s", "-z")
    for rec in filter(None, out.split("\0")):
        meta, path = rec.split("\t", 1)
        mode, sha, _stage = meta.split()
        if mode == "120000":
            yield path, sha


def range_links(spec: str):
    out = git("log", "--raw", "--no-abbrev", "--format=", "-m", *spec.split())
    seen = set()
    for line in out.splitlines():
        if not line.startswith(":"):
            continue
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) >= 5 and fields[1] == "120000" and (path, fields[3]) not in seen:
            seen.add((path, fields[3]))
            yield path, fields[3]


def report(links, protected) -> int:
    bad = 0
    for path, sha in links:
        hit = target_is_protected(path, blob_text(sha), protected)
        if hit:
            bad += 1
            sys.stderr.write(f"symlink_guard: {path} is a symlink involving protected name '{hit}'\n")
    if bad:
        sys.stderr.write("symlink_guard: refused. Unstage the symlink, or edit protected_symlink_targets in guardrails.json.\n")
    return 1 if bad else 0


def main(argv) -> int:
    try:
        root = toplevel()
        cfg = core.load_config(None, root)
        if "--post-merge" in argv:
            for name in cfg.protected_symlink_targets:
                if os.path.islink(os.path.join(root, name)):
                    sys.stderr.write(f"WARNING: '{name}' is now a symlink in this work tree. "
                                     "Check that it did not replace a real directory.\n")
            return 0
        if "--staged" in argv:
            return report(list(staged_links()), cfg.protected_symlink_targets)
        if "--range" in argv:
            spec = argv[argv.index("--range") + 1]
            return report(list(range_links(spec)), cfg.protected_symlink_targets)
        sys.stderr.write("usage: symlink_guard.py --staged | --range A..B | --post-merge\n")
        return 64
    except Exception as exc:
        if "--post-merge" in argv:
            return 0
        sys.stderr.write(f"symlink_guard: error, failing closed: {type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
