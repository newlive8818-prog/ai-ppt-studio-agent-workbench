"""Sanitized per-space projections for the Agent-native Widget."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_tasks import AgentTaskStore
from .artifact_store import ArtifactStore
from .errors import ProjectNotFoundError
from .models import ArtifactKind
from .paths import PathPolicy, is_within
from .state_store import StateStore


class SpaceProjectionBuilder:
    """Build decision-friendly summaries from authoritative project files."""

    def __init__(self, project_root: Path, policy: PathPolicy) -> None:
        self.project_root = policy.assert_write_allowed(project_root)
        self.policy = policy
        self.artifacts = ArtifactStore(self.project_root, policy)

    def build(self) -> dict[str, Any]:
        active_task = AgentTaskStore(self.project_root, self.policy).active()
        return {
            "materials": self._materials(active_task),
            "blueprint": self._blueprint(active_task),
            "visual": self._visual(active_task),
            "delivery": self._delivery(active_task),
        }

    def _materials(self, active_task: dict[str, Any] | None) -> dict[str, Any]:
        findings = self._payload(ArtifactKind.MATERIAL_FINDINGS)
        assignments = {
            str(item.get("source_id")): item
            for item in (findings or {}).get("source_assignments", [])
            if isinstance(item, dict)
        }
        rows = []
        for path in sorted((self.project_root / "sources").glob("*.json")):
            try:
                item = json.loads(path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            source_id = str(item.get("source_id", path.stem))
            assignment = assignments.get(source_id, {})
            original = str(item.get("original_ref", ""))
            rows.append(
                {
                    "source_id": source_id,
                    "source_ref": f"sources/{path.name}",
                    "name": self._source_name(original, source_id),
                    "kind": str(item.get("kind", "unknown")),
                    "mode": str(item.get("mode", "reference")),
                    "size_bytes": item.get("size_bytes"),
                    "classification": self._text(assignment.get("summary"), 160)
                    or "等待 AI 提炼",
                    "purposes": self._string_list(assignment.get("purposes"), 8),
                    "status": str(assignment.get("status", "awaiting-ai")),
                }
            )
        return {
            "status": "classified" if findings else ("awaiting-ai" if rows else "empty"),
            "source_count": len(rows),
            "sources": rows,
            "summary": self._text((findings or {}).get("summary"), 400)
            or (f"已接收 {len(rows)} 份材料，等待 AI 自动提炼" if rows else "尚未添加材料"),
            "findings": self._bounded_findings((findings or {}).get("findings")),
            "conflicts": self._string_list((findings or {}).get("conflicts"), 12),
            "gaps": self._string_list((findings or {}).get("gaps"), 12),
            "active_task": self._task_for(active_task, {"classify-materials"}),
        }

    def _blueprint(self, active_task: dict[str, Any] | None) -> dict[str, Any]:
        mission = self._payload(ArtifactKind.MISSION) or {}
        blueprint = self._payload(ArtifactKind.CONTENT_BLUEPRINT) or {}
        slides = []
        referenced: set[str] = set()
        for item in blueprint.get("slides", []):
            if not isinstance(item, dict):
                continue
            source_refs = self._string_list(item.get("source_refs"), 20)
            referenced.update(source_refs)
            slides.append(
                {
                    "slide_id": self._text(item.get("slide_id"), 80),
                    "title": self._text(item.get("title"), 180),
                    "role": self._text(item.get("role"), 120),
                    "purpose": self._text(item.get("purpose"), 260),
                    "claim": self._text(item.get("claim"), 320),
                    "visible_content": self._string_list(item.get("visible_content"), 12),
                    "speaker_notes": self._text(item.get("speaker_notes"), 600),
                    "source_refs": source_refs,
                    "material_refs": self._string_list(item.get("material_refs"), 20),
                    "fact_status": self._text(item.get("fact_status"), 160),
                }
            )
        source_count = len(list((self.project_root / "sources").glob("*.json")))
        return {
            "status": "ready" if slides else ("mission-only" if mission else "empty"),
            "title": self._text(blueprint.get("title") or mission.get("title"), 180),
            "audience": self._text(blueprint.get("audience") or mission.get("audience"), 240),
            "goal": self._text(blueprint.get("goal") or mission.get("goal"), 300),
            "context": self._text(mission.get("context"), 400),
            "narrative_thesis": self._text(
                blueprint.get("narrative_thesis") or mission.get("decision_start"), 500
            ),
            "chapters": self._chapters(blueprint.get("chapters")),
            "slides": slides,
            "slide_count": len(slides),
            "source_coverage": {
                "available": source_count,
                "referenced": len(referenced),
                "unreferenced": max(source_count - len(referenced), 0),
            },
            "active_task": self._task_for(
                active_task, {"generate-blueprint", "revise-blueprint"}
            ),
        }

    def _visual(self, active_task: dict[str, Any] | None) -> dict[str, Any]:
        brief = self._payload(ArtifactKind.VISUAL_BRIEF) or {}
        concepts = self._payload(ArtifactKind.CONCEPT_SET) or {}
        engineering = self._payload(ArtifactKind.ENGINEERING_SAMPLES) or {}
        contract = self._payload(ArtifactKind.VISUAL_CONTRACT) or {}
        scene = self._payload(ArtifactKind.SLIDE_SCENE_GRAPH) or {}
        directions = []
        for item in concepts.get("directions", []):
            if not isinstance(item, dict):
                continue
            sample_ref = self._project_ref(item.get("sample_image"))
            directions.append(
                {
                    "id": self._text(item.get("id"), 80),
                    "name": self._text(item.get("name"), 120),
                    "thesis": self._text(item.get("thesis"), 320),
                    "composition": self._text(item.get("composition"), 320),
                    "density": self._text(item.get("density"), 160),
                    "image_language": self._text(item.get("image_language"), 320),
                    "risk": self._text(item.get("risk"), 260),
                    "sample_asset_ref": sample_ref,
                    "sample_exists": self._asset_exists(sample_ref),
                }
            )
        samples = []
        for item in engineering.get("samples", []):
            if not isinstance(item, dict):
                continue
            render_ref = self._project_ref(item.get("render_ref"))
            samples.append(
                {
                    "sample_id": self._text(item.get("sample_id"), 80),
                    "slide_refs": self._string_list(item.get("slide_refs"), 20),
                    "render_ref": render_ref,
                    "render_exists": self._asset_exists(render_ref),
                    "native_element_ratio": item.get("native_element_ratio"),
                    "editable": bool(item.get("editable")),
                    "notes": self._text(item.get("notes"), 360),
                }
            )
        graphs = scene.get("slides") if isinstance(scene.get("slides"), list) else ([] if not scene else [scene])
        return {
            "status": "contract-ready" if contract and graphs else ("concept-ready" if directions else "empty"),
            "visual_brief": {
                "design_challenge": self._text(brief.get("design_challenge"), 420),
                "audience": self._text(brief.get("audience"), 240),
                "desired_response": self._text(brief.get("desired_response"), 320),
                "design_posture": self._text(brief.get("design_posture"), 320),
                "constraints": self._string_list(brief.get("constraints"), 16),
                "visual_prohibitions": self._string_list(brief.get("visual_prohibitions"), 16),
            },
            "directions": directions,
            "direction_count": len(directions),
            "recommended_direction": self._text(concepts.get("recommended_direction"), 80),
            "selected_direction": self._selected_direction(),
            "engineering_samples": samples,
            "engineering_summary": self._text(engineering.get("summary"), 400),
            "native_coverage": dict(engineering.get("native_coverage") or {}),
            "engineering_qa_status": self._text(engineering.get("qa_status"), 80),
            "visual_contract": self._contract_summary(contract),
            "scene_graph_coverage": len(graphs),
            "active_task": self._task_for(
                active_task,
                {"explore-concepts", "build-engineering-samples", "freeze-visual-contract"},
            ),
        }

    def _delivery(self, active_task: dict[str, Any] | None) -> dict[str, Any]:
        handoff = self._payload(ArtifactKind.PRESENTATION_HANDOFF) or {}
        delivery = self._payload(ArtifactKind.DELIVERY) or {}
        pptx_ref = self._project_ref(delivery.get("pptx") or handoff.get("output_pptx"))
        render_refs = self._string_list(delivery.get("renders"), 300)
        renders = [
            {"asset_ref": self._project_ref(ref), "exists": self._asset_exists(self._project_ref(ref))}
            for ref in render_refs
        ]
        gate = StateStore(self.project_root, self.policy).load().as_dict()
        qa_status = self._text(delivery.get("qa_status"), 80) or "not-run"
        return {
            "status": "accepted" if gate["gates"].get("G4") == "passed" else ("qa-passed" if qa_status == "passed" else ("built" if pptx_ref else "empty")),
            "gate_state": gate,
            "pptx_ref": pptx_ref,
            "pptx_exists": self._asset_exists(pptx_ref),
            "slide_count": int(delivery.get("slide_count") or handoff.get("slide_count") or len(renders)),
            "renders": renders,
            "render_count": len(renders),
            "qa_status": qa_status,
            "editable": bool(delivery.get("editable") or (handoff.get("editability_contract") or {}).get("native_business_content")),
            "whole_slide_bitmap": bool((handoff.get("editability_contract") or {}).get("whole_slide_bitmap", False)),
            "validation_ref": self._project_ref(delivery.get("validation_ref") or handoff.get("source_notes_ref")),
            "source_count": len(delivery.get("sources", [])) if isinstance(delivery.get("sources"), list) else 0,
            "active_task": self._task_for(
                active_task, {"build-pptx", "qa-render", "repair-pptx"}
            ),
        }

    def _payload(self, kind: ArtifactKind) -> dict[str, Any] | None:
        try:
            return self.artifacts.latest(kind).payload
        except ProjectNotFoundError:
            return None

    def _selected_direction(self) -> str:
        path = self.project_root / "cognition" / "decisions.jsonl"
        if not path.is_file():
            return ""
        selected = ""
        for line in path.read_text("utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(item.get("target_ref", "")).startswith("concept://"):
                selected = self._text(item.get("choice"), 80)
        return selected

    def _contract_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "design_thesis": self._text(payload.get("design_thesis"), 420),
            "palette": dict(payload.get("palette") or {}),
            "typography": dict(payload.get("typography") or {}),
            "layout_rules": self._string_list(payload.get("layout_rules"), 20),
            "image_language": self._string_list(payload.get("image_language"), 20),
            "editability_rules": self._string_list(payload.get("editability_rules"), 20),
            "page_families": self._string_list(payload.get("page_families"), 20),
        }

    def _task_for(self, active: dict[str, Any] | None, actions: set[str]) -> dict[str, Any] | None:
        if not active or active.get("action_type") not in actions:
            return None
        return {
            "task_id": active.get("task_id"),
            "action_type": active.get("action_type"),
            "status": active.get("status"),
            "updated_at": active.get("updated_at"),
        }

    def _bounded_findings(self, value: Any) -> list[dict[str, Any]]:
        result = []
        if not isinstance(value, list):
            return result
        for item in value[:80]:
            if not isinstance(item, dict):
                continue
            result.append(
                {
                    "finding_id": self._text(item.get("finding_id"), 80),
                    "finding_type": self._text(item.get("finding_type"), 80),
                    "content": self._text(item.get("content"), 500),
                    "source_ref": self._text(item.get("source_ref"), 240),
                    "locator": self._text(item.get("locator"), 180),
                    "fact_status": self._text(item.get("fact_status"), 80),
                    "purposes": self._string_list(item.get("purposes"), 12),
                }
            )
        return result

    def _chapters(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [
            {
                "title": self._text(item.get("title"), 180),
                "slide_ids": self._string_list(item.get("slide_ids"), 100),
            }
            for item in value[:40]
            if isinstance(item, dict)
        ]

    def _project_ref(self, value: Any) -> str:
        if not value:
            return ""
        path = Path(str(value))
        if not path.is_absolute():
            return path.as_posix()
        try:
            return path.resolve(strict=False).relative_to(self.project_root).as_posix()
        except ValueError:
            return ""

    def _asset_exists(self, project_ref: str | None) -> bool:
        if not project_ref:
            return False
        path = (self.project_root / project_ref).resolve(strict=False)
        return is_within(path, self.project_root) and path.is_file()

    @staticmethod
    def _source_name(original_ref: str, fallback: str) -> str:
        if original_ref.startswith("inline:"):
            return original_ref.removeprefix("inline:") or fallback
        if original_ref.startswith("upload:"):
            return original_ref.removeprefix("upload:").split(";mime=", 1)[0] or fallback
        return Path(original_ref).name or original_ref[:120] or fallback

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return str(value).strip()[:limit] if value is not None else ""

    @classmethod
    def _string_list(cls, value: Any, count: int) -> list[str]:
        if not isinstance(value, list):
            return []
        return [cls._text(item, 500) for item in value[:count] if cls._text(item, 500)]


__all__ = ["SpaceProjectionBuilder"]
