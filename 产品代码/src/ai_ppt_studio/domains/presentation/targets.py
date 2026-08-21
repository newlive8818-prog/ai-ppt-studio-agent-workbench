"""Desktop target-render evidence and policy-parameterized matrices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ai_ppt_studio.errors import GateBlockedError
from ai_ppt_studio.domains.presentation.release_policy import SUPPORTED_TARGET_IDS
from ai_ppt_studio.kernel.references import ArtifactReference

# Compatibility alias for callers not yet migrated to project-bound policy.
REQUIRED_TARGET_IDS = SUPPORTED_TARGET_IDS
TARGET_PROFILES = {
    "macos-powerpoint": ("macOS", "Microsoft PowerPoint"),
    "macos-wps": ("macOS", "WPS Office"),
    "windows-powerpoint": ("Windows 11", "Microsoft PowerPoint"),
    "windows-wps": ("Windows 11", "WPS Office"),
}
SLIDE_RESULT_FIELDS = (
    "semantic_result",
    "aesthetic_result",
    "engineering_result",
    "target_render_result",
)


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _artifact_ref(payload: dict[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    ArtifactReference.parse(value)
    return value


def _artifact_refs(payload: dict[str, Any], field: str) -> tuple[str, ...]:
    values = payload.get(field)
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value for value in values)
    ):
        raise ValueError(f"{field} must contain artifact references")
    for value in values:
        ArtifactReference.parse(value)
    return tuple(values)


@dataclass(frozen=True)
class TargetRenderEvidence:
    """Immutable identity and result for one supported desktop target."""

    target_id: str
    evidence_identity: str
    operating_system: str
    operating_system_version: str
    application: str
    application_version: str
    application_check_result: str
    font_check_result: str
    font_inventory_ref: str
    font_substitution_plan_ref: str
    reviewer_attestation_ref: str
    source_pptx_ref: str
    pptx_sha256: str
    sha256_before: str
    sha256_after: str
    export_refs: tuple[str, ...]
    page_image_refs: tuple[str, ...]
    slide_checks: tuple[dict[str, Any], ...]
    executor: str
    exported_at: str
    tool_version: str
    overall_result: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if self.target_id not in SUPPORTED_TARGET_IDS:
            raise ValueError(f"Unknown target profile: {self.target_id}")
        if self.evidence_identity != "formal-target-render":
            raise ValueError("Preflight-only output cannot be target-render evidence")
        expected_os, expected_application = TARGET_PROFILES[self.target_id]
        if (
            self.operating_system != expected_os
            or self.application != expected_application
        ):
            raise ValueError(
                f"Target {self.target_id} requires {expected_os} / {expected_application}"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.pptx_sha256):
            raise ValueError(
                "PPTX SHA-256 must be 64 lowercase hexadecimal characters"
            )
        if not (
            self.sha256_before
            == self.sha256_after
            == self.pptx_sha256
        ):
            raise ValueError(
                "Target evidence before/after hashes must match the source PPTX"
            )
        if not self.slide_checks:
            raise ValueError("Target evidence requires per-slide four-gate checks")
        if self.application_check_result not in {"passed", "failed"}:
            raise ValueError("application_check_result must be passed or failed")
        if self.font_check_result not in {"passed", "failed"}:
            raise ValueError("font_check_result must be passed or failed")
        failed = (
            self.application_check_result == "failed"
            or self.font_check_result == "failed"
        )
        seen: set[str] = set()
        for check in self.slide_checks:
            slide_id = check.get("slide_id")
            if not isinstance(slide_id, str) or not slide_id or slide_id in seen:
                raise ValueError("Target evidence slide IDs must be non-empty and unique")
            seen.add(slide_id)
            evidence_refs = check.get("evidence_refs")
            if (
                not isinstance(evidence_refs, list)
                or not evidence_refs
                or any(not isinstance(ref, str) or not ref for ref in evidence_refs)
            ):
                raise ValueError("Every target slide check requires evidence")
            for ref in evidence_refs:
                ArtifactReference.parse(ref)
            results = [check.get(field) for field in SLIDE_RESULT_FIELDS]
            if any(result not in {"passed", "failed"} for result in results):
                raise ValueError("Target slide checks must use passed or failed")
            if "failed" in results:
                failed = True
                if not str(check.get("failure_reason") or "").strip() or not str(
                    check.get("repair_instruction") or ""
                ).strip():
                    raise ValueError(
                        "Failed target slide checks require reason and repair instruction"
                    )
        computed = "failed" if failed else "passed"
        if self.overall_result != computed:
            raise ValueError(
                f"Target evidence overall_result must be {computed}"
            )
        try:
            exported_at = datetime.fromisoformat(self.exported_at)
        except ValueError as error:
            raise ValueError("exported_at must be an ISO-8601 timestamp") from error
        if exported_at.tzinfo is None:
            raise ValueError("exported_at must include a timezone")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TargetRenderEvidence":
        if not isinstance(payload, dict):
            raise ValueError("TargetRenderEvidence must be an object")
        target_id = _required_text(payload, "target_id")
        if target_id not in SUPPORTED_TARGET_IDS:
            raise ValueError(f"Unknown target profile: {target_id}")
        export_refs = _artifact_refs(payload, "export_refs")
        page_image_refs = _artifact_refs(payload, "page_image_refs")
        slide_checks = payload.get("slide_checks")
        if (
            not isinstance(slide_checks, list)
            or not slide_checks
            or any(not isinstance(check, dict) for check in slide_checks)
        ):
            raise ValueError("slide_checks must be a non-empty object array")
        pptx_sha256 = _required_text(payload, "pptx_sha256")
        return cls(
            target_id=target_id,
            evidence_identity=_required_text(payload, "evidence_identity"),
            operating_system=_required_text(payload, "operating_system"),
            operating_system_version=_required_text(
                payload, "operating_system_version"
            ),
            application=_required_text(payload, "application"),
            application_version=_required_text(payload, "application_version"),
            application_check_result=_required_text(
                payload, "application_check_result"
            ),
            font_check_result=_required_text(payload, "font_check_result"),
            font_inventory_ref=_artifact_ref(payload, "font_inventory_ref"),
            font_substitution_plan_ref=_artifact_ref(
                payload, "font_substitution_plan_ref"
            ),
            reviewer_attestation_ref=_artifact_ref(
                payload, "reviewer_attestation_ref"
            ),
            source_pptx_ref=_artifact_ref(payload, "source_pptx_ref"),
            pptx_sha256=pptx_sha256,
            sha256_before=_required_text(payload, "sha256_before"),
            sha256_after=_required_text(payload, "sha256_after"),
            export_refs=export_refs,
            page_image_refs=page_image_refs,
            slide_checks=tuple(dict(check) for check in slide_checks),
            executor=_required_text(payload, "executor"),
            exported_at=_required_text(payload, "exported_at"),
            tool_version=_required_text(payload, "tool_version"),
            overall_result=_required_text(payload, "overall_result"),
            evidence_ref=_artifact_ref(payload, "evidence_ref"),
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "evidence_identity": self.evidence_identity,
            "operating_system": self.operating_system,
            "operating_system_version": self.operating_system_version,
            "application": self.application,
            "application_version": self.application_version,
            "application_check_result": self.application_check_result,
            "font_check_result": self.font_check_result,
            "font_inventory_ref": self.font_inventory_ref,
            "font_substitution_plan_ref": self.font_substitution_plan_ref,
            "reviewer_attestation_ref": self.reviewer_attestation_ref,
            "source_pptx_ref": self.source_pptx_ref,
            "pptx_sha256": self.pptx_sha256,
            "sha256_before": self.sha256_before,
            "sha256_after": self.sha256_after,
            "export_refs": list(self.export_refs),
            "page_image_refs": list(self.page_image_refs),
            "slide_checks": [dict(check) for check in self.slide_checks],
            "executor": self.executor,
            "exported_at": self.exported_at,
            "tool_version": self.tool_version,
            "overall_result": self.overall_result,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(frozen=True)
class TargetEvidenceMatrix:
    """A complete policy-required result for one exact PPTX binary."""

    pptx_sha256: str
    target_ids: tuple[str, ...]


def validate_required_targets(
    evidence: list[TargetRenderEvidence],
    required_target_ids: tuple[str, ...] | None = None,
) -> TargetEvidenceMatrix:
    """Reject invalid, incomplete, failed, extra, or mixed-hash evidence."""

    required = (
        SUPPORTED_TARGET_IDS
        if required_target_ids is None
        else tuple(required_target_ids)
    )
    blockers: list[str] = []
    if not required:
        blockers.append("required-targets-empty")
    if len(required) != len(set(required)):
        blockers.append("required-targets-duplicate")
    if set(required).difference(SUPPORTED_TARGET_IDS):
        blockers.append("required-targets-unsupported")
    counts = {target: 0 for target in required}
    for item in evidence:
        if item.target_id not in counts:
            blockers.append(f"extra-target:{item.target_id}")
            continue
        counts[item.target_id] += 1
    blockers.extend(target for target, count in counts.items() if count != 1)
    if any(item.overall_result != "passed" for item in evidence):
        blockers.append("failed-target")
    hashes = {item.pptx_sha256 for item in evidence}
    if len(hashes) != 1:
        blockers.append("pptx-hash-mismatch")
    if blockers:
        raise GateBlockedError(
            "target-render-matrix", tuple(sorted(set(blockers)))
        )
    return TargetEvidenceMatrix(
        pptx_sha256=next(iter(hashes)), target_ids=required
    )
