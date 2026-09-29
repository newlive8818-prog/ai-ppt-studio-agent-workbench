"""Single write gate and read-only source validation."""

from __future__ import annotations

import os
from pathlib import Path

from .config import RuntimeConfig
from .errors import MaterialImportError, ProtectedPathError


def is_within(child: Path, parent: Path) -> bool:
    """Return whether *child* is equal to or nested below *parent*."""

    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


class PathPolicy:
    """Validate every runtime write and every external source read."""

    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config

    def assert_write_allowed(self, target: Path) -> Path:
        expanded = target.expanduser()
        lexical = expanded if expanded.is_absolute() else Path.cwd() / expanded
        lexical = Path(os.path.abspath(lexical))
        self._reject_symlink_components(lexical)
        candidate = lexical.resolve(strict=False)
        if not is_within(candidate, self.config.runtime_root):
            raise ProtectedPathError(
                f"Write target is outside managed runtime root: {candidate}"
            )
        for protected in self.config.protected_roots:
            if is_within(candidate, protected) or is_within(protected, candidate):
                raise ProtectedPathError(
                    f"Write target intersects protected root: {protected}"
                )
        return candidate

    def assert_source_readable(self, source: Path) -> Path:
        expanded = source.expanduser()
        lexical = expanded if expanded.is_absolute() else Path.cwd() / expanded
        lexical = Path(os.path.abspath(lexical))
        if lexical.is_symlink():
            raise MaterialImportError(f"Source cannot be a symlink: {lexical}")
        candidate = lexical.resolve(strict=True)
        if not (candidate.is_file() or candidate.is_dir()):
            raise MaterialImportError(
                f"Source must be a regular file or directory: {candidate}"
            )
        if not os.access(candidate, os.R_OK):
            raise MaterialImportError(f"Source is not readable: {candidate}")
        return candidate

    def _reject_symlink_components(self, target: Path) -> None:
        current = Path(target.anchor)
        for part in target.parts[1:]:
            current = current / part
            parent = current.parent.resolve(strict=False)
            if current.is_symlink() and is_within(
                parent, self.config.runtime_root
            ):
                raise ProtectedPathError(
                    f"Write target traverses symlink: {current}"
                )
