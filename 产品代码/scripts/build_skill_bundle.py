#!/usr/bin/env python3
"""Assemble a portable AI PPT Studio Skill bundle."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _assert_safe_output(source_root: Path, output_root: Path) -> None:
    broad = {Path(output_root.anchor), Path.home().resolve()}
    if output_root in broad:
        raise ValueError(f"Bundle output root is too broad: {output_root}")
    if _is_within(output_root, source_root) or _is_within(source_root, output_root):
        raise ValueError(
            f"Bundle output root must not intersect source repository: {output_root}"
        )


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise ValueError(f"Bundle source cannot be a symlink: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Bundle source contains a symlink: {path}")


def build_bundle(source_root: Path, output_root: Path) -> Path:
    source = source_root.expanduser().resolve(strict=True)
    output = output_root.expanduser().resolve(strict=False)
    _assert_safe_output(source, output)
    skill_source = source / "skills" / "ai-ppt-studio"
    runtime_source = source / "src" / "ai_ppt_studio"
    if not skill_source.is_dir() or not runtime_source.is_dir():
        raise FileNotFoundError("Skill source or Python runtime package is missing")
    _reject_symlinks(skill_source)
    _reject_symlinks(runtime_source)

    bundle = output / "ai-ppt-studio"
    if bundle.exists():
        if bundle.is_symlink() or not bundle.is_dir():
            raise ValueError(f"Refusing to replace non-directory bundle: {bundle}")
        shutil.rmtree(bundle)
    output.mkdir(parents=True, exist_ok=True)
    ignored = shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".git"
    )
    shutil.copytree(skill_source, bundle, ignore=ignored)
    runtime_bundle = bundle / "runtime"
    runtime_bundle.mkdir(mode=0o755)
    shutil.copytree(
        runtime_source,
        runtime_bundle / "ai_ppt_studio",
        ignore=ignored,
    )
    (runtime_bundle / "VERSION").write_text("0.4.0\n", encoding="utf-8")
    _reject_symlinks(bundle)
    return bundle.resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source_root = Path(__file__).resolve().parents[1]
    print(build_bundle(source_root, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
