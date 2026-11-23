import json
import os

import pytest

from guardrails import core
from guardrails.cli import main
from conftest import run, ROOT


@pytest.fixture
def proj(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()
    return tmp_path


def chk(proj, tool, paths=(), cmd=None, cfg=None):
    return core.check(tool, paths, cmd, cfg or core.Config(), str(proj), str(proj))


@pytest.mark.parametrize("path,allowed", [
    (".env", False),
    ("sub/.env", False),
    (".env.local", False),
    (".env.example", True),
    ("sub/.env.example", True),
    ("src/app.py", True),
    ("environment.md", True),
])
def test_read_table(proj, path, allowed):
    assert chk(proj, "read", [path]).allowed is allowed


def test_edit_of_env_denied(proj):
    assert not chk(proj, "edit", [".env"]).allowed


@pytest.mark.parametrize("path,allowed", [
    ("src/app.py", True),
    ("new/dir/file.txt", True),
    ("../outside.txt", False),
    ("/etc/hosts", False),
])
def test_write_roots(proj, path, allowed):
    assert chk(proj, "write", [path]).allowed is allowed


def test_write_through_symlink_escape(proj, tmp_path_factory):
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    os.symlink(elsewhere, proj / "link")
    assert not chk(proj, "write", ["link/file.txt"]).allowed


@pytest.mark.parametrize("cmd,allowed", [
    ("ls -la", True),
    ("git commit --no-verify -m x", False),
    ("git commit -m 'fix no-verify docs'", True),
    ("git push --force origin main", False),
    ("git push -f origin master", False),
    ("git push origin +main", False),
    ("git push origin feature", True),
    ("git push --force origin feature", True),
    ("git push --force-with-lease origin main", False),
    ("rm -rf build", True),
    ("rm -rf /tmp/somewhere-else", False),
    ("rm -rf ../sibling", False),
    ("rm file.txt", True),
    ("cat .env", False),
    ("cat ./config/.env.production", False),
    ("cat .env.example", True),
])
def test_bash_table(proj, cmd, allowed):
    assert chk(proj, "bash", cmd=cmd).allowed is allowed


def test_other_allowed_and_unknown_tool_denied(proj):
    assert chk(proj, "other").allowed
    assert not chk(proj, "teleport").allowed


def test_config_overrides(proj):
    cfg = core.Config(write_roots=["${REPO_ROOT}/src"], denied_cmd_patterns=[r"curl\s"])
    assert chk(proj, "write", ["src/a.py"], cfg=cfg).allowed
    assert not chk(proj, "write", ["README.md"], cfg=cfg).allowed
    assert not chk(proj, "bash", cmd="curl http://x.invalid", cfg=cfg).allowed


def test_load_config_validation(tmp_path):
    p = tmp_path / "g.json"
    p.write_text(json.dumps({"bogus": 1}))
    with pytest.raises(ValueError):
        core.load_config(str(p))
    p.write_text("{not json")
    with pytest.raises(ValueError):
        core.load_config(str(p))
    p.write_text(json.dumps({"denied_cmd_patterns": ["("]}))
    with pytest.raises(ValueError):
        core.load_config(str(p))


def test_example_config_loads():
    cfg = core.load_config(os.path.join(ROOT, "examples", "guardrails.json"))
    assert cfg.protected_symlink_targets[0] == ".venv"


def test_cli_exit_codes(proj):
    base = ["check", "--repo-root", str(proj), "--cwd", str(proj)]
    assert main(base + ["--tool", "read", "--path", "src/a.py"]) == 0
    assert main(base + ["--tool", "read", "--path", ".env"]) == 2


def test_cli_subprocess_reason_on_stderr(proj):
    r = run(["python3", "-m", "guardrails", "check", "--tool", "bash", "--cmd", "git commit --no-verify",
             "--repo-root", str(proj), "--cwd", str(proj)], cwd=ROOT)
    assert r.returncode == 2
    assert r.stderr.count("\n") == 1 and "denied" in r.stderr


def test_cli_usage_error_is_64():
    r = run(["python3", "-m", "guardrails", "check", "--tool", "nope"], cwd=ROOT)
    assert r.returncode == 64
