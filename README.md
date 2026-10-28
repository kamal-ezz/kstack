# Personal skills

- **chimp** — implementation and functional verification
- **davinci** — frontend visual design
- **ramsay** — code review
- **boom** — Git and pull request operations
- **poshanka** — technical explanations

## Install

Requires Python 3 and a filesystem that supports symbolic links:

```sh
python3 install.py --dry-run
python3 install.py
```

The installer detects `codex` and `claude` on `PATH` and links each skill folder
into `~/.codex/skills` and `~/.claude/skills`, respectively. It respects
`CODEX_HOME` and `CLAUDE_CONFIG_DIR` when set. Missing clients are skipped; if
none of the requested clients are detected, it exits with an error.

Use `--target codex` or `--target claude` to select one client. The script locates
this collection relative to itself, so it can run from any directory.

Correct links are left alone. Existing same-name copies or different symlinks
are backed up under the client's `skill-backups/<timestamp>/` before replacement.
Unrelated skills, Codex's built-in skills, and Claude's synced folder are preserved.

## Updates

Installed skills point directly to this checkout, including supporting files,
metadata, and licenses. Edits and Git updates are immediately reflected through
the links; no copying, watcher, or background service is needed. An already-running
client may need a fresh session to reload skill instructions.

Keep this checkout in place. Rerun the installer after moving it or adding a new
skill. If you delete a source skill, remove its installed links as well. Editing
through an installed link also edits this checkout.
