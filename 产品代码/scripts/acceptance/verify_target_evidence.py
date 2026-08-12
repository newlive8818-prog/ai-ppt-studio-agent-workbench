#!/usr/bin/env python3
"""Validate one immutable desktop target-evidence directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.presentation.targets import (
    SLIDE_RESULT_FIELDS,
    TARGET_PROFILES,
    TargetRenderEvidence,
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _inside(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError(f"Evidence file must be relative: {relative}")
    target = (root / relative).resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Evidence file escapes its directory: {relative}") from exc
    if target.is_symlink() or not target.is_file():
        raise ValueError(f"Evidence path must be a regular file: {relative}")
    return target


def _read_json(path: Path, expected: type) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Evidence JSON is invalid: {path}") from exc
    if not isinstance(payload, expected):
        raise ValueError(f"Evidence JSON has the wrong shape: {path}")
    return payload


def _artifact(kind: str, digest: str) -> str:
    return f"artifact://{kind}/{digest}"


def _timestamp(value: object, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def verify_target_evidence(
    evidence_dir: Path,
    source_pptx: Path,
    *,
    fixture_mode: bool = False,
) -> dict[str, Any]:
    root = evidence_dir.expanduser().resolve(strict=True)
    pptx = source_pptx.expanduser().resolve(strict=True)
    if root.is_symlink() or not root.is_dir() or pptx.is_symlink() or not pptx.is_file():
        raise ValueError("Evidence directory and source PPTX must be real paths")
    package = _read_json(root / "evidence-package.json", dict)
    if str(package.get("schema_version")) != "1.0":
        raise ValueError("Unsupported target evidence package schema")
    if not fixture_mode and package.get("capture_mode") != "desktop-evidence":
        raise ValueError("Formal target evidence requires desktop-evidence capture mode")
    expected_source_hash = str(package.get("source_pptx_sha256") or "")
    actual_source_hash = _sha(pptx)
    if expected_source_hash != actual_source_hash:
        raise ValueError("Source PPTX hash changed after desktop capture")
    source_kind = str(package.get("source_pptx_kind") or "")
    if source_kind not in {"native-pptx", "final-pptx"}:
        raise ValueError("source_pptx_kind must be native-pptx or final-pptx")
    declared_files = package.get("files")
    if not isinstance(declared_files, dict) or not declared_files:
        raise ValueError("Evidence package requires immutable file hashes")
    resolved_files: dict[str, Path] = {}
    for relative, digest in declared_files.items():
        if not isinstance(relative, str) or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise ValueError("Evidence file manifest is invalid")
        target = _inside(root, relative)
        if _sha(target) != digest:
            raise ValueError(f"Evidence file hash mismatch: {relative}")
        resolved_files[relative] = target
    required = {
        "environment.json",
        "font-inventory.json",
        "font-substitution-plan.json",
        "slide-checks.json",
        "reviewer-attestation.json",
    }
    if not required.issubset(resolved_files):
        raise ValueError("Evidence package misses environment, font, or slide checks")
    environment = _read_json(resolved_files["environment.json"], dict)
    target_id = str(environment.get("target_id") or "")
    if target_id not in TARGET_PROFILES:
        raise ValueError(f"Unknown target profile: {target_id}")
    expected_os, expected_application = TARGET_PROFILES[target_id]
    if (
        environment.get("operating_system") != expected_os
        or environment.get("application") != expected_application
    ):
        raise ValueError("Desktop environment does not match the target identity")
    for field in (
        "operating_system_version",
        "application_version",
        "executor",
        "exported_at",
        "tool_version",
    ):
        if not str(environment.get(field) or "").strip():
            raise ValueError(f"Desktop environment requires {field}")
    exported_at = _timestamp(environment["exported_at"], "exported_at")
    application_check = str(environment.get("application_check_result") or "")
    if application_check not in {"passed", "failed"}:
        raise ValueError("application_check_result must come from the desktop reviewer")
    font_inventory = _read_json(resolved_files["font-inventory.json"], dict)
    font_plan = _read_json(resolved_files["font-substitution-plan.json"], dict)
    if not isinstance(font_inventory.get("fonts"), list) or not font_inventory["fonts"]:
        raise ValueError("Font inventory cannot be empty")
    font_result = str(font_plan.get("result") or "")
    if font_result not in {"passed", "failed"}:
        raise ValueError("Font substitution result must be independently recorded")
    attestation = _read_json(
        resolved_files["reviewer-attestation.json"], dict
    )
    for field in ("reviewer_id", "reviewer_role"):
        if not str(attestation.get(field) or "").strip():
            raise ValueError(f"Independent reviewer attestation requires {field}")
    if attestation.get("independent_from_producer") is not True:
        raise ValueError("Desktop reviewer must attest independence from production")
    if (
        attestation.get("application_check_result") != application_check
        or attestation.get("font_check_result") != font_result
        or attestation.get("slide_checks_file") != "slide-checks.json"
    ):
        raise ValueError("Independent reviewer attestation does not match the package")
    reviewed_at = _timestamp(attestation.get("reviewed_at"), "reviewed_at")
    if reviewed_at < exported_at:
        raise ValueError("Independent desktop review cannot predate the export")
    exports = package.get("export_files")
    page_images = package.get("page_image_files")
    if (
        not isinstance(exports, list)
        or not exports
        or not isinstance(page_images, list)
        or not page_images
        or any(value not in resolved_files for value in [*exports, *page_images])
    ):
        raise ValueError("Evidence exports and page images must be hash-verified")
    checks = _read_json(resolved_files["slide-checks.json"], list)
    if not checks:
        raise ValueError("Evidence requires per-slide checks")
    normalized_checks: list[dict[str, Any]] = []
    seen: set[str] = set()
    failed = application_check == "failed" or font_result == "failed"
    for raw in checks:
        if not isinstance(raw, dict):
            raise ValueError("Slide checks must be objects")
        slide_id = str(raw.get("slide_id") or "")
        if not slide_id or slide_id in seen:
            raise ValueError("Slide checks require unique slide IDs")
        seen.add(slide_id)
        page_image = str(raw.get("page_image") or "")
        evidence_files = raw.get("evidence_files")
        if (
            page_image not in page_images
            or not isinstance(evidence_files, list)
            or not evidence_files
            or page_image not in evidence_files
            or any(value not in resolved_files for value in evidence_files)
        ):
            raise ValueError("Every slide check requires a verified page image")
        results = {field: raw.get(field) for field in SLIDE_RESULT_FIELDS}
        if any(value not in {"passed", "failed"} for value in results.values()):
            raise ValueError("Slide checks must preserve independent binary results")
        is_failed = "failed" in results.values()
        failed = failed or is_failed
        if is_failed and (
            not str(raw.get("failure_reason") or "").strip()
            or not str(raw.get("repair_instruction") or "").strip()
        ):
            raise ValueError("Failed slide checks require a directed repair")
        check_core = {
            "slide_id": slide_id,
            **results,
            **(
                {
                    "failure_reason": str(raw["failure_reason"]).strip(),
                    "repair_instruction": str(raw["repair_instruction"]).strip(),
                }
                if is_failed
                else {}
            ),
        }
        evidence_digest = _canonical_sha(
            {
                "check": check_core,
                "files": {value: declared_files[value] for value in evidence_files},
            }
        )
        normalized_checks.append(
            {
                **check_core,
                "evidence_refs": [_artifact("slide-check", evidence_digest)],
            }
        )
    if {str(check["page_image"]) for check in checks} != set(page_images):
        raise ValueError("Page image manifest must exactly cover the checked slides")
    computed_result = "failed" if failed else "passed"
    if environment.get("overall_result") != computed_result:
        raise ValueError(
            "Desktop overall_result must match application, font, and slide findings"
        )
    base_payload = {
        "target_id": target_id,
        "evidence_identity": (
            "deterministic-contract-fixture"
            if fixture_mode
            else "formal-target-render"
        ),
        "operating_system": expected_os,
        "operating_system_version": str(environment["operating_system_version"]),
        "application": expected_application,
        "application_version": str(environment["application_version"]),
        "application_check_result": application_check,
        "font_check_result": font_result,
        "font_inventory_ref": _artifact(
            "font-inventory", declared_files["font-inventory.json"]
        ),
        "font_substitution_plan_ref": _artifact(
            "font-plan", declared_files["font-substitution-plan.json"]
        ),
        "reviewer_attestation_ref": _artifact(
            "desktop-review-attestation",
            declared_files["reviewer-attestation.json"],
        ),
        "source_pptx_ref": _artifact(source_kind, actual_source_hash),
        "pptx_sha256": actual_source_hash,
        "sha256_before": expected_source_hash,
        "sha256_after": actual_source_hash,
        "export_refs": [
            _artifact("target-export", declared_files[value]) for value in exports
        ],
        "page_image_refs": [
            _artifact("target-page-image", declared_files[value])
            for value in page_images
        ],
        "slide_checks": normalized_checks,
        "executor": str(environment["executor"]),
        "exported_at": str(environment["exported_at"]),
        "tool_version": str(environment["tool_version"]),
        "overall_result": computed_result,
    }
    evidence_digest = _canonical_sha(
        {"package": package, "payload": base_payload}
    )
    payload = {
        **base_payload,
        "evidence_ref": _artifact("target-render-capture", evidence_digest),
        "verified_file_hashes": dict(declared_files),
        "verification_mode": "validate-independent-desktop-record",
        "simulation": fixture_mode,
        "proof_eligible": not fixture_mode,
    }
    if not fixture_mode:
        TargetRenderEvidence.from_payload(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--source-pptx", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fixture-mode", action="store_true")
    args = parser.parse_args()
    payload = verify_target_evidence(
        args.evidence_dir, args.source_pptx, fixture_mode=args.fixture_mode
    )
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
