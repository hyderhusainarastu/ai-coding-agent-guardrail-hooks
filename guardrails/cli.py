"""guardrails check --tool {read,write,edit,bash,other} [--path P]... [--cmd STR] [--config F]

Exit 0 allow, 2 deny (one-line reason on stderr), 64 usage or config error.
"""
from __future__ import annotations

import argparse
import sys

from . import core


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"guardrails: {message}\n")
        raise SystemExit(64)


def main(argv=None) -> int:
    ap = _Parser(prog="guardrails")
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="decide on one tool call")
    c.add_argument("--tool", required=True, choices=core.TOOLS)
    c.add_argument("--path", action="append", default=[])
    c.add_argument("--cmd")
    c.add_argument("--config")
    c.add_argument("--repo-root")
    c.add_argument("--cwd")
    args = ap.parse_args(argv)
    try:
        root = args.repo_root or core.find_repo_root(args.cwd or ".")
        cfg = core.load_config(args.config, root)
    except ValueError as exc:
        sys.stderr.write(f"guardrails: {exc}\n")
        return 64
    d = core.check(args.tool, args.path, args.cmd, cfg, root, args.cwd)
    if d.allowed:
        return 0
    sys.stderr.write(f"guardrails: denied: {d.reason}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
