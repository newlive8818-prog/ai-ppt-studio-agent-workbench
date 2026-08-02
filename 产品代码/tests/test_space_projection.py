from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.artifact_store import ArtifactStore
from ai_ppt_studio.config import RuntimeConfig
from ai_ppt_studio.materials import MaterialIntake
from ai_ppt_studio.models import ArtifactKind
from ai_ppt_studio.paths import PathPolicy
from ai_ppt_studio.project_store import ProjectStore
from ai_ppt_studio.space_projection import SpaceProjectionBuilder
from ai_ppt_studio.state_store import StateStore
from ai_ppt_studio.workbench_store import WorkbenchStore


def make_project(base: Path) -> tuple[Path, PathPolicy]:
    config = RuntimeConfig.create(
        base / "runtime", base / "repo", base / "install", base / "web"
    )
    policy = PathPolicy(config)
    manifest = ProjectStore(config, policy).create("空间投影测试")
    project = Path(manifest.project_root)
    StateStore(project, policy).initialize()
    return project, policy


class SpaceProjectionTests(unittest.TestCase):
    def test_sources_without_findings_are_honestly_waiting_for_ai(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = make_project(Path(temp))
            source = MaterialIntake(policy).add_text(
                project, "这段原文不得进入投影", "会议纪要"
            )

            projection = SpaceProjectionBuilder(project, policy).build()

            materials = projection["materials"]
            self.assertEqual(materials["source_count"], 1)
            self.assertEqual(materials["status"], "awaiting-ai")
            self.assertEqual(materials["sources"][0]["classification"], "等待 AI 提炼")
            self.assertEqual(materials["sources"][0]["source_id"], source.source_id)
            serialized = json.dumps(projection, ensure_ascii=False)
            self.assertNotIn("这段原文不得进入投影", serialized)
            self.assertNotIn("data:image", serialized)

    def test_all_spaces_project_latest_artifacts_and_real_asset_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project, policy = make_project(Path(temp))
            source = MaterialIntake(policy).add_text(project, "客户现状", "现状材料")
            source_ref = f"sources/{source.source_id}.json"
            artifacts = ArtifactStore(project, policy)
            artifacts.save(
                ArtifactKind.MISSION,
                {
                    "title": "智慧园区方案",
                    "audience": "园区领导",
                    "goal": "确认一期建设",
                    "context": "售前解决方案汇报",
                },
            )
            artifacts.save(
                ArtifactKind.MATERIAL_FINDINGS,
                {
                    "summary": "已提炼一份客户事实",
                    "findings": [
                        {
                            "finding_id": "F01",
                            "finding_type": "fact",
                            "content": "系统分散",
                            "source_ref": source_ref,
                            "locator": "全文",
                            "fact_status": "source-fact",
                            "purposes": ["customer-needs"],
                        }
                    ],
                    "source_assignments": [
                        {
                            "source_id": source.source_id,
                            "purposes": ["customer-needs"],
                            "summary": "客户现状",
                            "status": "usable",
                        }
                    ],
                    "conflicts": [],
                    "gaps": ["缺少验收指标"],
                },
            )
            artifacts.save(
                ArtifactKind.CONTENT_BLUEPRINT,
                {
                    "title": "智慧园区方案",
                    "audience": "园区领导",
                    "goal": "确认一期建设",
                    "narrative_thesis": "先证明问题，再给出低风险路径",
                    "chapters": [{"title": "为什么建设", "slide_ids": ["S01"]}],
                    "slides": [
                        {
                            "slide_id": "S01",
                            "title": "系统在线，运营仍然断裂",
                            "purpose": "建立紧迫性",
                            "claim": "系统分散阻碍协同",
                            "visible_content": ["五套系统"],
                            "speaker_notes": "引用客户材料",
                            "source_refs": [source_ref],
                            "material_refs": [source.source_id],
                        }
                    ],
                },
            )
            artifacts.save(
                ArtifactKind.VISUAL_BRIEF,
                {
                    "design_challenge": "把架构讲成业务闭环",
                    "audience": "园区领导",
                    "desired_response": "愿意启动一期",
                    "constraints": ["阅读优先", "16:9"],
                },
            )
            concept = project / "renders" / "concept-a.png"
            concept.write_bytes(b"concept")
            artifacts.save(
                ArtifactKind.CONCEPT_SET,
                {
                    "directions": [
                        {"id": "A", "name": "运营闭环", "thesis": "关系优先", "sample_image": "renders/concept-a.png"},
                        {"id": "B", "name": "证据路径", "thesis": "证据优先"},
                    ],
                    "recommended_direction": "A",
                },
            )
            artifacts.save(
                ArtifactKind.VISUAL_CONTRACT,
                {
                    "design_thesis": "关系优先",
                    "palette": {"ink": "#111827"},
                    "typography": {"chinese": "PingFang SC"},
                    "layout_rules": ["一页一个主张"],
                    "image_language": ["真实证据"],
                    "editability_rules": ["禁止整页位图"],
                },
            )
            artifacts.save(
                ArtifactKind.SLIDE_SCENE_GRAPH,
                {"slides": [{"slide_id": "S01", "width": 13.333, "height": 7.5, "elements": []}]},
            )
            render = project / "renders" / "slide-1.png"
            render.write_bytes(b"render")
            pptx = project / "ppt" / "deck.pptx"
            pptx.write_bytes(b"pptx")
            artifacts.save(
                ArtifactKind.DELIVERY,
                {
                    "pptx": "ppt/deck.pptx",
                    "renders": ["renders/slide-1.png"],
                    "qa_status": "passed",
                    "sources": [source_ref],
                    "editable": True,
                },
            )

            snapshot = WorkbenchStore(project, policy).ensure()
            spaces = snapshot.space_projections
            self.assertEqual(spaces["materials"]["status"], "classified")
            self.assertEqual(spaces["blueprint"]["slide_count"], 1)
            self.assertEqual(spaces["blueprint"]["source_coverage"]["referenced"], 1)
            self.assertEqual(spaces["visual"]["direction_count"], 2)
            self.assertEqual(spaces["visual"]["directions"][0]["sample_asset_ref"], "renders/concept-a.png")
            self.assertEqual(spaces["visual"]["scene_graph_coverage"], 1)
            self.assertTrue(spaces["delivery"]["pptx_exists"])
            self.assertEqual(spaces["delivery"]["render_count"], 1)
            self.assertTrue(spaces["delivery"]["renders"][0]["exists"])


if __name__ == "__main__":
    unittest.main()
