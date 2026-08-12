from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.v16_bridge import dispatch_v16
from ai_ppt_studio.domains.presentation.targets import REQUIRED_TARGET_IDS
from tests.test_v16_review_marks import accepted_content
from tests.v16_delivery_fixtures import prepared_delivery_ready


class V16WorkspaceProjectionTests(unittest.TestCase):
    def test_unconfirmed_overview_projects_the_complete_mission_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            service = ContentService.initialize(project, project_id="p1")
            draft_ref = service.save_mission_draft(
                "mission-card",
                0,
                {
                    "topic": "经营一体化方案",
                    "primary_audience": "客户经营与数字化决策团队",
                    "desired_judgment_or_action": "确认一期范围并进入联合验证",
                    "background": "客户尚未提供现状材料。",
                    "constraints": ["阅读优先", "不虚构客户事实"],
                    "red_lines": ["不承诺确定收益"],
                    "open_questions": ["客户当前系统边界待联合确认"],
                },
            )

            snapshot = dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project),
                }
            )["snapshot"]
            overview = snapshot["workspace"]["overview"]

            self.assertEqual(snapshot["workspace"]["active_space"], "overview")
            self.assertEqual(overview["mission_status"], "confirmable")
            self.assertEqual(overview["mission_draft_ref"], draft_ref)
            self.assertEqual(
                overview["mission_card"],
                {
                    "topic": "经营一体化方案",
                    "primary_audience": "客户经营与数字化决策团队",
                    "desired_judgment_or_action": "确认一期范围并进入联合验证",
                    "material_state": "no-materials",
                    "material_inventory_ref": "",
                    "materials": [],
                    "background": ["客户尚未提供现状材料。"],
                    "constraints": ["阅读优先", "不虚构客户事实"],
                    "red_lines": ["不承诺确定收益"],
                    "unknowns": ["客户当前系统边界待联合确认"],
                },
            )
            self.assertEqual(
                overview["primary_action"],
                {
                    "kind": "confirm-mission",
                    "label": "确认任务并开始内容策划",
                    "enabled": True,
                },
            )

    def test_schema3_snapshot_exposes_one_formal_five_space_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            service = ContentService.initialize(project, project_id="p1")
            _revision, blueprint_ref = accepted_content(service, slide_count=2)

            snapshot = dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project),
                }
            )["snapshot"]

            self.assertEqual(snapshot["schema_version"], "3.0")
            self.assertEqual(
                set(snapshot["workspace"]),
                {
                    "active_space",
                    "navigation",
                    "overview",
                    "materials",
                    "blueprint",
                    "visual",
                    "delivery",
                },
            )
            self.assertEqual(
                [item["space_id"] for item in snapshot["workspace"]["navigation"]],
                ["overview", "materials", "blueprint", "visual", "delivery"],
            )
            self.assertEqual(snapshot["workspace"]["active_space"], "blueprint")
            self.assertEqual(snapshot["workspace"]["blueprint"]["slide_count"], 2)
            self.assertEqual(
                snapshot["workspace"]["blueprint"]["source_version"],
                blueprint_ref,
            )
            self.assertTrue(snapshot["workspace"]["blueprint"]["review_available"])
            self.assertEqual(
                snapshot["workspace"]["blueprint"]["primary_action"],
                {
                    "kind": "open-content-review",
                    "label": "打开内容审阅",
                    "enabled": True,
                },
            )
            self.assertFalse(snapshot["workspace"]["visual"]["review_available"])
            self.assertEqual(
                snapshot["workspace"]["visual"]["primary_action"]["kind"],
                "none",
            )
            self.assertNotIn("space_projections", snapshot)
            serialized = json.dumps(snapshot, ensure_ascii=False).lower()
            self.assertNotIn("selected_direction", serialized)
            self.assertNotIn("weightedscore", serialized)

    def test_delivery_projection_preserves_four_independent_same_hash_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            _delivery, _revision, refs = prepared_delivery_ready(
                project, slide_count=2
            )

            snapshot = dispatch_v16(
                {
                    "operation": "get-project-snapshot",
                    "project_root": str(project),
                }
            )["snapshot"]
            delivery = snapshot["workspace"]["delivery"]

            self.assertEqual(snapshot["workspace"]["active_space"], "delivery")
            self.assertEqual(
                [item["target_id"] for item in delivery["targets"]],
                list(REQUIRED_TARGET_IDS),
            )
            self.assertEqual(
                {item["status"] for item in delivery["targets"]}, {"passed"}
            )
            self.assertEqual(
                {item["pptx_sha256"] for item in delivery["targets"]},
                {refs["pptx_sha256"]},
            )
            self.assertEqual(delivery["hash_identity"], refs["pptx_sha256"])
            self.assertEqual(
                delivery["quality_gates"],
                {
                    "semantic": "passed",
                    "aesthetic": "passed",
                    "engineering": "passed",
                    "target_render": "passed",
                },
            )
            self.assertEqual(delivery["primary_action"]["kind"], "none")
            self.assertNotIn("contact_sheet", json.dumps(delivery))
            self.assertNotIn("download", json.dumps(delivery))


if __name__ == "__main__":
    unittest.main()
