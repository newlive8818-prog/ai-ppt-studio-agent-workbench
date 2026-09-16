"""Strict-route-B delivery artifact contracts."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ai_ppt_studio.errors import ContractValidationError

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_SCORE_FIELDS = frozenset(
    {"score", "rating", "average", "weight", "weighted_score", "vote", "conditional_pass"}
)
SLIDE_QA_RESULTS = (
    "semantic_result",
    "aesthetic_result",
    "engineering_result",
    "preflight_result",
)
DECK_QA_RESULTS = (
    "sequence_result",
    "rhythm_result",
    "page_family_variation_result",
    "repetition_result",
    "density_result",
    "footer_pagination_result",
    "coherence_result",
)
REQUIRED_DELIVERY_REVIEWERS = ["独立审美审查智能体", "PPT 工程审查智能体"]


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _refs(payload: dict[str, Any], field: str) -> list[str]:
    values = payload.get(field)
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value for value in values)
    ):
        raise ContractValidationError(f"{field} must contain artifact references")
    return list(values)


def validate_presentation_build(
    payload: dict[str, Any], visual_contract: dict[str, Any]
) -> dict[str, Any]:
    """Require a complete native editable deck produced by Codex Presentations."""

    if not isinstance(payload, dict):
        raise ContractValidationError("PresentationBuild must be an object")
    normalized = dict(payload)
    normalized["visual_contract_ref"] = _text(payload, "visual_contract_ref")
    if payload.get("production_route") != "strict-B":
        raise ContractValidationError("Formal delivery requires strict-B")
    normalized["production_route"] = "strict-B"
    normalized["source_pptx_ref"] = _text(payload, "source_pptx_ref")
    sha256 = _text(payload, "pptx_sha256")
    if not SHA256_PATTERN.fullmatch(sha256):
        raise ContractValidationError(
            "PresentationBuild pptx_sha256 must be a lowercase SHA-256"
        )
    normalized["pptx_sha256"] = sha256
    expected_slide_ids = [
        contract.get("slide_id")
        for contract in visual_contract.get("slide_contracts") or []
        if isinstance(contract, dict)
    ]
    slide_ids = payload.get("slide_ids")
    if (
        not expected_slide_ids
        or slide_ids != expected_slide_ids
        or len(set(slide_ids or [])) != len(expected_slide_ids)
    ):
        raise ContractValidationError(
            "PresentationBuild must cover every frozen slide exactly once in final order"
        )
    normalized["slide_ids"] = list(slide_ids)
    normalized["native_editability_evidence_refs"] = _refs(
        payload, "native_editability_evidence_refs"
    )
    normalized["preflight_render_refs"] = _refs(
        payload, "preflight_render_refs"
    )
    if payload.get("preflight_identity") != "preflight-only":
        raise ContractValidationError(
            "Development renders must remain identified as preflight-only"
        )
    normalized["preflight_identity"] = "preflight-only"
    boolean_requirements = {
        "whole_slide_bitmap": False,
        "semantic_objects_native": True,
        "image_assets_independent": True,
    }
    for field, expected in boolean_requirements.items():
        if payload.get(field) is not expected:
            raise ContractValidationError(
                f"PresentationBuild requires {field}={expected}"
            )
        normalized[field] = expected
    if _text(payload, "tool_name") != "Codex Presentations":
        raise ContractValidationError(
            "Codex Presentations is the only formal PPTX production route"
        )
    normalized["tool_name"] = "Codex Presentations"
    normalized["tool_version"] = _text(payload, "tool_version")
    if "last_valid_build_ref" in payload:
        normalized["last_valid_build_ref"] = _text(
            payload, "last_valid_build_ref"
        )
    return normalized


def _binary_review(
    payload: dict[str, Any], result_fields: tuple[str, ...]
) -> dict[str, Any]:
    forbidden = FORBIDDEN_SCORE_FIELDS.intersection(payload)
    if forbidden:
        raise ContractValidationError(
            f"Delivery QA cannot contain score fields: {', '.join(sorted(forbidden))}"
        )
    normalized = dict(payload)
    failed = False
    for field in result_fields:
        result = _text(payload, field)
        if result not in {"passed", "failed"}:
            raise ContractValidationError(f"{field} must be passed or failed")
        normalized[field] = result
        failed = failed or result == "failed"
    expected_overall = "failed" if failed else "passed"
    if payload.get("overall_result") != expected_overall:
        raise ContractValidationError(
            f"overall_result must be {expected_overall}"
        )
    if failed and (
        not str(payload.get("failure_reason") or "").strip()
        or not str(payload.get("repair_instruction") or "").strip()
    ):
        raise ContractValidationError(
            "Failed delivery QA requires reason and repair instruction"
        )
    normalized["overall_result"] = expected_overall
    normalized["evidence_refs"] = _refs(payload, "evidence_refs")
    if payload.get("reviewer_roles") != REQUIRED_DELIVERY_REVIEWERS:
        raise ContractValidationError(
            "Delivery QA requires independent aesthetic and PPT engineering reviewers"
        )
    normalized["reviewer_roles"] = list(REQUIRED_DELIVERY_REVIEWERS)
    return normalized


def validate_slide_qa(
    payload: dict[str, Any], build: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("SlideQA must be an object")
    normalized = _binary_review(payload, SLIDE_QA_RESULTS)
    normalized["build_ref"] = _text(payload, "build_ref")
    normalized["pptx_sha256"] = _text(payload, "pptx_sha256")
    slide_id = _text(payload, "slide_id")
    if (
        normalized["pptx_sha256"] != build.get("pptx_sha256")
        or slide_id not in (build.get("slide_ids") or [])
    ):
        raise ContractValidationError(
            "SlideQA must bind the current build hash and one final slide"
        )
    normalized["slide_id"] = slide_id
    return normalized


def validate_deck_qa(
    payload: dict[str, Any], build: dict[str, Any], current_slide_qa_refs: list[str]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("DeckQA must be an object")
    normalized = _binary_review(payload, DECK_QA_RESULTS)
    normalized["build_ref"] = _text(payload, "build_ref")
    normalized["pptx_sha256"] = _text(payload, "pptx_sha256")
    if (
        normalized["pptx_sha256"] != build.get("pptx_sha256")
        or payload.get("slide_ids") != build.get("slide_ids")
        or payload.get("slide_qa_refs") != current_slide_qa_refs
    ):
        raise ContractValidationError(
            "DeckQA must cover the current build and every current slide QA in order"
        )
    normalized["slide_ids"] = list(build["slide_ids"])
    normalized["slide_qa_refs"] = list(current_slide_qa_refs)
    return normalized


def validate_failed_attempt(
    payload: dict[str, Any], current_build_ref: str, build: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("FailedBuildAttempt must be an object")
    normalized = dict(payload)
    normalized["attempt_ref"] = _text(payload, "attempt_ref")
    if payload.get("last_valid_build_ref") != current_build_ref:
        raise ContractValidationError(
            "Failed attempt must preserve the current last-valid build"
        )
    normalized["last_valid_build_ref"] = current_build_ref
    target_slide_ids = payload.get("target_slide_ids")
    if (
        not isinstance(target_slide_ids, list)
        or not target_slide_ids
        or not set(target_slide_ids).issubset(set(build.get("slide_ids") or []))
    ):
        raise ContractValidationError(
            "Failed attempt target slides must belong to the last-valid build"
        )
    normalized["target_slide_ids"] = list(target_slide_ids)
    for field in ("failure_code", "failure_reason", "retry_policy"):
        normalized[field] = _text(payload, field)
    return normalized


def validate_repair(
    payload: dict[str, Any], failed_attempt_ref: str, current_build_ref: str, build: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractValidationError("DeliveryRepair must be an object")
    normalized = dict(payload)
    if payload.get("failed_attempt_ref") != failed_attempt_ref:
        raise ContractValidationError("Repair must target the current failed attempt")
    if payload.get("last_valid_build_ref") != current_build_ref:
        raise ContractValidationError("Repair must preserve the current valid build")
    target_slide_ids = payload.get("target_slide_ids")
    if (
        not isinstance(target_slide_ids, list)
        or not target_slide_ids
        or not set(target_slide_ids).issubset(set(build.get("slide_ids") or []))
    ):
        raise ContractValidationError("Repair target slides are invalid")
    normalized["target_slide_ids"] = list(target_slide_ids)
    normalized["preserve_refs"] = _refs(payload, "preserve_refs")
    for field in ("failure_conditions", "review_route"):
        values = payload.get(field)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
        ):
            raise ContractValidationError(f"{field} must be a non-empty string array")
        normalized[field] = list(values)
    normalized["required_outcome"] = _text(payload, "required_outcome")
    normalized["failed_attempt_ref"] = failed_attempt_ref
    normalized["last_valid_build_ref"] = current_build_ref
    return normalized


def validate_delivery_package(
    payload: dict[str, Any],
    build: dict[str, Any],
    target_refs: list[str],
    release_target_policy_ref: str,
) -> dict[str, Any]:
    """Bind the user-facing package to one complete delivery-ready build."""

    if not isinstance(payload, dict):
        raise ContractValidationError("DeliveryPackage must be an object")
    normalized = dict(payload)
    normalized["build_ref"] = _text(payload, "build_ref")
    normalized["pptx_ref"] = _text(payload, "pptx_ref")
    normalized["pptx_sha256"] = _text(payload, "pptx_sha256")
    if (
        normalized["pptx_ref"] != build.get("source_pptx_ref")
        or normalized["pptx_sha256"] != build.get("pptx_sha256")
    ):
        raise ContractValidationError(
            "DeliveryPackage must bind the current final PPTX and SHA-256"
        )
    normalized["preview_refs"] = _refs(payload, "preview_refs")
    for field in (
        "source_manifest_ref",
        "font_platform_report_ref",
        "qa_report_ref",
    ):
        normalized[field] = _text(payload, field)
    if payload.get("target_evidence_refs") != target_refs:
        raise ContractValidationError(
            "DeliveryPackage must contain all current required G4 target evidence references in canonical order"
        )
    normalized["target_evidence_refs"] = list(target_refs)
    if payload.get("release_target_policy_ref") != release_target_policy_ref:
        raise ContractValidationError(
            "DeliveryPackage must bind the current release target policy"
        )
    normalized["release_target_policy_ref"] = release_target_policy_ref
    if payload.get("status") != "delivery-ready":
        raise ContractValidationError(
            "DeliveryPackage status must be delivery-ready"
        )
    normalized["status"] = "delivery-ready"
    return normalized


def validate_chat_delivery_receipt(
    payload: dict[str, Any],
    build_ref: str,
    package_ref: str,
    build: dict[str, Any],
) -> dict[str, Any]:
    """Validate a PPTX chat send without treating it as user acceptance."""

    if not isinstance(payload, dict):
        raise ContractValidationError("ChatDeliveryReceipt must be an object")
    normalized = dict(payload)
    if payload.get("delivery_type") != "pptx":
        raise ContractValidationError("Chat delivery_type must be pptx")
    normalized["delivery_type"] = "pptx"
    if payload.get("build_ref") != build_ref:
        raise ContractValidationError("Chat delivery must bind the current build")
    normalized["build_ref"] = build_ref
    if payload.get("package_ref") != package_ref:
        raise ContractValidationError("Chat delivery must bind the current package")
    normalized["package_ref"] = package_ref
    normalized["pptx_ref"] = _text(payload, "pptx_ref")
    normalized["pptx_sha256"] = _text(payload, "pptx_sha256")
    if (
        normalized["pptx_ref"] != build.get("source_pptx_ref")
        or normalized["pptx_sha256"] != build.get("pptx_sha256")
    ):
        raise ContractValidationError(
            "Chat delivery must bind the current final PPTX and SHA-256"
        )
    artifact_refs = _refs(payload, "artifact_refs")
    if (
        package_ref not in artifact_refs
        or normalized["pptx_ref"] not in artifact_refs
        or len(set(artifact_refs)) != len(artifact_refs)
    ):
        raise ContractValidationError(
            "Chat delivery artifacts must uniquely include the package and final PPTX"
        )
    normalized["artifact_refs"] = artifact_refs
    message_ref = _text(payload, "message_ref")
    if not message_ref.startswith("chat://message/"):
        raise ContractValidationError(
            "Chat delivery requires a chat://message send identity"
        )
    normalized["message_ref"] = message_ref
    send_status = _text(payload, "send_status")
    if send_status not in {"sent", "failed"}:
        raise ContractValidationError("send_status must be sent or failed")
    normalized["send_status"] = send_status
    sent_at = _text(payload, "sent_at")
    try:
        timestamp = datetime.fromisoformat(sent_at)
    except ValueError as error:
        raise ContractValidationError("sent_at must be an ISO timestamp") from error
    if timestamp.tzinfo is None:
        raise ContractValidationError("sent_at must include a timezone offset")
    normalized["sent_at"] = sent_at
    retry_of = payload.get("retry_of", "")
    if not isinstance(retry_of, str):
        raise ContractValidationError("retry_of must be empty or an artifact reference")
    normalized["retry_of"] = retry_of
    return normalized
