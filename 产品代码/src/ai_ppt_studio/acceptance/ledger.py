"""Build and validate the v1.6 acceptance requirement ledger."""

from __future__ import annotations

import re
import hashlib
from dataclasses import asdict, dataclass, replace
from pathlib import Path
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
    proof_refs: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    status: str = "unproven"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_evidence"] = list(self.required_evidence)
        payload["proof_refs"] = list(self.proof_refs)
        payload["missing_evidence"] = list(self.missing_evidence)
        return payload


@dataclass(frozen=True)
class EvidenceProof:
    """One immutable, hash-verified proof record."""

    proof_ref: str
    kind: str
    path: str
    sha256: str
    requirement_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["requirement_ids"] = list(self.requirement_ids)
        return payload


@dataclass(frozen=True)
class EvidenceIndex:
    """Repository-safe references to external or checked-in proof files."""

    schema_version: str
    proofs: tuple[EvidenceProof, ...]

    @classmethod
    def from_dict(
        cls, payload: dict[str, Any], *, base_path: Path | None = None
    ) -> "EvidenceIndex":
        if str(payload.get("schema_version")) != "1.0":
            raise ValueError("Unsupported evidence index schema")
        root = (base_path or Path.cwd()).resolve()
        proofs: list[EvidenceProof] = []
        seen: set[str] = set()
        for raw in payload.get("proofs", []):
            proof_ref = str(raw.get("proof_ref") or "").strip()
            kind = str(raw.get("kind") or "").strip()
            digest = str(raw.get("sha256") or "").strip()
            raw_path = str(raw.get("path") or "").strip()
            requirement_ids = tuple(
                str(value).strip()
                for value in raw.get("requirement_ids", [])
                if str(value).strip()
            )
            if (
                proof_ref != f"proof://{kind}/{digest}"
                or proof_ref in seen
                or not kind
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not raw_path
                or not requirement_ids
                or len(requirement_ids) != len(set(requirement_ids))
                or any(
                    not re.fullmatch(r"[A-Z]+-\d+(?:\.\d+)*-\d{2}", value)
                    for value in requirement_ids
                )
            ):
                raise ValueError(f"Invalid evidence proof: {proof_ref or '<missing>'}")
            path = Path(raw_path).expanduser()
            if path.is_symlink():
                raise ValueError(f"Evidence proof cannot be a symlink: {path}")
            resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
            try:
                actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except OSError as exc:
                raise ValueError(f"Evidence proof does not resolve: {resolved}") from exc
            if actual != digest:
                raise ValueError(f"Evidence proof hash mismatch: {proof_ref}")
            seen.add(proof_ref)
            proofs.append(
                EvidenceProof(
                    proof_ref=proof_ref,
                    kind=kind,
                    path=str(resolved),
                    sha256=digest,
                    requirement_ids=requirement_ids,
                )
            )
        return cls(schema_version="1.0", proofs=tuple(proofs))

    @classmethod
    def from_path(cls, path: Path) -> "EvidenceIndex":
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload, base_path=path.parent)


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

    def with_evidence(self, index: EvidenceIndex) -> "AcceptanceLedger":
        resolved: list[Requirement] = []
        for requirement in self.requirements:
            matching = [
                proof
                for proof in index.proofs
                if requirement.requirement_id in proof.requirement_ids
                or "*" in proof.requirement_ids
            ]
            covered = {
                proof.kind
                for proof in matching
                if proof.kind in requirement.required_evidence
            }
            missing = tuple(
                kind
                for kind in requirement.required_evidence
                if kind not in covered
            )
            resolved.append(
                replace(
                    requirement,
                    proof_refs=tuple(
                        proof.proof_ref
                        for proof in matching
                        if proof.kind in requirement.required_evidence
                    ),
                    missing_evidence=missing,
                    status="passed" if not missing else "unproven",
                )
            )
        return AcceptanceLedger(version=self.version, requirements=tuple(resolved))

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
                    proof_refs=tuple(item.get("proof_refs", [])),
                    missing_evidence=tuple(item.get("missing_evidence", [])),
                    status=str(item.get("status", "unproven")),
                )
                for item in payload["requirements"]
            ),
        )
