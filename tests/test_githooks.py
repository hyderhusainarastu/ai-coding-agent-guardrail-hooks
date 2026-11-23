import os

import pytest

from conftest import run, git, ROOT

HOOKS = os.path.join(ROOT, "git-hooks")


def secret():
    return "s3" + "cr3t-" + "value-" + "0042"


def commit(repo, msg="c", env=None):
    return run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", msg],
               cwd=str(repo), env=env)


def test_env_value_caught_and_never_printed(hooked):
    (hooked / ".env").write_text(f"API_TOKEN={secret()}\nDEBUG=1\n")
    (hooked / "notes.md").write_text(f"line one\ntoken is {secret()}\n")
    git(str(hooked), "add", "notes.md")
    r = commit(hooked)
    assert r.returncode == 1
    assert "notes.md:2" in r.stderr and "API_TOKEN" in r.stderr
    assert secret() not in r.stdout + r.stderr


def test_clean_commit_passes_and_env_itself_not_required(hooked):
    (hooked / ".env").write_text(f"API_TOKEN={secret()}\n")
    (hooked / "a.txt").write_text("nothing sensitive\n")
    git(str(hooked), "add", "a.txt")
    assert commit(hooked).returncode == 0


def test_staging_the_env_file_is_refused(hooked):
    (hooked / ".env").write_text(f"API_TOKEN={secret()}\n")
    git(str(hooked), "add", "-f", ".env")
    r = commit(hooked)
    assert r.returncode == 1 and ".env:1" in r.stderr and secret() not in r.stderr


def test_short_values_ignored_and_example_files_skipped(hooked):
    (hooked / ".env").write_text("FLAG=1\n")
    (hooked / ".env.example").write_text(f"API_TOKEN={secret()}\n")
    (hooked / "a.txt").write_text("FLAG=1\n" + secret() + "\n")
    git(str(hooked), "add", "a.txt")
    assert commit(hooked).returncode == 0


def test_staged_symlink_to_protected_target_refused(hooked, tmp_path):
    real = tmp_path / "real_data"
    real.mkdir()
    os.symlink(str(real), hooked / "data")
    git(str(hooked), "add", "data")
    r = commit(hooked)
    assert r.returncode == 1 and "data" in r.stderr


def test_symlink_with_protected_component_in_target_refused(hooked):
    os.symlink("../main-checkout/.venv/lib", hooked / "libs")
    git(str(hooked), "add", "libs")
    assert commit(hooked).returncode == 1


def test_harmless_symlink_allowed(hooked):
    os.symlink("README.txt", hooked / "alias.txt")
    git(str(hooked), "add", "alias.txt")
    assert commit(hooked).returncode == 0


def test_symlink_in_linked_worktree(hooked, tmp_path):
    git(str(hooked), "config", "core.hooksPath", HOOKS)
    wt = tmp_path / "wt"
    git(str(hooked), "worktree", "add", "-q", "-b", "feature", str(wt))
    (hooked / "models").mkdir()
    os.symlink(str(hooked / "models"), wt / "models")
    git(str(wt), "add", "-A")
    r = commit(wt)
    assert r.returncode == 1 and "models" in r.stderr


def test_pre_push_refuses_bad_symlink_in_range(repo, tmp_path):
    bare = tmp_path / "remote.git"
    run(["git", "init", "-q", "--bare", str(bare)])
    git(str(repo), "remote", "add", "origin", str(bare))
    git(str(repo), "push", "-q", "origin", "main")
    os.symlink("../elsewhere/.venv", repo / "venv_link")
    git(str(repo), "add", "venv_link")
    git(str(repo), "commit", "-q", "-m", "bypassed", "--no-verify")
    git(str(repo), "config", "core.hooksPath", HOOKS)
    r = run(["git", "push", "origin", "main"], cwd=str(repo))
    assert r.returncode != 0 and "venv_link" in r.stderr


def test_pre_push_allows_clean_range(hooked, tmp_path):
    bare = tmp_path / "remote.git"
    run(["git", "init", "-q", "--bare", str(bare)])
    git(str(hooked), "remote", "add", "origin", str(bare))
    assert run(["git", "push", "origin", "main"], cwd=str(hooked)).returncode == 0


def test_post_merge_warns_but_exits_zero(hooked, tmp_path):
    os.symlink(str(tmp_path), hooked / "node_modules")
    r = run(["sh", os.path.join(HOOKS, "post-merge")], cwd=str(hooked))
    assert r.returncode == 0 and "node_modules" in r.stderr


def test_git_kill_switch_needs_both_variables(hooked, tmp_path):
    os.symlink(str(tmp_path), hooked / "data")
    git(str(hooked), "add", "data")
    assert commit(hooked, env={"GUARDRAILS_DISABLE": "1"}).returncode == 1
    assert not (hooked / ".guardrails").exists()
    r = commit(hooked, env={"GUARDRAILS_DISABLE": "1", "GUARDRAILS_DISABLE_GIT": "1"})
    assert r.returncode == 0
    line = (hooked / ".guardrails" / "audit.log").read_text().strip()
    assert line.endswith("pre-commit disabled")


def test_install_path_copy_uninstall_and_foreign(repo):
    inst = os.path.join(ROOT, "install-git-hooks.sh")
    assert run(["sh", inst], cwd=str(repo)).returncode == 0
    assert git(str(repo), "config", "--get", "core.hooksPath").strip().endswith("git-hooks")
    assert run(["sh", inst, "--uninstall"], cwd=str(repo)).returncode == 0
    assert run(["git", "config", "--get", "core.hooksPath"], cwd=str(repo)).returncode == 1

    hooks = repo / ".git" / "hooks"
    (hooks / "pre-commit").write_text("#!/bin/sh\necho foreign\n")
    r = run(["sh", inst, "--copy"], cwd=str(repo))
    assert r.returncode == 1 and "foreign" in r.stderr
    assert "echo foreign" in (hooks / "pre-commit").read_text()
    assert run(["sh", inst, "--copy", "--force"], cwd=str(repo)).returncode == 0
    # copied hooks work on their own
    os.symlink("x/.venv", repo / "bad")
    git(str(repo), "add", "bad")
    assert commit(repo).returncode == 1
    assert run(["sh", inst, "--uninstall"], cwd=str(repo)).returncode == 0
    assert not (hooks / "pre-commit").exists()
