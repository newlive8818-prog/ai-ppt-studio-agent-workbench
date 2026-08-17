"""Byte-exact transaction persistence and rollback primitives."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from ai_ppt_studio.errors import ArtifactReferenceError, TransactionRollbackError
from ai_ppt_studio.json_io import atomic_write_json
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState


class PersistenceMixin:
    def _persist_transaction(
        self,
        *,
        committed: KernelState,
        event: dict[str, Any],
        event_path: Path,
        persistence_entries: list[tuple[str, dict[str, Any], ArtifactReference]],
        original_state_existed: bool,
        original_state_bytes: bytes,
    ) -> None:
        for kind, payload, candidate in persistence_entries:
            path = self.artifacts.path_for(candidate)
            if path.exists() and self.artifacts.resolve(candidate) != {
                "project_id": self.project_id,
                "kind": kind,
                "payload": payload,
            }:
                raise ArtifactReferenceError(
                    "Pre-existing artifact envelope differs from candidate: "
                    f"{candidate}"
                )
        created_object_paths: list[Path] = []
        try:
            for kind, payload, candidate in persistence_entries:
                path = self.artifacts.path_for(candidate)
                if not path.exists() and path not in created_object_paths:
                    created_object_paths.append(path)
                if self.artifacts.put(kind, payload) != candidate:
                    raise RuntimeError(
                        "Persisted artifact reference differs from candidate"
                    )
            atomic_write_json(event_path, event)
            atomic_write_json(self.state_path, committed.as_dict())
        except Exception as original_error:
            rollback_errors, state_restored, preserved = (
                self._rollback_failed_persistence(
                    original_state_existed=original_state_existed,
                    original_state_bytes=original_state_bytes,
                    event_path=event_path,
                    created_object_paths=tuple(created_object_paths),
                )
            )
            if rollback_errors:
                raise TransactionRollbackError(
                    rollback_errors=rollback_errors,
                    state_restored=state_restored,
                    preserved_exposed_transaction=preserved,
                ) from original_error
            raise

    def _rollback_failed_persistence(
        self,
        *,
        original_state_existed: bool,
        original_state_bytes: bytes,
        event_path: Path,
        created_object_paths: tuple[Path, ...],
    ) -> tuple[tuple[dict[str, str], ...], bool, bool]:
        """Restore authority first, then clean unexposed transaction files."""

        rollback_errors: list[dict[str, str]] = []
        state_restored = self._state_matches_snapshot(
            existed=original_state_existed,
            content=original_state_bytes,
        )
        if not state_restored:
            try:
                if original_state_existed:
                    self._restore_bytes(self.state_path, original_state_bytes)
                else:
                    self.state_path.unlink(missing_ok=True)
            except Exception as error:
                rollback_errors.append(
                    self._rollback_error("restore", self.state_path, error)
                )
            state_restored = self._state_matches_snapshot(
                existed=original_state_existed,
                content=original_state_bytes,
            )
            if not state_restored and not any(
                item["action"] == "restore" for item in rollback_errors
            ):
                rollback_errors.append(
                    {
                        "action": "restore",
                        "path": str(self.state_path),
                        "error_type": "StateVerificationError",
                        "message": "state does not match its pre-transaction snapshot",
                    }
                )

        preserved_exposed_transaction = not state_restored
        if state_restored:
            cleanup_targets = (
                ("remove-event", event_path),
                *(
                    ("remove-object", path)
                    for path in reversed(created_object_paths)
                ),
            )
            for action, path in cleanup_targets:
                try:
                    path.unlink(missing_ok=True)
                except Exception as error:
                    rollback_errors.append(
                        self._rollback_error(action, path, error)
                    )
                    continue
                if action == "remove-object":
                    try:
                        path.parent.rmdir()
                    except OSError:
                        pass
        return tuple(rollback_errors), state_restored, preserved_exposed_transaction

    def _state_matches_snapshot(self, *, existed: bool, content: bytes) -> bool:
        try:
            if self.state_path.exists() != existed:
                return False
            return not existed or self.state_path.read_bytes() == content
        except OSError:
            return False

    @staticmethod
    def _rollback_error(
        action: str, path: Path, error: Exception
    ) -> dict[str, str]:
        return {
            "action": action,
            "path": str(path),
            "error_type": type(error).__name__,
            "message": str(error),
        }

    @staticmethod
    def _restore_bytes(path: Path, content: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".rollback", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


__all__ = ["PersistenceMixin"]
