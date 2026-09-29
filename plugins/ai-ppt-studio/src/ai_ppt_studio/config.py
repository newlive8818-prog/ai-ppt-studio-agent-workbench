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

    @classmethod
    def from_workspace_file(cls, path: Path) -> "RuntimeConfig":
        """Load either a runtime config or the existing managed workspace profile."""

        profile_path = path.expanduser().resolve(strict=True)
        try:
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(
                f"Cannot load managed workspace profile: {profile_path}"
            ) from exc
        runtime_value = payload.get("runtime_root") or payload.get("workspace_root")
        source_value = payload.get("source_repo_root") or payload.get(
            "source_repository"
        )
        install_value = payload.get("install_root") or payload.get(
            "future_install_root"
        )
        protected_values = payload.get("protected_roots")
        if not runtime_value or not source_value or not install_value:
            raise ConfigurationError(
                "Workspace profile requires workspace_root, source_repository, and future_install_root"
            )
        if not isinstance(protected_values, list) or not protected_values:
            raise ConfigurationError(
                "Workspace profile requires at least one protected root"
            )
        source = _canonical(Path(str(source_value)))
        install = _canonical(Path(str(install_value)))
        protected = tuple(_canonical(Path(str(item))) for item in protected_values)
        explicit_upstream = payload.get("upstream_root")
        if explicit_upstream:
            upstream = _canonical(Path(str(explicit_upstream)))
        else:
            candidates = [root for root in protected if root not in {source, install}]
            if not candidates:
                raise ConfigurationError(
                    "Workspace profile cannot identify an upstream protected root"
                )
            upstream = candidates[0]
        primary = {source, install, upstream}
        extras = tuple(root for root in protected if root not in primary)
        return cls.create(
            runtime_root=Path(str(runtime_value)),
            source_repo_root=source,
            install_root=install,
            upstream_root=upstream,
            extra_protected_roots=extras,
        )
