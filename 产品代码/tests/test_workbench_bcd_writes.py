from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.errors import GateBlockedError, RevisionConflictError
from ai_ppt_studio.models import ArtifactKind, Gate
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.state_store import StateStore
from ai_ppt_studio.workbench_store import WorkbenchStore


def make_store(base: Path) -> WorkbenchStore:
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    policy = PathPolicy(config)
    manifest = ProjectStore(config, policy).create("BCD 写入测试")
    project = Path(manifest.project_root)
    StateStore(project, policy).initialize()
    return WorkbenchStore(project, policy)


def slide(source_ref: str) -> dict[str, object]:
    return {
        "slide_id": "S01",
        "title": "为什么现在必须建设",
        "purpose": "建立紧迫性",
        "claim": "分散系统阻碍运营协同",
        "visible_content": ["系统分散"],
        "speaker_notes": "引用客户会议纪要",
        "source_refs": [source_ref],
        "material_refs": [Path(source_ref).stem],
    }


class WorkbenchBcdWriteTests(unittest.TestCase):
    def test_material_and_agent_request_each_increment_once_and_conflict_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = make_store(Path(temp))
            initial = store.ensure()
            added = store.add_material(
                expected_revision=initial.revision,
                material_type="text",
                value="客户需要在九月完成一期上线",
                label="会议纪要",
            )
            self.assertEqual(added.snapshot.revision, 1)
            self.assertEqual(added.snapshot.space_projections["materials"]["source_count"], 1)
            source_files = list((store.project_root / "sources").glob("*.json"))
            events_before = (store.project_root / "events" / "events.jsonl").read_text("utf-8")

            with self.assertRaises(RevisionConflictError):
                store.request_agent_action(
                    expected_revision=initial.revision,
                    action_type="classify-materials",
                    target_refs=["project://sources"],
                    instructions="自动提炼材料",
                )
            self.assertEqual(list((store.project_root / "sources").glob("*.json")), source_files)
            self.assertEqual((store.project_root / "events" / "events.jsonl").read_text("utf-8"), events_before)

            requested = store.request_agent_action(
                expected_revision=added.snapshot.revision,
                action_type="classify-materials",
                target_refs=["project://sources"],
                instructions="自动提炼材料",
            )
            self.assertEqual(requested.snapshot.revision, 2)
            self.assertEqual(requested.decision["status"], "requested")
            self.assertIn("classify-materials", requested.follow_up_message)
            self.assertTrue((store.project_root / requested.model_context["context_ref"]).is_file())

    def test_commit_artifact_completes_matching_task_and_refreshes_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = make_store(Path(temp))
            first = store.ensure()
            requested = store.request_agent_action(
                expected_revision=first.revision,
                action_type="generate-blueprint",
                target_refs=["artifact://content-blueprint"],
                instructions="根据材料形成内容蓝图",
            )
            task_id = requested.decision["task_id"]
            source_ref = "sources/source-1.json"
            committed = store.commit_artifact(
                expected_revision=requested.snapshot.revision,
                kind=ArtifactKind.CONTENT_BLUEPRINT,
                payload={
                    "title": "智慧园区方案",
                    "audience": "园区领导",
                    "goal": "确认一期建设",
                    "slides": [slide(source_ref)],
                },
                task_id=task_id,
            )
            self.assertEqual(committed.snapshot.revision, 2)
            self.assertEqual(committed.snapshot.space_projections["blueprint"]["slide_count"], 1)
            result = json.loads(
                (store.project_root / "tasks" / f"{task_id}.result.json").read_text("utf-8")
            )
            self.assertEqual(result["result_revision"], 2)
            self.assertEqual(result["status"], "completed")

    def test_gates_require_project_evidence_and_advance_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = make_store(Path(temp))
            current = store.ensure()
            with self.assertRaises(GateBlockedError) as blocked:
                store.confirm_gate(expected_revision=current.revision, gate=Gate.G0)
            self.assertIn("mission", blocked.exception.missing_evidence)
            self.assertEqual(store.ensure().revision, current.revision)

            source_result = store.add_material(
                expected_revision=current.revision,
                material_type="text",
                value="客户现状",
                label="现状",
            )
            source_ref = source_result.decision["source_refs"][0]
            current = source_result.snapshot
            for kind, payload in (
                (
                    ArtifactKind.MISSION,
                    {"title": "方案", "audience": "领导", "goal": "立项", "context": "售前"},
                ),
                (
                    ArtifactKind.CONTENT_BLUEPRINT,
                    {"title": "方案", "audience": "领导", "goal": "立项", "slides": [slide(source_ref)]},
                ),
            ):
                current = store.commit_artifact(
                    expected_revision=current.revision, kind=kind, payload=payload
                ).snapshot
            current = store.confirm_gate(expected_revision=current.revision, gate=Gate.G0).snapshot
            self.assertEqual(current.gate_state["gates"]["G1"], "open")

            current = store.commit_artifact(
                expected_revision=current.revision,
                kind=ArtifactKind.CONCEPT_SET,
                payload={"directions": [{"id": "A"}, {"id": "B"}]},
            ).snapshot
            with self.assertRaises(GateBlockedError):
                store.confirm_gate(expected_revision=current.revision, gate=Gate.G1)
            current = store.submit_decision(
                expected_revision=current.revision,
                target_ref="concept://direction",
                choice="A",
                feedback="采用方向 A",
            ).snapshot
            current = store.confirm_gate(expected_revision=current.revision, gate=Gate.G1).snapshot

            render = store.project_root / "renders" / "engineering.png"
            render.write_bytes(b"render")
            current = store.commit_artifact(
                expected_revision=current.revision,
                kind=ArtifactKind.ENGINEERING_SAMPLES,
                payload={
                    "summary": "已形成工程样张",
                    "samples": [{"sample_id": "E01", "slide_refs": ["S01"], "render_ref": "renders/engineering.png", "native_element_ratio": 0.9, "editable": True, "notes": "原生可编辑"}],
                    "native_coverage": {"text": True, "shape": True, "whole_slide_bitmap": False},
                    "qa_status": "passed",
                },
            ).snapshot
            current = store.confirm_gate(expected_revision=current.revision, gate=Gate.G2).snapshot

            current = store.commit_artifact(
                expected_revision=current.revision,
                kind=ArtifactKind.VISUAL_CONTRACT,
                payload={"design_thesis": "证据优先", "palette": {"ink": "#111827"}, "typography": {"chinese": "PingFang SC"}, "layout_rules": ["一页一主张"], "image_language": ["真实证据"], "editability_rules": ["禁止整页位图"]},
            ).snapshot
            current = store.commit_artifact(
                expected_revision=current.revision,
                kind=ArtifactKind.SLIDE_SCENE_GRAPH,
                payload={"slides": [{"slide_id": "S01", "width": 13.333, "height": 7.5, "elements": []}]},
            ).snapshot
            current = store.confirm_gate(expected_revision=current.revision, gate=Gate.G3).snapshot

            pptx = store.project_root / "ppt" / "deck.pptx"
            pptx.write_bytes(b"pptx")
            final_render = store.project_root / "renders" / "slide-1.png"
            final_render.write_bytes(b"render")
            current = store.commit_artifact(
                expected_revision=current.revision,
                kind=ArtifactKind.PRESENTATION_HANDOFF,
                payload={"content_blueprint_ref": "blueprint/content-blueprint/v0001.json", "visual_contract_ref": "visual/visual-contract/v0001.json", "scene_graph_ref": "scene-graph/slide-scene-graph/v0001.json", "output_pptx": "ppt/deck.pptx", "render_directory": "renders", "source_notes_ref": "reviews/sources.json", "editability_contract": {"native_business_content": True, "whole_slide_bitmap": False}},
            ).snapshot
            current = store.commit_artifact(
                expected_revision=current.revision,
                kind=ArtifactKind.DELIVERY,
                payload={"pptx": "ppt/deck.pptx", "renders": ["renders/slide-1.png"], "qa_status": "passed", "sources": [source_ref], "editable": True},
            ).snapshot
            current = store.confirm_gate(expected_revision=current.revision, gate=Gate.G4).snapshot
            self.assertEqual(current.gate_state["gates"]["G4"], "passed")

            reopened = store.reopen_scope(
                expected_revision=current.revision,
                gate=Gate.G1,
                reason="听众偏好变化，需要重新选择方向",
            )
            self.assertEqual(reopened.snapshot.revision, current.revision + 1)
            self.assertEqual(reopened.snapshot.gate_state["gates"]["G1"], "open")
            self.assertEqual(reopened.snapshot.gate_state["gates"]["G4"], "locked")
            self.assertTrue((store.project_root / "visual" / "concept-set" / "v0001.json").is_file())


if __name__ == "__main__":
    unittest.main()
