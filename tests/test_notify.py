import importlib.util
import json
import os

from conftest import ROOT


def load():
    spec = importlib.util.spec_from_file_location("notify", os.path.join(ROOT, "hooks", "notify.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_event_name_only_and_sanitized():
    n = load()
    payload = json.dumps({"hook_event_name": "Stop", "tool_input": {"command": "secret stuff"}})
    assert n.event_name(payload) == "Stop"
    assert n.event_name(json.dumps({"hook_event_name": "x;rm -rf"})) == "xrmrf"
    assert n.event_name("garbage") == "unknown"


def test_sinks_use_mocked_network(monkeypatch):
    n = load()
    calls = []

    class Resp:
        def close(self):
            pass

    def fake_urlopen(req, timeout=None):
        calls.append((req.full_url, req.data))
        return Resp()

    monkeypatch.setattr(n.urllib.request, "urlopen", fake_urlopen)
    tried = n.notify("Stop", {"GUARDRAILS_NTFY_URL": "https://ntfy.invalid/t",
                              "GUARDRAILS_WEBHOOK_URL": "https://hook.invalid/h"})
    assert tried == ["ntfy", "webhook"]
    assert calls[0] == ("https://ntfy.invalid/t", b"agent event: Stop")
    assert json.loads(calls[1][1]) == {"event": "Stop"}


def test_fail_open_on_network_error(monkeypatch):
    n = load()

    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(n.urllib.request, "urlopen", boom)
    assert n.notify("Stop", {"GUARDRAILS_NTFY_URL": "https://ntfy.invalid/t"}) == ["ntfy"]


def test_no_sinks_configured():
    assert load().notify("Stop", {}) == []
