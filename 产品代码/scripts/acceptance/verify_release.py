#!/usr/bin/env python3
"""Verify the installed plugin and final real-project acceptance state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (  # noqa: E402
    AcceptanceLedger,
    EvidenceIndex,
    extract_numbered_requirements,
)
from ai_ppt_studio.application.release_policy_service import (  # noqa: E402
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.domains.presentation.targets import (  # noqa: E402
    TargetRenderEvidence,
    validate_required_targets,
)
from ai_ppt_studio.errors import GateBlockedError  # noqa: E402
from ai_ppt_studio.kernel.references import ArtifactReference  # noqa: E402
from ai_ppt_studio.kernel.transactions import ProjectKernel  # noqa: E402

SOURCES = (
    (PROJECT / "01-产品需求基线-v1.0.md", "PRD", "验收标准"),
    (PROJECT / "02-系统详细设计-v1.0.md", "SDD", "测试策略"),
    (PROJECT / "03-UI设计与交互规范-v1.0.md", "UI", "UI 验收"),
)
DEFAULT_INSTALL_EVIDENCE = (
    ROOT / "output" / "acceptance" / "v1.6" / "plugin-install" / "install-evidence.json"
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, expected: type = dict) -> Any:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON evidence: {path}") from exc
    if not isinstance(payload, expected):
        raise ValueError(f"Evidence has the wrong shape: {path}")
    return payload


def _canonical(payload: object) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _authoritative_ledger(index: EvidenceIndex) -> AcceptanceLedger:
    requirements = []
    for path, prefix, section_title in SOURCES:
        requirements.extend(
            extract_numbered_requirements(
                path.read_text(encoding="utf-8"),
                source_prefix=prefix,
                source_file=path.name,
                section_title=section_title,
            )
        )
    return AcceptanceLedger("2.2", tuple(requirements)).with_evidence(index)


def _verify_ledger(
    ledger_path: Path,
    evidence_index_path: Path,
    *,
    fixture_mode: bool,
) -> tuple[AcceptanceLedger, EvidenceIndex]:
    index = EvidenceIndex.from_path(evidence_index_path)
    expected = _authoritative_ledger(index)
    checked_in = AcceptanceLedger.from_dict(_json(ledger_path))
    if not checked_in.requirements:
        raise ValueError("Final acceptance ledger is empty")
    if checked_in.requirement_ids != expected.requirement_ids:
        raise ValueError("Acceptance requirement identities drifted")
    for actual, authoritative in zip(
        checked_in.requirements, expected.requirements, strict=True
    ):
        if actual.text != authoritative.text:
            raise ValueError(
                f"Acceptance requirement text drifted: {actual.requirement_id}"
            )
    if _canonical(checked_in.as_dict()) != _canonical(expected.as_dict()):
        raise ValueError(
            "Acceptance ledger does not match the authoritative baselines and evidence index"
        )
    for requirement in checked_in.requirements:
        if (
            requirement.status != "passed"
            or requirement.missing_evidence
            or not requirement.proof_refs
        ):
            raise ValueError(
                f"Acceptance requirement remains unproven: {requirement.requirement_id}"
            )
    if not fixture_mode:
        for proof in index.proofs:
            payload = _json(Path(proof.path))
            identity = str(payload.get("evidence_identity") or "").lower()
            if (
                payload.get("simulation") is True
                or payload.get("proof_eligible") is False
                or "fixture" in identity
                or "simulation" in identity
            ):
                raise ValueError(
                    f"Deterministic fixture cannot close formal acceptance: {proof.proof_ref}"
                )
    return checked_in, index


def _safe_release_file(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError(f"Release manifest path must be relative: {relative}")
    target = (root / relative).resolve(strict=True)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Release file escapes the installed plugin: {relative}") from exc
    if target.is_symlink() or not target.is_file():
        raise ValueError(f"Installed release entry is not a regular file: {relative}")
    return target


def _verify_installed_release(
    install_evidence_path: Path, *, fixture_mode: bool
) -> dict[str, Any]:
    evidence = _json(install_evidence_path)
    if str(evidence.get("schema_version")) != "1.0":
        raise ValueError("Unsupported plugin install evidence schema")
    identity = str(evidence.get("evidence_identity") or "")
    if fixture_mode:
        if identity not in {
            "deterministic-contract-fixture",
            "real-local-plugin-install",
        }:
            raise ValueError("Unknown fixture install evidence identity")
    elif identity != "real-local-plugin-install":
        raise ValueError("Formal acceptance requires a real local plugin install")
    cache_root = Path(str(evidence.get("installed_cache_root") or "")).expanduser()
    cache = cache_root.resolve(strict=True)
    if cache.is_symlink() or not cache.is_dir():
        raise ValueError("Installed plugin cache root must be a real directory")
    manifest_path = cache / "release-manifest.json"
    manifest_hash = str(evidence.get("release_manifest_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest_hash) or _sha(
        manifest_path
    ) != manifest_hash:
        raise ValueError("Installed release manifest identity changed")
    manifest = _json(manifest_path)
    files = manifest.get("files")
    manifest_catalog_hash = str(manifest.get("tool_catalog_sha256") or "")
    if (
        str(manifest.get("schema_version")) != "1.0"
        or manifest.get("plugin_name") != "ai-ppt-studio"
        or manifest.get("hash_algorithm") != "sha256"
        or not isinstance(files, dict)
        or not files
    ):
        raise ValueError("Installed release manifest is incomplete")
    for relative, digest in files.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise ValueError(f"Installed release digest is invalid: {relative}")
        if _sha(_safe_release_file(cache, str(relative))) != digest:
            raise ValueError(f"Installed release file hash mismatch: {relative}")
    probe = evidence.get("installed_probe")
    tools = probe.get("tools") if isinstance(probe, dict) else None
    probe_catalog_hash = (
        str(probe.get("tool_catalog_sha256") or "")
        if isinstance(probe, dict)
        else ""
    )
    tool_catalog_valid = (
        isinstance(tools, list)
        and bool(tools)
        and all(isinstance(tool, str) and tool for tool in tools)
        and len(tools) == len(set(tools))
        and probe.get("tool_count") == len(tools)
        and bool(re.fullmatch(r"[0-9a-f]{64}", probe_catalog_hash))
        and probe_catalog_hash == manifest_catalog_hash
    )
    professional_review = (
        probe.get("professional_review") if isinstance(probe, dict) else None
    )
    host_open = (
        professional_review.get("host_open")
        if isinstance(professional_review, dict)
        else None
    )
    host_notification = (
        professional_review.get("host_notification")
        if isinstance(professional_review, dict)
        else None
    )
    ai_receipt = (
        professional_review.get("ai_receipt")
        if isinstance(professional_review, dict)
        else None
    )
    professional_review_valid = (
        isinstance(professional_review, dict)
        and professional_review.get("review_session")
        in {"available", "unavailable"}
        and isinstance(
            professional_review.get("content_review_projection"), bool
        )
        and isinstance(
            professional_review.get("visual_review_projection"), bool
        )
        and isinstance(host_open, dict)
        and host_open.get("status") in {"available", "unavailable"}
        and host_open.get("code")
        in {"BROWSER_REVIEW_UNAVAILABLE", "BROWSER_REVIEW_AVAILABLE"}
        and isinstance(host_open.get("proofEligible"), bool)
        and isinstance(host_open.get("realHostEvidence"), bool)
        and isinstance(host_notification, dict)
        and host_notification.get("status")
        in {"available", "unavailable", "unverified"}
        and isinstance(host_notification.get("proofEligible"), bool)
        and isinstance(host_notification.get("realHostEvidence"), bool)
        and isinstance(ai_receipt, dict)
        and ai_receipt.get("status")
        in {"available", "unavailable", "unverified", "received"}
        and isinstance(ai_receipt.get("proofEligible"), bool)
        and isinstance(ai_receipt.get("realHostEvidence"), bool)
    )
    if (
        evidence.get("official_plugin_validation") != "passed"
        or evidence.get("runtime_recovery_test") != "passed"
        or not isinstance(probe, dict)
        or probe.get("status") != "passed"
        or probe.get("source_repository_pythonpath") is not False
        or not tool_catalog_valid
        or probe.get("chat_ui_template_count") != 0
        or probe.get("ordinary_tools_data_only") is not True
        or not professional_review_valid
    ):
        raise ValueError(
            "Installed plugin validation, recovery, MCP tool catalog, data-only, or host capability probe failed"
        )
    if not fixture_mode and (
        evidence.get("simulation") is True or evidence.get("proof_eligible") is False
    ):
        raise ValueError("Simulated plugin installation cannot close formal acceptance")
    return {
        "identity": identity,
        "cache_root": str(cache),
        "manifest_sha256": manifest_hash,
        "file_count": len(files),
        "tool_count": len(tools),
        "tool_catalog_sha256": probe_catalog_hash,
    }


def _artifact_payload(
    kernel: ProjectKernel, reference: str, expected_kind: str
) -> dict[str, Any]:
    try:
        record = kernel.artifacts.resolve(ArtifactReference.parse(reference))
    except Exception as exc:
        raise ValueError(f"Project artifact cannot be resolved: {reference}") from exc
    if record.get("kind") != expected_kind:
        raise ValueError(
            f"Project artifact kind mismatch: expected {expected_kind}, got {record.get('kind')}"
        )
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"Project artifact payload is invalid: {reference}")
    return payload


def _target_matrix(
    kernel: ProjectKernel,
    state: Any,
    *,
    stage: str,
    required_target_ids: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    prefix = "visual" if stage == "G2" else "delivery"
    values: list[TargetRenderEvidence] = []
    for target_id in required_target_ids:
        slot = f"{prefix}/target-evidence/{stage}/{target_id}"
        ref = state.artifact_heads.get(slot, "")
        if not ref:
            raise ValueError(f"Missing current {stage} target evidence: {target_id}")
        payload = _artifact_payload(kernel, ref, "target-render-evidence")
        try:
            item = TargetRenderEvidence.from_payload(payload)
        except ValueError as exc:
            raise ValueError(f"Invalid {stage} target evidence: {target_id}") from exc
        if item.target_id != target_id:
            raise ValueError(f"{stage} target slot identity mismatch: {target_id}")
        values.append(item)
    try:
        matrix = validate_required_targets(values, required_target_ids)
    except GateBlockedError as exc:
        raise ValueError(
            f"{stage} release-target evidence matrix is not complete"
        ) from exc
    return matrix.pptx_sha256, matrix.target_ids


def _verify_project(project_root: Path) -> dict[str, Any]:
    project = project_root.expanduser().resolve(strict=True)
    if project.is_symlink() or not project.is_dir() or project.parent.name != "projects":
        raise ValueError("Real acceptance project must be a regular managed projects child")
    state_json = _json(project / "kernel" / "state.json")
    if state_json.get("schema_version") != "3.0":
        raise ValueError("Final acceptance project must use schema 3.0")
    project_id = str(state_json.get("project_id") or "")
    if not project_id:
        raise ValueError("Final acceptance project lacks project identity")
    kernel = ProjectKernel(project, project_id=project_id)
    state = kernel.load()
    policy_ref, policy = ReleaseTargetPolicyService(kernel).current()
    for gate in ("G0", "G1", "G2", "G3", "G4"):
        if state.gate_status.get(gate) != "passed":
            raise ValueError(f"Final acceptance Gate is not passed: {gate}")
    g2_hash, g2_targets = _target_matrix(
        kernel,
        state,
        stage="G2",
        required_target_ids=policy.required_target_ids,
    )
    g4_hash, g4_targets = _target_matrix(
        kernel,
        state,
        stage="G4",
        required_target_ids=policy.required_target_ids,
    )
    if g2_hash != g4_hash:
        raise ValueError("G2 and G4 target matrices must use the same PPTX SHA-256")
    build_ref = state.artifact_heads.get("delivery/build", "")
    package_ref = state.artifact_heads.get("delivery/package", "")
    receipt_ref = state.artifact_heads.get("chat-delivery/pptx", "")
    confirmation_ref = state.artifact_heads.get("gate/G4/confirmation", "")
    if not all((build_ref, package_ref, receipt_ref, confirmation_ref)):
        raise ValueError("Final build, package, chat receipt, or G4 confirmation is missing")
    build = _artifact_payload(kernel, build_ref, "presentation-build")
    package = _artifact_payload(kernel, package_ref, "delivery-package")
    receipt = _artifact_payload(kernel, receipt_ref, "chat-delivery-receipt")
    confirmation = _artifact_payload(kernel, confirmation_ref, "g4-confirmation")
    if (
        build.get("pptx_sha256") != g4_hash
        or package.get("release_target_policy_ref") != policy_ref
        or package.get("build_ref") != build_ref
        or package.get("pptx_sha256") != g4_hash
        or receipt.get("build_ref") != build_ref
        or receipt.get("package_ref") != package_ref
        or receipt.get("pptx_sha256") != g4_hash
        or receipt.get("send_status") != "sent"
        or not str(receipt.get("message_ref") or "").startswith("chat://message/")
        or confirmation.get("build_ref") != build_ref
        or confirmation.get("package_ref") != package_ref
        or confirmation.get("receipt_ref") != receipt_ref
        or confirmation.get("release_target_policy_ref") != policy_ref
        or not str(confirmation.get("user_message_ref") or "").startswith(
            "chat://message/"
        )
    ):
        raise ValueError("Final delivery package, chat receipt, or G4 acceptance is stale")
    return {
        "project_id": project_id,
        "project_root": str(project),
        "revision": state.revision,
        "g2_pptx_sha256": g2_hash,
        "g4_pptx_sha256": g4_hash,
        "g2_targets": list(g2_targets),
        "g4_targets": list(g4_targets),
        "release_target_policy_ref": policy_ref,
        "required_target_ids": list(policy.required_target_ids),
        "deferred_target_ids": list(policy.deferred_target_ids),
        "chat_message_ref": receipt["message_ref"],
        "g4_user_message_ref": confirmation["user_message_ref"],
    }


def verify_final_acceptance(
    project_root: Path,
    ledger_path: Path,
    *,
    evidence_index_path: Path | None = None,
    install_evidence_path: Path | None = None,
    fixture_mode: bool = False,
) -> dict[str, Any]:
    ledger_file = ledger_path.expanduser().resolve(strict=True)
    evidence_file = (
        evidence_index_path.expanduser().resolve(strict=True)
        if evidence_index_path
        else ledger_file.with_name(
            ledger_file.name.replace("-acceptance-ledger.json", "-evidence.json")
        ).resolve(strict=True)
    )
    install_file = (
        install_evidence_path.expanduser().resolve(strict=True)
        if install_evidence_path
        else DEFAULT_INSTALL_EVIDENCE.resolve(strict=True)
    )
    ledger, index = _verify_ledger(
        ledger_file, evidence_file, fixture_mode=fixture_mode
    )
    installed = _verify_installed_release(install_file, fixture_mode=fixture_mode)
    project = _verify_project(project_root)
    return {
        "schema_version": "1.0",
        "evidence_identity": (
            "deterministic-contract-fixture"
            if fixture_mode
            else f"v{ledger.version}-final-acceptance"
        ),
        "proof_eligible": not fixture_mode,
        "simulation": fixture_mode,
        "acceptance_ledger_version": ledger.version,
        "requirement_count": len(ledger.requirements),
        "passed_requirement_count": sum(
            item.status == "passed" for item in ledger.requirements
        ),
        "proof_count": len(index.proofs),
        **installed,
        **project,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--evidence-index", type=Path)
    parser.add_argument("--install-evidence", type=Path)
    parser.add_argument("--fixture-mode", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_final_acceptance(
        args.project,
        args.ledger,
        evidence_index_path=args.evidence_index,
        install_evidence_path=args.install_evidence,
        fixture_mode=args.fixture_mode,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
