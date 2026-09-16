"""Shared schema 3 delivery builders; target captures here are simulations only."""

from __future__ import annotations

from pathlib import Path

from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
from tests.v16_visual_fixtures import prepared_g2
from tests.host_confirmation_fixtures import gate_confirmation_kwargs


def prepared_g3(
    project: Path, slide_count: int = 3
) -> tuple[DeliveryService, int, dict[str, object]]:
    visual, revision, refs = prepared_g2(project, slide_count=slide_count)
    published = visual.publish_visual_review("delivery-publish-visual", revision)
    visual_contract_ref = published.artifact_heads["visual/contract"]
    context = visual.gate_confirmation_context()
    g3 = visual.confirm_g3(
        "delivery-confirm-g3",
        published.revision,
        **gate_confirmation_kwargs(context),
    )
    return DeliveryService(visual.kernel), g3.revision, {
        **refs,
        "visual_contract": visual_contract_ref,
    }


def build_artifacts(
    delivery: DeliveryService, slide_ids: list[str], sha256: str = "7" * 64
) -> dict[str, str]:
    final_pptx_ref = str(
        delivery.kernel.artifacts.put(
            "final-pptx",
            {
                "pptx_sha256": sha256,
                "production_route": "strict-B",
                "slide_ids": slide_ids,
                "tool_name": "Codex Presentations",
            },
        )
    )
    editability_ref = str(
        delivery.kernel.artifacts.put(
            "editability-evidence",
            {
                "semantic_objects_editable": True,
                "whole_slide_bitmap": False,
                "slide_ids": slide_ids,
            },
        )
    )
    preflight_ref = str(
        delivery.kernel.artifacts.put(
            "preflight-render",
            {"identity": "preflight-only", "slide_ids": slide_ids},
        )
    )
    return {
        "final_pptx": final_pptx_ref,
        "editability": editability_ref,
        "preflight": preflight_ref,
        "pptx_sha256": sha256,
    }


def valid_build_payload(
    refs: dict[str, object], artifacts: dict[str, str]
) -> dict:
    return {
        "visual_contract_ref": refs["visual_contract"],
        "production_route": "strict-B",
        "source_pptx_ref": artifacts["final_pptx"],
        "pptx_sha256": artifacts["pptx_sha256"],
        "slide_ids": refs["slide_ids"],
        "native_editability_evidence_refs": [artifacts["editability"]],
        "preflight_render_refs": [artifacts["preflight"]],
        "preflight_identity": "preflight-only",
        "whole_slide_bitmap": False,
        "semantic_objects_native": True,
        "image_assets_independent": True,
        "tool_name": "Codex Presentations",
        "tool_version": "presentations/test-contract-version",
    }


def prepared_build(
    project: Path, slide_count: int = 2
) -> tuple[DeliveryService, int, dict[str, object]]:
    delivery, revision, refs = prepared_g3(project, slide_count=slide_count)
    artifacts = build_artifacts(
        delivery, refs["slide_ids"], sha256=refs["pptx_sha256"]
    )
    build_ref = delivery.register_build(
        "prepared-full-build",
        revision,
        valid_build_payload(refs, artifacts),
    )
    return delivery, revision + 1, {
        **refs,
        **artifacts,
        "build": build_ref,
    }


def valid_slide_qa(
    delivery: DeliveryService,
    refs: dict[str, object],
    slide_id: str,
    *,
    result: str = "passed",
) -> dict:
    render_ref = str(
        delivery.kernel.artifacts.put(
            "slide-render",
            {"build_ref": refs["build"], "slide_id": slide_id},
        )
    )
    object_report_ref = str(
        delivery.kernel.artifacts.put(
            "object-report",
            {
                "build_ref": refs["build"],
                "slide_id": slide_id,
                "native_objects": True,
            },
        )
    )
    return {
        "build_ref": refs["build"],
        "pptx_sha256": refs["pptx_sha256"],
        "slide_id": slide_id,
        "semantic_result": result,
        "aesthetic_result": result,
        "engineering_result": result,
        "preflight_result": result,
        "evidence_refs": [render_ref, object_report_ref],
        "reviewer_roles": ["独立审美审查智能体", "PPT 工程审查智能体"],
        "overall_result": result,
        **(
            {
                "failure_reason": "本页四门存在失败项",
                "repair_instruction": "只修复本页失败对象并重新复验",
            }
            if result == "failed"
            else {}
        ),
    }


