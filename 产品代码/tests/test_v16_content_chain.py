from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.content_service import ContentService
from ai_ppt_studio.application.scoped_confirmation import (
    HOST_CONFIRMATION_SECRET_ENV,
)
from ai_ppt_studio.errors import ContentWorkflowError
from tests.test_v16_content_acceptance import (
    TEST_SECRET,
    authorize_current_framework,
)
from tests.v16_content_fixtures import (
    complete_slide_draft_payload,
    publish_content_stage,
)


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
    mission_confirmation = service.confirm_mission(
        "c3-confirm",
        2,
        mission_draft_ref=mission,
        material_mode="materials-provided",
        material_inventory_ref=materials,
        user_action_ref="test-user-action://confirmed-content-fixture",
        user_message_ref="",
    )
    with patch.dict(
        os.environ, {HOST_CONFIRMATION_SECRET_ENV: TEST_SECRET}, clear=False
    ):
        authorize_current_framework(service, mission_confirmation)
    revision = service.kernel.load().revision
    strategy = publish_content_stage(
        service,
        "c4",
        "strategy",
        {
            "mission_ref": mission,
            "material_inventory_ref": materials,
            "content_identity_mode": "material-backed",
            "decision_stage": "立项",
            "core_tension": "系统割裂",
        },
    )
    claim_map = publish_content_stage(
        service,
        "c5",
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
    argument = publish_content_stage(
        service,
        "c6",
        "argument-map",
        {
            "strategy_ref": strategy,
            "claim_evidence_map_ref": claim_map,
            "chapters": [
                {"chapter_id": "ch1", "task": "建立问题共识"}
            ],
        },
    )
    draft = publish_content_stage(
        service,
        "c7",
        "slide-draft-set",
        complete_slide_draft_payload(
            argument_map_ref=argument,
            material_ref=materials,
            slide_count=slide_count,
            slide_id_prefix="s",
        ),
    )
    return service.kernel.load().revision, draft, {
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
            with self.assertRaises(ContentWorkflowError) as caught:
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
            self.assertEqual(caught.exception.code, "CONTENT_REVIEW_CONFLICT")
            self.assertEqual(service.kernel.load().revision, revision)


if __name__ == "__main__":
    unittest.main()
