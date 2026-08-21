"""Shared builders for schema 3 visual contract tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_review.batch_service import ContentReviewBatchService
from ai_ppt_studio.application.content_review.decision_service import ContentDecisionService
from ai_ppt_studio.application.presales_content_service import PresalesContentService
from ai_ppt_studio.application.review_session_service import ReviewSessionService
from ai_ppt_studio.application.release_policy_service import ReleaseTargetPolicyService
from ai_ppt_studio.application.visual_service import VisualService
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from tests.test_v22_content_repair_loop import build_content
from tests.host_confirmation_fixtures import gate_confirmation_kwargs


G2_REVIEW_FORGERY_VARIANTS = (
    "self-review",
    "empty-checks",
    "forbidden-score",
    "forged-hard-failure",
    "missing-check-evidence",
    "unresolvable-check-evidence",
    "unresolvable-wrong-kind-check-evidence",
    "resolvable-wrong-kind-check-evidence",
)


def forge_g2_visual_review(
    payload: dict,
    variant: str,
    *,
    resolvable_wrong_kind_ref: str | None = None,
) -> dict:
    """Return a raw current-head corruption that the G2 validator must reject."""

    forged = deepcopy(payload)
    if variant == "self-review":
        forged["reviewer_role"] = forged["producer_role"]
    elif variant == "empty-checks":
        forged["checks"] = []
    elif variant == "forbidden-score":
        forged["score"] = 100
    elif variant == "forged-hard-failure":
        forged["checks"][0].update(
            {
                "result": "failed",
                "failure_reason": "锨点工程硬检查失败",
            }
        )
        forged["overall_result"] = "passed"
    elif variant == "missing-check-evidence":
        forged["checks"][0]["evidence_refs"] = []
    elif variant == "unresolvable-check-evidence":
        forged["checks"][0]["evidence_refs"] = [
            "artifact://anchor-slide-set/" + "0" * 64
        ]
    elif variant == "unresolvable-wrong-kind-check-evidence":
        reference = ArtifactReference.parse(forged["checks"][0]["evidence_refs"][0])
        forged["checks"][0]["evidence_refs"] = [
            f"artifact://visual-contract-set/{reference.sha256}"
        ]
    elif variant == "resolvable-wrong-kind-check-evidence":
        if not resolvable_wrong_kind_ref:
            raise AssertionError("Resolvable wrong-kind evidence ref is required")
        reference = ArtifactReference.parse(resolvable_wrong_kind_ref)
        if reference.kind == "anchor-slide-set":
            raise AssertionError("Wrong-kind evidence must not be an AnchorSlideSet")
        forged["checks"][0]["evidence_refs"] = [str(reference)]
    else:
        raise AssertionError(f"Unknown G2 review forgery variant: {variant}")
    return forged


def confirmed_g0(
    project: Path, project_id: str = "p1", slide_count: int = 1
) -> tuple[PresalesContentService, int, str]:
    kernel = ProjectKernel.initialize(project, project_id=project_id)
    ReleaseTargetPolicyService(kernel).bind_current_policy(
        "visual-fixture-release-policy", kernel.load().revision
    )
    content = PresalesContentService(kernel)
    blueprint_ref = build_content(kernel, slide_count=slide_count)
    blueprint_publication_revision = kernel.load().revision
    gates = ContentHardGateService(kernel)
    gates.run_evidence_gate(
        command_id="visual-fixture-evidence-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=[],
        reviewer_mode="isolated-review-task",
    )
    gates.run_presales_reading_gate(
        command_id="visual-fixture-reading-pass",
        expected_revision=kernel.load().revision,
        semantic_check_results=[],
        reviewer_mode="isolated-review-task",
    )
    blueprint = kernel.artifacts.resolve(ArtifactReference.parse(blueprint_ref))["payload"]
    state = kernel.load()
    _session_ref, session, state = ReviewSessionService(kernel).open_or_resume(
        command_id="visual-fixture-open-review",
        expected_revision=state.revision,
        review_type="content-full-deck",
        target_artifact_ref=blueprint_ref,
        source_version=blueprint["source_version"],
        source_revision=blueprint_publication_revision,
        open_policy="foreground-if-waiting",
    )
    decisions = ContentDecisionService(kernel)
    for slide in blueprint["slides"]:
        _decision_ref, _decision, state = decisions.save(
            command_id=f"visual-fixture-approve-{slide['slide_id']}",
            expected_revision=state.revision,
            review_session_id=session["review_session_id"],
            source_version=blueprint["source_version"],
            slide_id=slide["slide_id"],
            decision="approved",
            comment="",
        )
    _batch_ref, _batch, state = ContentReviewBatchService(kernel).submit(
        command_id="visual-fixture-submit-review",
        expected_revision=state.revision,
        review_session_id=session["review_session_id"],
        source_version=blueprint["source_version"],
    )
    state = content.open_g0_review(
        command_id="visual-fixture-open-g0",
        expected_revision=state.revision,
    )
    context = content.gate_confirmation_context()
    state = content.confirm_g0(
        command_id="visual-fixture-confirm-g0",
        expected_revision=state.revision,
        **gate_confirmation_kwargs(context),
    )
    return content, state.revision, blueprint_ref


def valid_visual_brief(blueprint_ref: str) -> dict:
    return {
        "reading_blueprint_ref": blueprint_ref,
        "production_route": "strict-B",
        "design_proposition": "以经营证据链建立可信决策",
        "audience_fit": "决策者先看结论，评审者可下钻证据",
        "narrative_rhythm": "问题—证据—方案—价值—行动",
        "imagery_strategy": "只使用可追溯素材和非语义装饰",
        "diagram_strategy": "关系使用原生可编辑对象",
        "powerpoint_constraints": "事实文字、数字和关系保持原生可编辑",
        "target_ids": ["macos-powerpoint"],
    }


def valid_design_system(brief_ref: str, blueprint_ref: str) -> dict:
    return {
        "visual_brief_ref": brief_ref,
        "reading_blueprint_ref": blueprint_ref,
        "production_route": "strict-B",
        "theme_proposition": "可信的经营证据链",
        "page_families": ["章节页", "证据页", "方案页"],
        "composition_grammar": "12 栅格，结论优先",
        "typography_tokens": {"title": "Microsoft YaHei", "body": "Microsoft YaHei"},
        "color_tokens": {"ink": "#172033", "accent": "#5B3DF5"},
        "imagery_strategy": "非语义图像可替换",
        "diagram_strategy": "原生线条和形状",
        "table_strategy": "原生表格",
        "editability_rules": "文字、数据、关系全部原生可编辑",
        "fallback_fonts": {"macOS": "PingFang SC", "Windows": "Microsoft YaHei"},
        "forbidden_patterns": ["整页位图", "数字评分"],
        "rule_definitions": [
            {
                "rule_id": "r1",
                "level": "must-follow",
                "condition": "事实文字存在",
                "expected_outcome": "原生可编辑",
                "evidence_method": "对象检查",
            }
        ],
    }


def valid_contract_set(
    system_ref: str,
    blueprint_ref: str,
    frozen_slides: list[dict] | None = None,
) -> dict:
    slides = frozen_slides or [
        {
            "slide_id": "S01",
            "page_task": "说明当前已知断点和证据边界",
            "reading_question": "当前已知什么，仍需验证什么",
            "neutral_title": "当前流程断点与证据边界",
            "visible_copy_blocks": [
                {"block_id": "b1", "text": "材料记录了流程断点", "identity": "来源事实"}
            ],
            "identity_labels": ["来源事实"],
            "evidence_bindings": [],
            "analysis_or_proposal_blocks": [],
            "solution_mapping_refs": ["mapping-1"],
            "previous_relation": "开篇",
            "next_relation": "进入方案要求",
            "speaker_notes": "解释来源",
            "reading_quality": {
                "independently_readable": True,
                "information_density": "moderate",
                "review_note": "事实与建议分开",
            },
            "material_mode": "material-backed",
        }
    ]
    return {
        "deck_design_system_ref": system_ref,
        "reading_blueprint_ref": blueprint_ref,
        "production_route": "strict-B",
        "role_runs": [
            {
                "role_id": "visual-art-director",
                "display_name": "视觉艺术指导智能体",
                "role_kind": "production",
                "context_pack_version": "visual-context-v1",
                "tool_pack_version": "native-visual-brief-v1",
            },
            {
                "role_id": "independent-aesthetic-reviewer",
                "display_name": "独立审美审查智能体",
                "role_kind": "review",
                "context_pack_version": "visual-review-context-v1",
                "tool_pack_version": "aesthetic-review-v1",
            },
        ],
        "slide_contracts": [
            {
                "slide_id": frozen["slide_id"],
                "order": index,
                "page_family": "证据页",
                "page_task": frozen["page_task"],
                "reading_question": frozen["reading_question"],
                "neutral_title": frozen["neutral_title"],
                "visible_copy_blocks": frozen["visible_copy_blocks"],
                "identity_labels": frozen["identity_labels"],
                "evidence_bindings": frozen["evidence_bindings"],
                "analysis_or_proposal_blocks": frozen[
                    "analysis_or_proposal_blocks"
                ],
                "solution_mapping_refs": frozen["solution_mapping_refs"],
                "previous_relation": frozen["previous_relation"],
                "next_relation": frozen["next_relation"],
                "speaker_notes": frozen["speaker_notes"],
                "reading_quality": frozen["reading_quality"],
                "material_mode": frozen["material_mode"],
                "information_hierarchy": "结论—事实—因果",
                "composition_intent": "左事实、右因果链",
                "regions": [{"region_id": "facts", "purpose": "事实"}],
                "object_relationships": ["事实指向经营断点"],
                "reading_order": ["title", "facts", "impact"],
                "image_selection_and_crop": "不使用语义图片",
                "typography_application": "标题 28pt，正文 16pt",
                "color_application": "紫色仅表达当前焦点",
                "diagram_chart_table_treatment": "原生关系线",
                "native_bitmap_routing": "全部语义对象原生",
                "editability_requirements": "文字与关系可编辑",
                "fallbacks": ["Windows 使用 Microsoft YaHei"],
                "allowed_exceptions": [],
                "acceptance_criteria": [
                    {
                        "criterion_id": "r1",
                        "level": "must-follow",
                        "expected_outcome": "事实文字原生可编辑",
                    }
                ],
            }
            for index, frozen in enumerate(slides, start=1)
        ],
    }


def prepared_visual_contracts(
    project: Path, slide_count: int = 1
) -> tuple[VisualService, int, dict[str, str]]:
    content, revision, blueprint_ref = confirmed_g0(
        project, slide_count=slide_count
    )
    visual = VisualService(content.kernel)
    brief_ref = visual.register_visual_brief(
        "visual-brief", revision, valid_visual_brief(blueprint_ref)
    )
    system_ref = visual.register_design_system(
        "visual-system",
        revision + 1,
        valid_design_system(brief_ref, blueprint_ref),
    )
    blueprint = content.kernel.artifacts.resolve(
        ArtifactReference.parse(blueprint_ref)
    )["payload"]
    contracts = valid_contract_set(system_ref, blueprint_ref, blueprint["slides"])
    contract_ref = visual.register_visual_contract_set(
        "visual-contracts", revision + 2, contracts
    )
    return visual, revision + 3, {
        "blueprint": blueprint_ref,
        "brief": brief_ref,
        "system": system_ref,
        "contracts": contract_ref,
    }


def passing_visual_review(
    target_ref: str,
    *,
    stage: str = "G1",
    reviewer_kind: str = "aesthetic",
    reviewer_role: str = "independent-aesthetic-reviewer",
) -> dict:
    return {
        "stage": stage,
        "target_ref": target_ref,
        "reviewer_kind": reviewer_kind,
        "reviewer_role": reviewer_role,
        "producer_role": "visual-art-director",
        "checks": [
            {
                "criterion_id": "visual-hard",
                "level": "minimum-aesthetic",
                "applicability": "applicable",
                "result": "passed",
                "evidence_refs": [target_ref],
            }
        ],
        "overall_result": "passed",
    }


def prepared_g1_anchor(
    project: Path, slide_count: int = 3
) -> tuple[VisualService, int, dict[str, object]]:
    visual, revision, refs = prepared_visual_contracts(
        project, slide_count=slide_count
    )
    visual.register_convergence(
        "g1-anchor-convergence",
        revision,
        {
            "production_route": "strict-B",
            "visual_contract_set_ref": refs["contracts"],
            "producer_role": "visual-art-director",
            "decision_summary": "锚点页覆盖关键页面家族和视觉风险",
            "convergence_status": "passed",
        },
    )
    visual.register_visual_review(
        "g1-anchor-review",
        revision + 1,
        passing_visual_review(refs["contracts"]),
    )
    g1 = visual.record_g1("g1-anchor-pass", revision + 2)
    sha256 = "d" * 64
    pptx_ref = str(
        visual.kernel.artifacts.put(
            "native-pptx",
            {"pptx_sha256": sha256, "production_route": "strict-B"},
        )
    )
    editability_ref = str(
        visual.kernel.artifacts.put(
            "editability-evidence", {"semantic_objects_editable": True}
        )
    )
    preflight_ref = str(
        visual.kernel.artifacts.put(
            "preflight-render", {"identity": "preflight-only"}
        )
    )
    slide_ids = [f"S{index:02d}" for index in range(1, slide_count + 1)]
    anchor_ref = visual.register_anchor_set(
        "g1-anchor-set",
        g1.revision,
        {
            "visual_contract_set_ref": refs["contracts"],
            "slide_ids": slide_ids,
            "selection_reason": "覆盖章节、证据和方案三类关键页面家族",
            "render_assets": [
                {
                    "slide_id": slide_id,
                    "current_asset_ref": (
                        f"review-assets/anchors/{slide_id}-current.png"
                    ),
                    "previous_asset_ref": "",
                }
                for slide_id in slide_ids
            ],
            "native_first_pptx_ref": pptx_ref,
            "pptx_sha256": sha256,
            "native_first_frozen": True,
            "editability_evidence_refs": [editability_ref],
            "preflight_render_refs": [preflight_ref],
        },
    )
    return visual, g1.revision + 1, {
        **refs,
        "anchors": anchor_ref,
        "pptx": pptx_ref,
        "pptx_sha256": sha256,
        "slide_ids": slide_ids,
    }


def rich_target_payload(
    visual: VisualService, target_id: str, refs: dict[str, object]
) -> dict:
    operating_system = "macOS" if target_id.startswith("macos") else "Windows 11"
    application = "WPS Office" if target_id.endswith("wps") else "Microsoft PowerPoint"
    target_tag = target_id.replace("-", "_")
    font_inventory_ref = str(
        visual.kernel.artifacts.put(
            "font-inventory", {"target_id": target_id, "fonts": ["Arial"]}
        )
    )
    font_plan_ref = str(
        visual.kernel.artifacts.put(
            "font-plan",
            {"target_id": target_id, "fallback": "Arial", "risks": []},
        )
    )
    reviewer_attestation_ref = str(
        visual.kernel.artifacts.put(
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
        visual.kernel.artifacts.put(
            "target-export", {"target_id": target_id, "format": "pdf"}
        )
    )
    page_image_ref = str(
        visual.kernel.artifacts.put(
            "target-page-image", {"target_id": target_id, "slide_ids": refs["slide_ids"]}
        )
    )
    slide_check_ref = str(
        visual.kernel.artifacts.put(
            "slide-check", {"target_id": target_id, "result": "passed"}
        )
    )
    capture_ref = str(
        visual.kernel.artifacts.put(
            "target-render-capture",
            {"target_id": target_id, "identity": "formal-target-render"},
        )
    )
    return {
        "stage": "G2",
        "anchor_slide_set_ref": refs["anchors"],
        "target_id": target_id,
        "evidence_identity": "formal-target-render",
        "operating_system": operating_system,
        "operating_system_version": "15.6" if operating_system == "macOS" else "24H2",
        "application": application,
        "application_version": f"{target_tag}/test-version",
        "application_check_result": "passed",
        "font_check_result": "passed",
        "font_inventory_ref": font_inventory_ref,
        "font_substitution_plan_ref": font_plan_ref,
        "reviewer_attestation_ref": reviewer_attestation_ref,
        "source_pptx_ref": refs["pptx"],
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
                "evidence_refs": [slide_check_ref],
            }
            for slide_id in refs["slide_ids"]
        ],
        "executor": "desktop-qa-operator",
        "exported_at": "2026-08-09T12:00:00+08:00",
        "tool_version": "target-capture/1.0",
        "overall_result": "passed",
        "evidence_ref": capture_ref,
    }


def prepared_g2(
    project: Path, slide_count: int = 3
) -> tuple[VisualService, int, dict[str, object]]:
    visual, revision, refs = prepared_g1_anchor(project, slide_count=slide_count)
    visual.register_visual_review(
        "g2-aesthetic-review",
        revision,
        passing_visual_review(
            refs["anchors"], stage="G2", reviewer_kind="aesthetic"
        ),
    )
    visual.register_visual_review(
        "g2-engineering-review",
        revision + 1,
        passing_visual_review(
            refs["anchors"],
            stage="G2",
            reviewer_kind="engineering",
            reviewer_role="independent-ppt-engineering-reviewer",
        ),
    )
    current_revision = revision + 2
    target_refs: dict[str, str] = {}
    _policy_ref, policy = ReleaseTargetPolicyService(visual.kernel).current()
    for target_id in policy.required_target_ids:
        target_refs[target_id] = visual.register_target_render_evidence(
            f"g2-target-{target_id}",
            current_revision,
            rich_target_payload(visual, target_id, refs),
        )
        current_revision += 1
    state = visual.record_g2("g2-pass", current_revision)
    return visual, state.revision, {**refs, "target_evidence": target_refs}