def valid_deck_qa(
    delivery: DeliveryService,
    refs: dict[str, object],
    slide_qa_refs: list[str],
) -> dict:
    evidence_ref = str(
        delivery.kernel.artifacts.put(
            "deck-rhythm-report",
            {"build_ref": refs["build"], "slide_ids": refs["slide_ids"]},
        )
    )
    return {
        "build_ref": refs["build"],
        "pptx_sha256": refs["pptx_sha256"],
        "slide_ids": refs["slide_ids"],
        "slide_qa_refs": slide_qa_refs,
        "sequence_result": "passed",
        "rhythm_result": "passed",
        "page_family_variation_result": "passed",
        "repetition_result": "passed",
        "density_result": "passed",
        "footer_pagination_result": "passed",
        "coherence_result": "passed",
        "evidence_refs": [evidence_ref],
        "reviewer_roles": ["独立审美审查智能体", "PPT 工程审查智能体"],
        "overall_result": "passed",
    }


def prepared_qa(
    project: Path, slide_count: int = 2
) -> tuple[DeliveryService, int, dict[str, object]]:
    delivery, revision, refs = prepared_build(project, slide_count=slide_count)
    slide_qa_refs: list[str] = []
    for slide_id in refs["slide_ids"]:
        slide_qa_refs.append(
            delivery.register_slide_qa(
                f"prepared-qa-{slide_id}",
                revision,
                valid_slide_qa(delivery, refs, slide_id),
            )
        )
        revision += 1
    deck_qa_ref = delivery.register_deck_qa(
        "prepared-deck-qa",
        revision,
        valid_deck_qa(delivery, refs, slide_qa_refs),
    )
    return delivery, revision + 1, {
        **refs,
        "slide_qa": slide_qa_refs,
        "deck_qa": deck_qa_ref,
    }


def rich_g4_target_payload(
    delivery: DeliveryService, target_id: str, refs: dict[str, object]
) -> dict:
    operating_system = "macOS" if target_id.startswith("macos") else "Windows 11"
    application = "WPS Office" if target_id.endswith("wps") else "Microsoft PowerPoint"
    font_inventory_ref = str(
        delivery.kernel.artifacts.put(
            "font-inventory", {"target_id": target_id, "fonts": ["Arial"]}
        )
    )
    font_plan_ref = str(
        delivery.kernel.artifacts.put(
            "font-plan",
            {"target_id": target_id, "fallback": "Arial", "risks": []},
        )
    )
    reviewer_attestation_ref = str(
        delivery.kernel.artifacts.put(
            "desktop-review-attestation",
            {
                "target_id": target_id,
                "reviewer_id": "desktop-qa-operator",
                "independent_from_producer": True,
                "result": "passed",
            },
        )
    )
    export_ref = str(
        delivery.kernel.artifacts.put(
            "target-export", {"target_id": target_id, "format": "pdf"}
        )
    )
    page_image_ref = str(
        delivery.kernel.artifacts.put(
            "target-page-image",
            {"target_id": target_id, "slide_ids": refs["slide_ids"]},
        )
    )
    slide_check_refs = {
        slide_id: str(
            delivery.kernel.artifacts.put(
                "slide-check",
                {
                    "target_id": target_id,
                    "slide_id": slide_id,
                    "result": "passed",
                },
            )
        )
        for slide_id in refs["slide_ids"]
    }
    capture_ref = str(
        delivery.kernel.artifacts.put(
            "target-render-capture",
            {"target_id": target_id, "identity": "formal-target-render"},
        )
    )
    return {
        "stage": "G4",
        "presentation_build_ref": refs["build"],
        "target_id": target_id,
        "evidence_identity": "formal-target-render",
        "operating_system": operating_system,
        "operating_system_version": "15.6" if operating_system == "macOS" else "24H2",
        "application": application,
        "application_version": f"{target_id}/test-version",
        "application_check_result": "passed",
        "font_check_result": "passed",
        "font_inventory_ref": font_inventory_ref,
        "font_substitution_plan_ref": font_plan_ref,
        "reviewer_attestation_ref": reviewer_attestation_ref,
        "source_pptx_ref": refs["final_pptx"],
        "pptx_sha256": refs["pptx_sha256"],
        "sha256_before": refs["pptx_sha256"],
        "sha256_after": refs["pptx_sha256"],
        "export_refs": [export_ref],
        "page_image_refs": [page_image_ref],
        "slide_checks": [
            {
                "slide_id": slide_id,
                "semantic_result": "passed",
                "aesthetic_result": "passed",
                "engineering_result": "passed",
                "target_render_result": "passed",
                "evidence_refs": [slide_check_refs[slide_id]],
            }
            for slide_id in refs["slide_ids"]
        ],
        "executor": "desktop-qa-operator",
        "exported_at": "2026-08-09T12:00:00+08:00",
        "tool_version": "target-capture/1.0",
        "overall_result": "passed",
        "evidence_ref": capture_ref,
    }


