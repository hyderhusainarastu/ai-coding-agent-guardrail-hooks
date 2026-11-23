import json
import os

import pytest

from conftest import run, ROOT

ADAPTER = os.path.join(ROOT, "adapters", "claude_code.py")


def call(payload, cwd, env=None):
    payload = dict(payload, cwd=str(cwd), hook_event_name="PreToolUse")
    return run(["python3", "-I", ADAPTER], cwd=str(cwd), env=env, inp=json.dumps(payload))


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.mark.parametrize("payload,code", [
    ({"tool_name": "Read", "tool_input": {"file_path": ".env"}}, 2),
    ({"tool_name": "Read", "tool_input": {"file_path": "a.py"}}, 0),
    ({"tool_name": "Write", "tool_input": {"file_path": "/etc/hosts", "content": "x"}}, 2),
    ({"tool_name": "Write", "tool_input": {"file_path": "ok.txt", "content": "x"}}, 0),
    ({"tool_name": "Edit", "tool_input": {"file_path": "../x.py"}}, 2),
    ({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/etc/n.ipynb"}}, 2),
    ({"tool_name": "Bash", "tool_input": {"command": "git commit --no-verify -m x"}}, 2),
    ({"tool_name": "Bash", "tool_input": {"command": "echo hi"}}, 0),
    ({"tool_name": "Grep", "tool_input": {"pattern": "x", "path": ".env"}}, 2),
    ({"tool_name": "WebSearch", "tool_input": {"query": "x"}}, 0),
])
def test_exit_codes(proj, payload, code):
    r = call(payload, proj)
    assert r.returncode == code, r.stderr
    if code == 2:
        assert "denied" in r.stderr


def test_fail_open_on_garbage_stdin(proj):
    r = run(["python3", "-I", ADAPTER], cwd=str(proj), inp="not json")
    assert r.returncode == 0


def test_fail_open_on_bad_config(proj):
    (proj / "guardrails.json").write_text("{broken")
    r = call({"tool_name": "Read", "tool_input": {"file_path": ".env"}}, proj)
    assert r.returncode == 0


def test_project_config_is_used(proj):
    (proj / "guardrails.json").write_text(json.dumps({"denied_cmd_patterns": ["curl"]}))
    r = call({"tool_name": "Bash", "tool_input": {"command": "curl x.invalid"}}, proj)
    assert r.returncode == 2


def test_kill_switch_writes_content_free_audit_line(proj):
    r = call({"tool_name": "Read", "tool_input": {"file_path": ".env"}}, proj, env={"GUARDRAILS_DISABLE": "1"})
    assert r.returncode == 0
    lines = (proj / ".guardrails" / "audit.log").read_text().splitlines()
    assert len(lines) == 1
    stamp, hook, word = lines[0].split(" ")
    assert stamp.endswith("Z") and hook == "claude_code" and word == "disabled"
    assert ".env" not in lines[0]


def test_example_settings_shape():
    with open(os.path.join(ROOT, "examples", "claude-settings.json")) as f:
        s = json.load(f)
    h = s["hooks"]["PreToolUse"][0]["hooks"][0]
    assert h["type"] == "command" and h["timeout"] <= 10 and "python3 -I" in h["command"]
