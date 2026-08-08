"""Build and validate the v1.6 acceptance requirement ledger."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

MAJOR_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
HEADING = re.compile(r"^###\s+(\d+(?:\.\d+)*)\s+(.+?)\s*$")
ITEM = re.compile(r"^(\d+)\.\s+(.+?)\s*$")


@dataclass(frozen=True)
class Requirement:
    """One numbered baseline requirement and its minimum proof contract."""

    requirement_id: str
    source_section: str
    text: str
    required_evidence: tuple[str, ...]
    status: str = "unproven"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = list(self.required_evidence)
        return payload


def _proof_kinds(source_prefix: str, section: str) -> tuple[str, ...]:
    proofs = ["automated-test", "runtime-evidence"]
    if source_prefix == "PRD" and section == "17.3":
        proofs.extend(["target-evidence", "real-project"])
    elif source_prefix == "SDD" and section == "21.3":
        proofs.append("real-project")
    elif source_prefix == "UI" and section.startswith("23"):
        proofs.append("viewport-evidence")
    return tuple(proofs)


def extract_numbered_requirements(
    markdown: str, *, source_prefix: str, section_prefix: str
) -> tuple[Requirement, ...]:
    """Extract numbered list items under the requested baseline section."""

    current_section = ""
    entries: list[Requirement] = []
    for line in markdown.splitlines():
        major = MAJOR_HEADING.match(line)
        if major:
            current_section = major.group(1)
            continue
        heading = HEADING.match(line)
        if heading:
            current_section = heading.group(1)
            continue
        if not current_section.startswith(f"{section_prefix}."):
            continue
        item = ITEM.match(line)
        if not item:
            continue
        number, text = item.groups()
        entries.append(
            Requirement(
                requirement_id=(
                    f"{source_prefix}-{current_section}-{int(number):02d}"
                ),
                source_section=current_section,
                text=text,
                required_evidence=_proof_kinds(source_prefix, current_section),
            )
        )
    return tuple(entries)


@dataclass(frozen=True)
class AcceptanceLedger:
    """Versioned inventory of formal requirements and required evidence."""

    version: str
    requirements: tuple[Requirement, ...]

    def __post_init__(self) -> None:
        ids = self.ids
        if len(ids) != len(set(ids)):
            raise ValueError("Acceptance requirement IDs must be unique")
        if any(not item.required_evidence for item in self.requirements):
            raise ValueError("Every requirement needs an evidence contract")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(item.requirement_id for item in self.requirements)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "requirements": [item.as_dict() for item in self.requirements],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AcceptanceLedger":
        return cls(
            version=str(payload["version"]),
            requirements=tuple(
                Requirement(
                    requirement_id=str(item["requirement_id"]),
                    source_section=str(item["source_section"]),
                    text=str(item["text"]),
                    required_evidence=tuple(item["required_evidence"]),
                    status=str(item.get("status", "unproven")),
                )
                for item in payload["requirements"]
            ),
        )
