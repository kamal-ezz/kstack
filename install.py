#!/usr/bin/env python3
"""Link this collection's skills into installed Codex and Claude Code clients."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile


CLIENTS = {
    "codex": ("CODEX_HOME", ".codex"),
    "claude": ("CLAUDE_CONFIG_DIR", ".claude"),
}


def install_skill(source, root, dry_run=False):
    destination = root / "skills" / source.name
    if destination.is_symlink() and destination.resolve() == source:
        print(f"  Already linked: {destination}")
        return
    if destination.resolve() == source:
        raise OSError(f"Refusing to replace the source directory: {destination}")
    exists = destination.exists() or destination.is_symlink()
    if dry_run:
        action = "Replace (with backup)" if exists else "Link"
        print(f"  {action}: {destination} -> {source}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    # Verify link creation works before moving an existing installation.
    with tempfile.TemporaryDirectory(prefix=".skill-install-", dir=root) as staging:
        staged = Path(staging) / source.name
        staged.symlink_to(source, target_is_directory=True)
        if exists:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = root / "skill-backups" / stamp / source.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
            raise
    print(f"  Linked: {destination} -> {source}")
    if backup is not None:
        print(f"    Previous installation: {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", choices=["all", *CLIENTS], default="all",
        help="Client to install into (default: all detected clients)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show planned links without writing files",
    )
    args = parser.parse_args()
    collection = Path(__file__).resolve().parent
    skills = sorted(
        path for path in collection.iterdir()
        if path.is_dir() and not path.is_symlink() and (path / "SKILL.md").is_file()
    )
    if not skills:
        parser.error(f"No skills found in {collection}")

    detected = 0
    for client, (variable, default) in CLIENTS.items():
        if args.target not in ("all", client):
            continue
        executable = shutil.which(client)
        if executable is None:
            print(f"Skipping {client}: executable not found on PATH.")
            continue
        detected += 1
        configured = os.environ.get(variable)
        root = Path(configured).expanduser().absolute() if configured else Path.home() / default
        print(f"{client}: {executable}")
        for skill in skills:
            install_skill(skill, root, args.dry_run)

    if not detected:
        print("No requested clients detected. Install them or add their executables to PATH.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, shutil.Error) as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        sys.exit(1)
