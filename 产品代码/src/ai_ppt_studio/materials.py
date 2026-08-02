"""Read-only registration and verified import of user-provided materials."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from .errors import MaterialImportError
from .json_io import atomic_write_json
from .models import ImportMode, MaterialSource, SourceKind
from .paths import PathPolicy
from .project_store import normalize_slug

HASH_CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


class MaterialIntake:
    """Add sources without changing originals or performing web requests."""

    def __init__(self, policy: PathPolicy) -> None:
        self.policy = policy

    def add_local(
        self, project_root: Path, source: Path, mode: ImportMode
    ) -> tuple[MaterialSource, ...]:
        project = self.policy.assert_write_allowed(project_root)
        original = self.policy.assert_source_readable(source)
        if original.is_file():
            return (self._add_file(project, original, mode, SourceKind.FILE),)

        candidates: list[Path] = []
        for candidate in original.rglob("*"):
            if candidate.is_symlink():
                raise MaterialImportError(
                    f"Source directory contains a symlink: {candidate}"
                )
            if candidate.is_file():
                candidates.append(candidate)
        candidates.sort(key=lambda path: path.relative_to(original).as_posix())
        return tuple(
            self._add_file(project, candidate, mode, SourceKind.DIRECTORY)
            for candidate in candidates
        )

    def add_url(self, project_root: Path, url: str) -> MaterialSource:
        project = self.policy.assert_write_allowed(project_root)
        exact = url.strip()
        parsed = urlsplit(exact)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise MaterialImportError(f"Only complete HTTP(S) URLs are accepted: {url}")
        record = MaterialSource(
            source_id=str(uuid.uuid4()),
            kind=SourceKind.URL,
            mode=ImportMode.REFERENCE,
            original_ref=exact,
            managed_ref=None,
            sha256=None,
            size_bytes=None,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._write_record(project, record)
        return record

    def add_text(self, project_root: Path, text: str, label: str) -> MaterialSource:
        project = self.policy.assert_write_allowed(project_root)
        body = text.strip()
        if not body:
            raise MaterialImportError("Text material cannot be empty")
        source_id = str(uuid.uuid4())
        safe_label = normalize_slug(label)[:48]
        destination = self.policy.assert_write_allowed(
            project
            / "managed-assets"
            / "text"
            / f"{source_id}-{safe_label}.txt"
        )
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination.write_text(body + "\n", encoding="utf-8")
        record = MaterialSource(
            source_id=source_id,
            kind=SourceKind.TEXT,
            mode=ImportMode.COPY,
            original_ref=f"inline:{label.strip() or 'text'}",
            managed_ref=str(destination),
            sha256=file_sha256(destination),
            size_bytes=destination.stat().st_size,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._write_record(project, record)
        return record

    def add_bytes(
        self,
        project_root: Path,
        filename: str,
        data: bytes,
        mime_type: str,
    ) -> MaterialSource:
        """Copy one host-uploaded file into the managed project.

        The host supplies bytes explicitly; this method never follows a path from
        the browser and never performs a network request.
        """

        project = self.policy.assert_write_allowed(project_root)
        if not isinstance(data, bytes) or not data:
            raise MaterialImportError("Uploaded material cannot be empty")
        if len(data) > MAX_UPLOAD_BYTES:
            raise MaterialImportError(
                f"Uploaded material exceeds {MAX_UPLOAD_BYTES} bytes"
            )
        exact_name = Path(filename.strip()).name
        suffix = Path(exact_name).suffix.lower()[:16]
        safe_stem = normalize_slug(Path(exact_name).stem)[:64]
        safe_name = f"{safe_stem}{suffix}" if suffix else safe_stem
        source_id = str(uuid.uuid4())
        destination = self.policy.assert_write_allowed(
            project / "managed-assets" / "uploads" / source_id / safe_name
        )
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        destination.write_bytes(data)
        digest = file_sha256(destination)
        record = MaterialSource(
            source_id=source_id,
            kind=SourceKind.FILE,
            mode=ImportMode.COPY,
            original_ref=f"upload:{exact_name or safe_name};mime={mime_type.strip() or 'application/octet-stream'}",
            managed_ref=str(destination),
            sha256=digest,
            size_bytes=len(data),
            created_at=datetime.now(UTC).isoformat(),
        )
        self._write_record(project, record)
        return record

    def _add_file(
        self,
        project: Path,
        original: Path,
        mode: ImportMode,
        source_kind: SourceKind,
    ) -> MaterialSource:
        source_id = str(uuid.uuid4())
        original_hash = file_sha256(original)
        managed_ref: str | None = None
        if mode is ImportMode.COPY:
            destination = self.policy.assert_write_allowed(
                project
                / "managed-assets"
                / "local"
                / source_id
                / original.name
            )
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(original, destination)
            managed_hash = file_sha256(destination)
            if managed_hash != original_hash:
                destination.unlink(missing_ok=True)
                raise MaterialImportError(
                    f"Managed copy hash mismatch for source: {original}"
                )
            managed_ref = str(destination)
        record = MaterialSource(
            source_id=source_id,
            kind=source_kind,
            mode=mode,
            original_ref=str(original),
            managed_ref=managed_ref,
            sha256=original_hash,
            size_bytes=original.stat().st_size,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._write_record(project, record)
        return record

    def _write_record(self, project: Path, record: MaterialSource) -> None:
        destination = self.policy.assert_write_allowed(
            project / "sources" / f"{record.source_id}.json"
        )
        atomic_write_json(destination, record.as_dict())


__all__ = [
    "ImportMode",
    "MAX_UPLOAD_BYTES",
    "MaterialIntake",
    "MaterialSource",
    "SourceKind",
]
