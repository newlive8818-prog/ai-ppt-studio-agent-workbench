from __future__ import annotations

from typing import Any


DEFAULT_MATERIAL_REF = "artifact://material-inventory/" + "a" * 64


def complete_material_evidence(
    material_ref: str = DEFAULT_MATERIAL_REF,
) -> dict[str, str]:
    return {
        "evidence_id": "E-MAT-01",
        "evidence_kind": "material",
        "material_ref": material_ref,
        "asset_ref": "asset://customer-system-landscape/page-03.png",
        "source_file": "客户现状调研材料.pptx",
        "source_page_or_region": "P03 · 系统现状全页",
        "used_region": "五个业务系统与三处手工交接区域",
        "supports_claim": "跨系统交接正在割裂经营主线",
        "treatment": "crop",
        "fact_identity": "customer-provided-material",
        "evidence_gap": "调研材料可证明流程断点，但尚不支撑定量收益主张。",
    }


def complete_planned_gap_evidence() -> dict[str, str]:
    return {
        "evidence_id": "E-GAP-01",
        "evidence_kind": "planned-gap",
        "material_ref": "",
        "asset_ref": "",
        "source_file": "待补",
        "source_page_or_region": "待补",
        "used_region": "待补客户现状证据",
        "supports_claim": "客户当前流程确有重复录入",
        "treatment": "to-supply",
        "fact_identity": "joint-validation-required",
        "evidence_gap": "G0 前需补材料，或将主张降级为诊断假设。",
    }


def complete_proposal_only_slide(
    *, slide_id: str = "s1", order: int = 1
) -> dict[str, Any]:
    planned_gap = complete_planned_gap_evidence()
    planned_gap.update(
        {
            "used_region": "待补联合澄清的现状证据",
            "supports_claim": "诊断假设：流程可能存在重复录入",
            "evidence_gap": "需补材料，或将主张降级为诊断假设。",
        }
    )
    slide = complete_reading_first_slide(
        slide_id=slide_id,
        order=order,
        evidence_items=[planned_gap],
        source_refs=[],
    )
    slide.update(
        {
            "title": "联合验证的起点",
            "page_purpose": "方案建议：明确当前是联合澄清阶段。",
            "customer_judgment": "待联合验证：先补充现状依据，再冻结建设范围。",
            "communication_goal": "明确当前内容身份",
            "core_claim": "诊断假设：跨系统协同可能存在断点",
            "identity_class": "diagnostic-hypothesis",
            "visible_copy": [
                {
                    "copy_id": "COPY-GAP-01",
                    "role": "body",
                    "text": "诊断假设：流程断点需联合澄清。",
                },
                {
                    "copy_id": "COPY-GAP-02",
                    "role": "boundary",
                    "text": "当前内容不代表已确认事实。",
                },
            ],
            "speaker_notes": "方案建议：先共同验证现状，再冻结建设范围。",
            "user_judgment_prompt": "待联合验证：请判断是否先补充现状证据。",
        }
    )
    return slide


def complete_proposal_only_draft_payload(
    *, argument_map_ref: str = "artifact://deck-argument-map/" + "b" * 64
) -> dict[str, Any]:
    return {
        "argument_map_ref": argument_map_ref,
        "content_identity_mode": "proposal-only",
        "identity_labels": [
            "diagnostic-hypothesis",
            "solution-recommendation",
            "joint-validation-required",
        ],
        "slides": [complete_proposal_only_slide()],
    }


def complete_reading_first_slide(
    *,
    order: int = 1,
    slide_id: str | None = None,
    chapter_id: str = "C01",
    material_ref: str = DEFAULT_MATERIAL_REF,
    evidence_items: list[dict[str, str]] | None = None,
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    resolved_slide_id = slide_id or f"S{order:02d}"
    return {
        "slide_id": resolved_slide_id,
        "chapter_id": chapter_id,
        "order": order,
        "title": "跨系统断点正在阻碍经营决策闭环",
        "page_purpose": "把分散的系统现象转成客户可判断的经营问题。",
        "customer_judgment": "当前问题需要跨系统治理，不是单点界面优化。",
        "communication_goal": "建立一期治理范围的问题共识。",
        "core_claim": "跨系统交接断点使经营信息无法及时闭环。",
        "visible_copy": [
            {
                "copy_id": "COPY-01",
                "role": "headline",
                "text": "跨系统断点正在阻碍经营决策闭环",
            },
            {
                "copy_id": "COPY-02",
                "role": "body",
                "text": "五套系统各自记录局部进展，三条断点仍需手工交接与重复核对。",
            },
            {
                "copy_id": "COPY-03",
                "role": "source-note",
                "text": "来源：客户现状调研材料 P03；定量收益待联合验证。",
            },
        ],
        "evidence_items": evidence_items
        if evidence_items is not None
        else [complete_material_evidence(material_ref)],
        "speaker_notes": "解释来源和边界：材料支持存在跨系统交接断点，但不把未经验证的收益数字当作客户事实。",
        "reading_quality": {
            "independently_readable": True,
            "information_density": "moderate",
            "claim_reason_evidence_boundary_complete": True,
            "review_note": "去掉逐字稿后仍能理解主张、证据边界和客户判断。",
        },
        "sequence": {
            "previous_slide_id": "",
            "next_slide_id": "S02",
            "transition_from_previous": "从封面的决策目标进入当前经营断点。",
            "transition_to_next": "在问题共识上进一步定义一期建设原则。",
        },
        "user_judgment_prompt": "请判断：这一页是否足以说明问题是跨系统治理，而不是单点优化？",
        "source_refs": source_refs if source_refs is not None else [material_ref],
    }


def complete_slide_draft_payload(
    *,
    argument_map_ref: str = "artifact://deck-argument-map/" + "b" * 64,
    material_ref: str = DEFAULT_MATERIAL_REF,
    slide_count: int = 1,
    slide_id_prefix: str = "S",
) -> dict[str, Any]:
    slides = [
        complete_reading_first_slide(
            order=index,
            slide_id=(
                f"{slide_id_prefix}{index:02d}"
                if slide_id_prefix == "S"
                else f"{slide_id_prefix}{index}"
            ),
            material_ref=material_ref,
        )
        for index in range(1, slide_count + 1)
    ]
    for index, slide in enumerate(slides):
        slide["sequence"]["previous_slide_id"] = (
            slides[index - 1]["slide_id"] if index > 0 else ""
        )
        slide["sequence"]["next_slide_id"] = (
            slides[index + 1]["slide_id"] if index + 1 < len(slides) else ""
        )
        slide["title"] = (
            "为什么现在必须改变"
            if index == 0
            else f"方案论证页 {index + 1}"
        )
        slide["core_claim"] = (
            "割裂阻碍经营"
            if index == 0
            else f"核心主张 {index + 1}"
        )
        slide["communication_goal"] = (
            "建立紧迫性"
            if index == 0
            else "建立方案信心"
        )
        slide["speaker_notes"] = (
            "解释来源"
            if index == 0
            else f"讲解备注 {index + 1}"
        )
        slide["visible_copy"] = (
            [
                {
                    "copy_id": "COPY-01",
                    "role": "headline",
                    "text": "五套系统",
                },
                {
                    "copy_id": "COPY-02",
                    "role": "五套系统",
                    "text": "三条断点",
                },
            ]
            if index == 0
            else [
                {
                    "copy_id": f"COPY-{index + 1:02d}",
                    "role": "body",
                    "text": f"方案要点 {index + 1}",
                }
            ]
        )
    return {"argument_map_ref": argument_map_ref, "slides": slides}
