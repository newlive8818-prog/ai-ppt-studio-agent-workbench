"""Append-only project event persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from .json_io import append_jsonl
from .paths import PathPolicy


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class EventStore:
    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy

    def append(self, event_type: str, payload: dict[str, object]) -> str:
        event_name = event_type.strip()
        if not event_name:
            raise ValueError("Event type cannot be empty")
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "event_type": event_name,
            "occurred_at": utc_now(),
            "payload": payload,
        }
        path = self.policy.assert_write_allowed(
            self.project_root / "events" / "events.jsonl"
        )
        append_jsonl(path, event)
        return event_id
