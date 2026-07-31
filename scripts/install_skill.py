#!/usr/bin/env python3
"""Install a validated AI PPT Studio bundle at one exact Skill target."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise ValueError(f"Skill bundle cannot be a symlink: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Skill bundle contains a symlink: {path}")


def _validate_target(target: Path) -> None:
    if target.name != "ai-ppt-studio":
        raise ValueError(f"Install target must end in ai-ppt-studio: {target}")
    if target in {Path(target.anchor), Path.home().resolve()}:
        raise ValueError(f"Install target is too broad: {target}")
    if target.is_symlink():
        raise ValueError(f"Install target cannot be a symlink: {target}")


def _validator_path() -> Path:
    validator = (
        Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "skill-creator"
        / "scripts"
        / "quick_validate.py"
    )
    if not validator.is_file():
        raise FileNotFoundError(f"Official Skill validator is missing: {validator}")
    return validator


def install_bundle(bundle: Path, target: Path) -> Path:
    source = bundle.expanduser().resolve(strict=True)
    destination = target.expanduser().resolve(strict=False)
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise ValueError(f"Not an AI PPT Studio Skill bundle: {source}")
    _reject_symlinks(source)
    _validate_target(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = destination.parent / f".ai-ppt-studio.stage-{token}"
    backup = destination.parent / f".ai-ppt-studio.backup-{token}"
    replaced = False
    try:
        shutil.copytree(source, staging)
        _reject_symlinks(staging)
        validated = subprocess.run(
            [sys.executable, str(_validator_path()), str(staging)],
            text=True,
            capture_output=True,
            check=False,
        )
        if validated.returncode != 0:
            raise ValueError(
                f"Skill bundle validation failed: {validated.stdout}{validated.stderr}"
            )
        if destination.exists():
            if not destination.is_dir():
                raise ValueError(
                    f"Refusing to replace non-directory Skill target: {destination}"
                )
            os.replace(destination, backup)
            replaced = True
        os.replace(staging, destination)
        if backup.exists():
            shutil.rmtree(backup)
        return destination
    except Exception:
        if replaced and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists() and destination.exists():
            shutil.rmtree(backup)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    args = parser.parse_args()
    print(install_bundle(args.bundle, args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
