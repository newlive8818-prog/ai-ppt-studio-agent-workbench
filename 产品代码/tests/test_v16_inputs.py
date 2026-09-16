from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.materials.contracts import (
    validate_material_inventory,
)
from ai_ppt_studio.domains.mission.contracts import validate_mission_draft
from ai_ppt_studio.errors import ContractValidationError


class V16InputContractTests(unittest.TestCase):
    def test_mission_draft_becomes_confirmable_but_never_self_confirms(self) -> None:
        mission = validate_mission_draft(
            {
                "topic": "经营一体化方案",
                "primary_audience": "客户决策者",
                "desired_judgment_or_action": "批准一期立项",
                "status": "confirmed",
            }
        )
        self.assertEqual(mission["status"], "confirmable")
        self.assertEqual(mission["missing_required_fields"], [])

        draft = validate_mission_draft({"topic": "经营一体化方案"})
        self.assertEqual(draft["status"], "draft")
        self.assertEqual(
            draft["missing_required_fields"],
            ["primary_audience", "desired_judgment_or_action"],
        )

        with self.assertRaises(ContractValidationError):
            validate_mission_draft({"topic": 42})

    def test_material_inventory_rejects_non_user_origin_and_missing_locator(
        self,
    ) -> None:
        inventory = validate_material_inventory(
            {
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
        )
        self.assertEqual(len(inventory["sources"]), 1)
        with self.assertRaises(ContractValidationError):
            validate_material_inventory(
                {
                    "sources": [
                        {
                            "source_id": "s2",
                            "origin": "web-search",
                            "kind": "url",
                            "locator": "https://example.com",
                            "sha256": "b" * 64,
                        }
                    ]
                }
            )
        with self.assertRaises(ContractValidationError):
            validate_material_inventory(
                {
                    "sources": [
                        {
                            "source_id": "s3",
                            "origin": "user-provided",
                            "kind": "file",
                            "sha256": "c" * 64,
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
