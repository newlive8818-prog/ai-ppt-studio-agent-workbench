from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.errors import ArtifactReferenceError
from tests.v16_content_fixtures import complete_slide_draft_payload


def valid_mission() -> dict[str, str]:
    return {
        "topic": "经营一体化方案",
        "primary_audience": "客户决策者",
        "desired_judgment_or_action": "批准一期立项",
    }


def valid_materials() -> dict[str, list[dict[str, str]]]:
    return {
        "sources": [
            {
                "source_id": "s1",
                "origin": "user-provided",
                "kind": "text",
                "locator": "chat://message/material-1",
                "sha256": "a" * 64,
            }
        ]
    }


def build_ready_draft(
    service: ContentService,
    slide_count: int = 1,
) -> tuple[int, str, dict[str, str]]:
    mission = service.save_mission_draft("c1", 0, valid_mission())
    materials = service.register_materials("c2", 1, valid_materials())
    service.confirm_mission(
        "c3-confirm",
        2,
        mission_draft_ref=mission,
        material_mode="materials-provided",
        material_inventory_ref=materials,
        user_action_ref="test-user-action://confirmed-content-fixture",
        user_message_ref="",
    )
    strategy = service.register_content_stage(
        "c4",
        3,
        "strategy",
        {
            "mission_ref": mission,
            "material_inventory_ref": materials,
            "content_identity_mode": "material-backed",
            "decision_stage": "立项",
            "core_tension": "系统割裂",
        },
    )
    claim_map = service.register_content_stage(
        "c5",
        4,
        "claim-map",
        {
            "strategy_ref": strategy,
            "claims": [
                {
                    "claim_id": "claim-1",
                    "status": "supported",
                    "evidence_refs": [materials],
                }
            ],
        },
    )
    argument = service.register_content_stage(
        "c6",
        5,
        "argument-map",
        {
            "strategy_ref": strategy,
            "claim_evidence_map_ref": claim_map,
            "chapters": [
                {"chapter_id": "ch1", "task": "建立问题共识"}
            ],
        },
    )
    draft = service.register_content_stage(
        "c7",
        6,
        "slide-draft-set",
        complete_slide_draft_payload(
            argument_map_ref=argument,
            material_ref=materials,
            slide_count=slide_count,
            slide_id_prefix="s",
        ),
    )
    return 7, draft, {
        "mission": mission,
        "materials": materials,
        "strategy": strategy,
        "claim_map": claim_map,
        "argument": argument,
    }


class V16ContentChainTests(unittest.TestCase):
    def test_content_chain_requires_current_verified_upstream_heads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ContentService.initialize(Path(temp), project_id="p1")
            revision, draft, refs = build_ready_draft(service)
            self.assertTrue(draft.startswith("artifact://slide-draft-set/"))
            self.assertEqual(service.kernel.load().revision, revision)
            with self.assertRaises(ArtifactReferenceError):
                service.register_content_stage(
                    "bad",
                    revision,
                    "argument-map",
                    {
                        "strategy_ref": (
                            "artifact://presales-content-strategy/" + "f" * 64
                        ),
                        "claim_evidence_map_ref": refs["claim_map"],
                        "chapters": [{"chapter_id": "x", "task": "x"}],
                    },
                )
            self.assertEqual(service.kernel.load().revision, revision)


if __name__ == "__main__":
    unittest.main()
