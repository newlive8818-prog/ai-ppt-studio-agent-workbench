"""Compact schema 3.0 projection for the five stable cognition spaces."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy


SPACE_LABELS = {
    "overview": "项目总览",
    "materials": "材料工作台",
    "blueprint": "内容蓝图",
    "visual": "视觉设计",
    "delivery": "制作与交付",
}


def _action(
    kind: str,
    label: str = "",
    *,
    enabled: bool = False,
) -> dict[str, Any]:
    return {"kind": kind, "label": label, "enabled": enabled}


class WorkspaceProjectionService:
    """Derive display-ready summaries without copying domain or Gate rules."""

    SPACE_IDS = tuple(SPACE_LABELS)

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def project(self) -> dict[str, Any]:
        state = self.kernel.load()
        mission = self._payload(state, "mission/draft", "mission-draft")
        identity = MissionReadinessPolicy(self.kernel).projection()
        materials = self._payload(state, "materials", "material-inventory")
        blueprint = self._payload(
            state, "content/blueprint", "content-blueprint"
        )
        acceptance = self._payload(
            state, "content/acceptance", "content-acceptance"
        )
        visual_contract = self._payload(
            state, "visual/contract", "visual-contract"
        )
        delivery = DeliveryService(self.kernel).delivery_status_projection()
        active_space = self._active_space(state)
        spaces = {
            "overview": self._overview(
                state, mission, identity, materials
            ),
            "materials": self._materials(state, materials),
            "blueprint": self._blueprint(
                state, blueprint=blueprint, acceptance=acceptance
            ),
            "visual": self._visual(state, visual_contract),
            "delivery": self._delivery(state, delivery),
        }
        return {
            "active_space": active_space,
            "navigation": [
                {
                    "space_id": space_id,
                    "label": SPACE_LABELS[space_id],
                    "status": spaces[space_id]["status"],
                    "high_impact_count": spaces[space_id][
                        "high_impact_count"
                    ],
                }
                for space_id in self.SPACE_IDS
            ],
            **spaces,
        }

    def project_name(self) -> str:
        state = self.kernel.load()
        manifest = self._payload(
            state, "project/manifest", "project-manifest"
        )
        mission = self._payload(state, "mission/draft", "mission-draft")
        return str(
            mission.get("topic")
            or manifest.get("name")
            or state.project_id
        )

    def _active_space(self, state: KernelState) -> str:
        if "mission/draft" not in state.artifact_heads:
            return "overview"
        identity = MissionReadinessPolicy(self.kernel).projection()
        if identity["content_identity_mode"] == "blocked":
            return "overview"
        if state.gate_status.get("G0") != "passed":
            return "blueprint"
        if state.gate_status.get("G3") != "passed":
            return "visual"
        return "delivery"

    def _overview(
        self,
        state: KernelState,
        mission: dict[str, Any],
        identity: dict[str, str],
        materials: dict[str, Any],
    ) -> dict[str, Any]:
        topic = str(mission.get("topic") or "尚未建立汇报任务")
        audience = str(
            mission.get("primary_audience") or "主要听众尚未确认"
        )
        desired = str(
            mission.get("desired_judgment_or_action")
            or "期望判断或行动尚未确认"
        )
        draft_ready = mission.get("status") == "confirmable"
        confirmed = identity["content_identity_mode"] != "blocked"
        ready = draft_ready and confirmed
        focus = self._gate_focus(state)
        source_rows = materials.get("sources")
        sources = source_rows if isinstance(source_rows, list) else []
        inventory_ref = state.artifact_heads.get("materials", "")
        return {
            "status": "ready" if ready else "needs-input",
            "conclusion": (
                f"围绕“{topic}”促成“{desired}”。"
                if ready
                else (
                    "任务字段已齐全，等待用户显式确认。"
                    if draft_ready
                    else "需要先建立汇报对象、主题和期望判断。"
                )
            ),
            "focus": focus,
            "risk": (
                "暂无任务确认级阻断，后续风险以当前质量门为准。"
                if ready
                else (
                    "任务卡未获得真实用户确认，不能开始正式内容生产。"
                    if draft_ready
                    else "任务卡最低信息不完整，不能形成正式交付目标。"
                )
            ),
            "affected_artifacts": self._refs(
                state, "mission/draft", "mission/confirmation"
            ),
            "high_impact_count": 0 if ready else 1,
            "primary_action": _action(
                "confirm-mission" if draft_ready and not confirmed else "continue-chat",
                (
                    "确认任务并开始内容策划"
                    if draft_ready and not confirmed
                    else ("继续与 Codex 对话" if ready else "建立汇报任务")
                ),
                enabled=True,
            ),
            "delivery_goal": desired,
            "audiences": [audience] if audience else [],
            "topic": topic,
            "mission_status": str(mission.get("status") or "draft"),
            "mission_draft_ref": identity["mission_draft_ref"],
            "mission_confirmation_ref": identity[
                "mission_confirmation_ref"
            ],
            "material_mode": identity["material_mode"],
            "content_identity_mode": identity["content_identity_mode"],
            "mission_card": {
                "topic": str(mission.get("topic") or ""),
                "primary_audience": str(
                    mission.get("primary_audience") or ""
                ),
                "desired_judgment_or_action": str(
                    mission.get("desired_judgment_or_action") or ""
                ),
                "material_state": (
                    "materials-provided" if sources else "no-materials"
                ),
                "material_inventory_ref": inventory_ref,
                "materials": [
                    str(
                        item.get("label")
                        or item.get("source_id")
                        or item.get("locator")
                        or "用户提供材料"
                    )
                    for item in sources
                    if isinstance(item, dict)
                ],
                "background": self._string_list(
                    mission.get("background")
                ),
                "constraints": self._string_list(
                    mission.get("constraints")
                ),
                "red_lines": self._string_list(
                    mission.get("red_lines") or mission.get("redLines")
                ),
                "unknowns": self._string_list(
                    mission.get("open_questions")
                    or mission.get("openQuestions")
                    or mission.get("unknowns")
                ),
            },
        }

    def _materials(
        self, state: KernelState, materials: dict[str, Any]
    ) -> dict[str, Any]:
        sources = materials.get("sources")
        source_rows = sources if isinstance(sources, list) else []
        source_count = len(source_rows)
        ready = source_count > 0
        return {
            "status": "ready" if ready else "needs-input",
            "conclusion": (
                f"已接收 {source_count} 份用户提供且可追溯的材料。"
                if ready
                else "尚未收到可用于本项目的材料。"
            ),
            "focus": (
                "材料将按当前任务自动分类并提炼。"
                if ready
                else "通过 Codex 聊天补充文件、目录、文字、图片或链接。"
            ),
            "risk": (
                "当前投影不替代来源冲突和关键证据缺口的专业诊断。"
                if ready
                else "缺少真实项目材料，内容阶段不能形成可追溯事实。"
            ),
            "affected_artifacts": self._refs(state, "materials"),
            "high_impact_count": 0 if ready else 1,
            "primary_action": _action(
                "continue-chat",
                "查看 AI 提炼结果" if ready else "继续补充材料",
                enabled=True,
            ),
            "source_count": source_count,
            "parsed_count": source_count,
            "failed_count": 0,
            "authorization_count": 0,
            "external_search": False,
        }

    def _blueprint(
        self,
        state: KernelState,
        *,
        blueprint: dict[str, Any],
        acceptance: dict[str, Any],
    ) -> dict[str, Any]:
        blueprint_ref = state.artifact_heads.get("content/blueprint", "")
        slides = blueprint.get("slides")
        slide_rows = slides if isinstance(slides, list) else []
        internal_result = str(acceptance.get("overall_result") or "pending")
        review_available = bool(
            blueprint_ref
            and internal_result == "passed"
            and state.gate_status.get("G0") in {"user-reviewable", "passed"}
        )
        strategy = blueprint.get("strategy")
        strategy_row = strategy if isinstance(strategy, dict) else {}
        thesis = str(
            strategy_row.get("persuasion_proposition")
            or strategy_row.get("core_tension")
            or (
                "逐页内容、讲解稿和来源已形成。"
                if slide_rows
                else "AI 正在形成售前策略、证据、论证和逐页内容。"
            )
        )
        mark_count = self._mark_count(state, "content", blueprint_ref)
        status = str(state.gate_status.get("G0") or "locked")
        return {
            "status": status,
            "conclusion": (
                "内容蓝图已通过内部审查，可集中阅读整套论证。"
                if review_available
                else "内容仍在内部生产或审查，失败稿不会进入用户审阅。"
            ),
            "focus": thesis,
            "risk": (
                "完成专业审阅和标记保存后，在聊天中确认或修改 G0。"
                if review_available and status != "passed"
                else "当前没有需要用户处理的内容审阅动作。"
            ),
            "affected_artifacts": self._refs(
                state, "content/blueprint", "content/acceptance"
            ),
            "high_impact_count": 0,
            "primary_action": (
                _action(
                    "open-content-review", "打开内容审阅", enabled=True
                )
                if review_available
                else _action("none")
            ),
            "phase": status,
            "internal_status": internal_result,
            "slide_count": len(slide_rows),
            "saved_mark_count": mark_count,
            "review_available": review_available,
            "source_version": blueprint_ref,
        }

    def _visual(
        self, state: KernelState, visual_contract: dict[str, Any]
    ) -> dict[str, Any]:
        contract_ref = state.artifact_heads.get("visual/contract", "")
        g1 = str(state.gate_status.get("G1") or "locked")
        g2 = str(state.gate_status.get("G2") or "locked")
        g3 = str(state.gate_status.get("G3") or "locked")
        review_available = bool(
            contract_ref
            and g1 == "passed"
            and g2 == "passed"
            and g3 in {"user-reviewable", "passed"}
        )
        design_system = visual_contract.get("deck_design_system")
        design_system_row = (
            design_system if isinstance(design_system, dict) else {}
        )
        theme = str(
            design_system_row.get("theme_proposition")
            or "整套视觉命题与页面合同仍在内部收敛。"
        )
        return {
            "status": g3 if g3 != "locked" else g2,
            "conclusion": (
                "整套视觉合同和锚点页已通过 G1 / G2 内部门。"
                if review_available
                else "AI 正在收敛整套视觉合同和严格路线 B 锚点证据。"
            ),
            "focus": theme,
            "risk": (
                "完成合同审阅和标记保存后，在聊天中确认或修改 G3。"
                if review_available and g3 != "passed"
                else "任一内部硬门或四目标证据不完整时不会开放确认。"
            ),
            "affected_artifacts": self._refs(
                state,
                "visual/contract",
                "visual/design-system",
                "visual/anchors",
            ),
            "high_impact_count": 0,
            "primary_action": (
                _action(
                    "open-visual-review", "打开视觉合同", enabled=True
                )
                if review_available
                else _action("none")
            ),
            "g1_status": g1,
            "g2_status": g2,
            "g3_status": g3,
            "saved_mark_count": self._mark_count(
                state, "visual", contract_ref
            ),
            "review_available": review_available,
            "source_version": contract_ref,
            "production_route": str(
                visual_contract.get("production_route") or "strict-B"
            ),
        }

    def _delivery(
        self, state: KernelState, delivery: dict[str, Any]
    ) -> dict[str, Any]:
        blocker = delivery.get("highest_blocker")
        phase = str(delivery.get("phase") or "locked")
        completed = int(delivery.get("slides", {}).get("completed") or 0)
        total = int(delivery.get("slides", {}).get("total") or 0)
        chat_status = str(delivery.get("chat_send", {}).get("status") or "pending")
        return {
            "status": phase,
            "conclusion": (
                f"已完成 {completed}/{total} 页制作与逐页质量检查。"
                if total
                else "整套 PPTX 尚未进入正式构建。"
            ),
            "focus": (
                "最终 PPTX 已发送到聊天，等待用户明确接受或修改。"
                if chat_status == "sent"
                else "系统继续完成构建、四门和四目标同哈希证据。"
            ),
            "risk": str(blocker or "当前没有内部阻断项。"),
            "affected_artifacts": self._refs(
                state,
                "delivery/build",
                "delivery/qa/deck",
                "delivery/package",
                "chat-delivery/pptx",
            ),
            "high_impact_count": 1 if blocker else 0,
            "primary_action": _action("none"),
            **delivery,
        }

    def _mark_count(
        self, state: KernelState, review_type: str, source_version: str
    ) -> int:
        if not source_version:
            return 0
        payload = self._payload(
            state, f"review-marks/{review_type}", "review-mark-set"
        )
        if payload.get("source_version") != source_version:
            return 0
        marks = payload.get("marks")
        return len(marks) if isinstance(marks, list) else 0

    def _payload(
        self, state: KernelState, slot: str, expected_kind: str
    ) -> dict[str, Any]:
        value = state.artifact_heads.get(slot, "")
        if not value:
            return {}
        reference = ArtifactReference.parse(value)
        if reference.kind != expected_kind:
            return {}
        payload = self.kernel.artifacts.resolve(reference).get("payload")
        return dict(payload) if isinstance(payload, dict) else {}

    @staticmethod
    def _refs(state: KernelState, *slots: str) -> list[str]:
        return [
            state.artifact_heads[slot]
            for slot in slots
            if state.artifact_heads.get(slot)
        ]

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            clean = value.strip()
            return [clean] if clean else []
        if not isinstance(value, list):
            return []
        return [
            clean
            for item in value
            if (clean := str(item).strip())
        ]

    @staticmethod
    def _gate_focus(state: KernelState) -> str:
        for gate in ("G0", "G1", "G2", "G3", "G4"):
            status = str(state.gate_status.get(gate) or "locked")
            if status not in {"locked", "passed"}:
                return f"当前焦点：{gate} · {status}"
        return "当前焦点：全部质量门已完成"


__all__ = ["SPACE_LABELS", "WorkspaceProjectionService"]