def prepared_delivery_ready(
    project: Path, slide_count: int = 2
) -> tuple[DeliveryService, int, dict[str, object]]:
    delivery, revision, refs = prepared_qa(project, slide_count=slide_count)
    target_refs: list[str] = []
    policy_ref, policy = ReleaseTargetPolicyService(delivery.kernel).current()
    for target_id in policy.required_target_ids:
        target_refs.append(
            delivery.register_target_render_evidence(
                f"prepared-g4-target-{target_id}",
                revision,
                rich_g4_target_payload(delivery, target_id, refs),
            )
        )
        revision += 1
    ready = delivery.finalize_delivery("prepared-delivery-ready", revision)
    return delivery, ready.revision, {
        **refs,
        "g4_target_evidence": target_refs,
        "release_target_policy_ref": policy_ref,
    }


def package_artifacts(delivery: DeliveryService, refs: dict[str, object]) -> dict[str, str]:
    policy_ref, policy = ReleaseTargetPolicyService(delivery.kernel).current()
    return {
        "preview": str(
            delivery.kernel.artifacts.put(
                "delivery-preview", {"build_ref": refs["build"]}
            )
        ),
        "source_manifest": str(
            delivery.kernel.artifacts.put(
                "source-manifest", {"visual_contract_ref": refs["visual_contract"]}
            )
        ),
        "font_platform_report": str(
            delivery.kernel.artifacts.put(
            "font-platform-report",
                {
                    "build_ref": refs["build"],
                    "release_target_policy_ref": policy_ref,
                    "targets": list(policy.required_target_ids),
                    "deferred_targets": list(policy.deferred_target_ids),
                },
            )
        ),
        "qa_report": str(
            delivery.kernel.artifacts.put(
                "delivery-qa-report",
                {"build_ref": refs["build"], "deck_qa_ref": refs["deck_qa"]},
            )
        ),
    }


def valid_package_payload(
    refs: dict[str, object], artifacts: dict[str, str]
) -> dict:
    return {
        "build_ref": refs["build"],
        "pptx_ref": refs["final_pptx"],
        "pptx_sha256": refs["pptx_sha256"],
        "preview_refs": [artifacts["preview"]],
        "source_manifest_ref": artifacts["source_manifest"],
        "font_platform_report_ref": artifacts["font_platform_report"],
        "qa_report_ref": artifacts["qa_report"],
        "target_evidence_refs": refs["g4_target_evidence"],
        "release_target_policy_ref": refs["release_target_policy_ref"],
        "status": "delivery-ready",
    }
