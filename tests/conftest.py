import os
import subprocess
import sys

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def run(cmd, cwd=None, env=None, inp=None):
    e = dict(os.environ)
    e.pop("GUARDRAILS_DISABLE", None)
    e.pop("GUARDRAILS_DISABLE_GIT", None)
    e.update(env or {})
    return subprocess.run(cmd, cwd=cwd, env=e, input=inp, capture_output=True, text=True)


def git(cwd, *args):
    r = run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=cwd)
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    git(str(d), "init", "-q", "-b", "main")
    (d / "README.txt").write_text("hello\n")
    git(str(d), "add", "README.txt")
    git(str(d), "commit", "-q", "-m", "init")
    return d


@pytest.fixture
def hooked(repo):
    git(str(repo), "config", "core.hooksPath", os.path.join(ROOT, "git-hooks"))
    return repo
