#!/usr/bin/env python3
"""Content-free completion notifier. Reads only the event name from the hook JSON on stdin.

Sinks (all optional, chosen by environment):
  GUARDRAILS_NTFY_URL      POST the message text to an ntfy topic URL
  GUARDRAILS_WEBHOOK_URL   POST {"event": "<name>"} as JSON
  GUARDRAILS_NOTIFY_DESKTOP=1   osascript (macOS) or notify-send (Linux)
Always exits 0.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request


def event_name(stdin_text: str) -> str:
    try:
        name = json.loads(stdin_text).get("hook_event_name", "")
    except Exception:
        name = ""
    name = re.sub(r"[^A-Za-z_]", "", str(name))[:40]
    return name or "unknown"


def _post(url, data, content_type):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": content_type}, method="POST")
    urllib.request.urlopen(req, timeout=3).close()


def notify(name: str, env=None) -> list:
    """Send to every configured sink; return the sink names attempted."""
    env = os.environ if env is None else env
    msg = f"agent event: {name}"
    tried = []
    for sink in ("ntfy", "webhook", "desktop"):
        try:
            if sink == "ntfy" and env.get("GUARDRAILS_NTFY_URL"):
                tried.append(sink)
                _post(env["GUARDRAILS_NTFY_URL"], msg.encode(), "text/plain")
            elif sink == "webhook" and env.get("GUARDRAILS_WEBHOOK_URL"):
                tried.append(sink)
                _post(env["GUARDRAILS_WEBHOOK_URL"], json.dumps({"event": name}).encode(), "application/json")
            elif sink == "desktop" and env.get("GUARDRAILS_NOTIFY_DESKTOP") == "1":
                if sys.platform == "darwin" and shutil.which("osascript"):
                    tried.append(sink)
                    subprocess.run(["osascript", "-e", f'display notification "{msg}"'], timeout=3, check=False)
                elif shutil.which("notify-send"):
                    tried.append(sink)
                    subprocess.run(["notify-send", msg], timeout=3, check=False)
        except Exception:
            pass  # fail open
    return tried


if __name__ == "__main__":
    notify(event_name(sys.stdin.read()))
    sys.exit(0)
