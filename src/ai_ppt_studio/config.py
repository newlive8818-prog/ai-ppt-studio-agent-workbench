"""Runtime configuration for the isolated AI PPT workspace."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigurationError


def _canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


@dataclass(frozen=True)
class RuntimeConfig:
    """Canonical locations and protected roots for one local installation."""

    schema_version: str
    runtime_root: Path
    source_repo_root: Path
    install_root: Path
    upstream_root: Path
    protected_roots: tuple[Path, ...]

    @classmethod
    def create(
        cls,
        runtime_root: Path,
        source_repo_root: Path,
        install_root: Path,
        upstream_root: Path,
        extra_protected_roots: tuple[Path, ...] = (),
    ) -> "RuntimeConfig":
        runtime = _canonical(runtime_root)
        source_repo = _canonical(source_repo_root)
        install = _canonical(install_root)
        upstream = _canonical(upstream_root)
        roots = tuple(
            dict.fromkeys(
                _canonical(path)
                for path in (
                    source_repo,
                    install,
                    upstream,
                    *extra_protected_roots,
                )
            )
        )
        cls._validate(runtime, roots)
        return cls(
            schema_version="1.0",
            runtime_root=runtime,
            source_repo_root=source_repo,
            install_root=install,
            upstream_root=upstream,
            protected_roots=roots,
        )

    @staticmethod
    def _validate(runtime_root: Path, protected_roots: tuple[Path, ...]) -> None:
        forbidden_broad = {Path(runtime_root.anchor), Path.home().resolve()}
        if runtime_root in forbidden_broad:
            raise ConfigurationError(f"Runtime root is too broad: {runtime_root}")
        if runtime_root.exists() and runtime_root.is_symlink():
            raise ConfigurationError(f"Runtime root cannot be a symlink: {runtime_root}")
        for protected in protected_roots:
            if _is_within(runtime_root, protected):
                raise ConfigurationError(
                    f"Runtime root intersects protected root: {protected}"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "runtime_root": str(self.runtime_root),
            "source_repo_root": str(self.source_repo_root),
            "install_root": str(self.install_root),
            "upstream_root": str(self.upstream_root),
            "protected_roots": [str(path) for path in self.protected_roots],
        }

    def save(self, path: Path) -> None:
        """Atomically save configuration beneath the managed runtime root."""

        target = _canonical(path)
        if not _is_within(target, self.runtime_root):
            raise ConfigurationError(
                f"Configuration must be saved under runtime root: {target}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(self.as_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
            target.chmod(0o600)
        finally:
            temporary = Path(temporary_name)
            if temporary.exists():
                temporary.unlink()

    @classmethod
    def load(cls, path: Path) -> "RuntimeConfig":
        try:
            payload = json.loads(path.expanduser().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Cannot load runtime configuration: {path}") from exc
        if payload.get("schema_version") != "1.0":
            raise ConfigurationError(
                f"Unsupported runtime configuration schema: {payload.get('schema_version')}"
            )
        required = (
            "runtime_root",
            "source_repo_root",
            "install_root",
            "upstream_root",
            "protected_roots",
        )
        if any(key not in payload for key in required):
            raise ConfigurationError("Runtime configuration is missing required keys")
        primary = {
            _canonical(Path(payload["source_repo_root"])),
            _canonical(Path(payload["install_root"])),
            _canonical(Path(payload["upstream_root"])),
        }
        extra = tuple(
            Path(item)
            for item in payload["protected_roots"]
            if _canonical(Path(item)) not in primary
        )
        return cls.create(
            runtime_root=Path(payload["runtime_root"]),
            source_repo_root=Path(payload["source_repo_root"]),
            install_root=Path(payload["install_root"]),
            upstream_root=Path(payload["upstream_root"]),
            extra_protected_roots=extra,
        )
