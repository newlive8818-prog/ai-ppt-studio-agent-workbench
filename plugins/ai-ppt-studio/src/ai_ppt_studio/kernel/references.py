"""Strict content-addressed artifact identities."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai_ppt_studio.errors import ArtifactReferenceError

REFERENCE = re.compile(r"^artifact://([a-z][a-z0-9-]*)/([0-9a-f]{64})$")


@dataclass(frozen=True, order=True)
class ArtifactReference:
    """A validated ``artifact://<kind>/<sha256>`` identity."""

    kind: str
    sha256: str

    def __post_init__(self) -> None:
        if not REFERENCE.fullmatch(str(self)):
            raise ArtifactReferenceError(f"Invalid artifact reference: {self}")

    def __str__(self) -> str:
        return f"artifact://{self.kind}/{self.sha256}"

    @classmethod
    def parse(cls, value: str) -> "ArtifactReference":
        match = REFERENCE.fullmatch(value)
        if not match:
            raise ArtifactReferenceError(f"Invalid artifact reference: {value}")
        return cls(kind=match.group(1), sha256=match.group(2))
