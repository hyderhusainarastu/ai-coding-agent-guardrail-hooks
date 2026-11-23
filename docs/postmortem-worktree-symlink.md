# Post-mortem: symlinks committed from a worktree replaced real directories

Anonymous and generalized. No dates, names, paths or counts.

## Setup

A project kept large, untracked directories (a virtual environment, datasets, model files) at the top of the main checkout. To work in a git worktree without copying them, someone linked those directories into the worktree with symlinks that pointed back at the main checkout.

## What happened

1. An agent working in the worktree ran `git add -A`. The symlinks were not ignored (the ignore rules named directories, and a symlink is a file to git), so they were staged and committed as symlink entries.
2. The branch was merged back into the main checkout by fast-forward.
3. In the main checkout, git replaced the real directories with the committed symlinks. Because the target of each link was a path that no longer made sense there, the real contents were no longer reachable, and part of the untracked data was lost. Tracked files could be restored from git; untracked data could not.

## Which part of this repo prevents what

| Step | Prevented by |
|---|---|
| Symlink to a protected directory is staged | `pre-commit` runs `symlink_guard.py --staged` and refuses it |
| It was committed anyway (hooks bypassed) and is pushed | `pre-push` runs `symlink_guard.py --range` over the pushed commits |
| A merge or pull turns a protected directory into a symlink | `post-merge` warns; it cannot undo anything |
| The agent runs `git add -A` | `AGENTS.md` rule and a `denied_cmd_patterns` entry you may add; not enforced by default |

## What a commit-time check cannot prevent

- Someone commits with `--no-verify`, or with hooks not installed in that clone. Repeat the symlink check in CI.
- A fast-forward or checkout that overwrites untracked files already happened by the time a post-merge hook runs.
- Data that is only in untracked directories has no backup unless you made one. Keep backups outside the repository.
- Symlinks created outside git (by a script or by hand) are invisible to these hooks until someone stages them.
