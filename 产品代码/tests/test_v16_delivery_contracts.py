from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.delivery_service import DeliveryService
from ai_ppt_studio.errors import (
    ArtifactReferenceError,
    ContractValidationError,
    GateBlockedError,
)
from tests.v16_delivery_fixtures import (
    build_artifacts,
    prepared_g3,
    valid_build_payload,
)
from tests.v16_visual_fixtures import prepared_g2


class V16DeliveryContractTests(unittest.TestCase):
    def test_build_requires_g3_and_complete_native_editable_deck(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            visual, revision, refs = prepared_g2(Path(temp), slide_count=3)
            delivery = DeliveryService(visual.kernel)
            artifacts = build_artifacts(delivery, refs["slide_ids"])
            with self.assertRaises(GateBlockedError):
                delivery.register_build(
                    "early-build",
                    revision,
                    {
                        **valid_build_payload(
                            {**refs, "visual_contract": "artifact://visual-contract/" + "a" * 64},
                            artifacts,
                        )
                    },
                )

        with tempfile.TemporaryDirectory() as temp:
            delivery, revision, refs = prepared_g3(Path(temp), slide_count=3)
            mismatched = build_artifacts(
                delivery, refs["slide_ids"], sha256="7" * 64
            )
            with self.assertRaises(ContractValidationError):
                delivery.register_build(
                    "g2-g4-hash-mismatch",
                    revision,
                    valid_build_payload(refs, mismatched),
                )
            artifacts = build_artifacts(
                delivery, refs["slide_ids"], sha256=refs["pptx_sha256"]
            )
            valid = valid_build_payload(refs, artifacts)
            invalid_payloads = []
            for changes in (
                {"production_route": "route-A"},
                {"slide_ids": list(reversed(refs["slide_ids"]))},
                {"whole_slide_bitmap": True},
                {"native_editability_evidence_refs": []},
                {"pptx_sha256": "8" * 64},
                {"preflight_identity": "formal-target-render"},
                {"semantic_objects_native": False},
                {"image_assets_independent": False},
                {"tool_name": "python-pptx"},
            ):
                invalid_payloads.append({**copy.deepcopy(valid), **changes})
            stale = copy.deepcopy(valid)
            stale["visual_contract_ref"] = "artifact://visual-contract/" + "a" * 64
            invalid_payloads.append(stale)
            for index, payload in enumerate(invalid_payloads):
                with self.subTest(index=index), self.assertRaises(
                    (ContractValidationError, ArtifactReferenceError)
                ):
                    delivery.register_build(
                        f"invalid-build-{index}", revision, payload
                    )
                self.assertEqual(delivery.kernel.load().revision, revision)

            build_ref = delivery.register_build(
                "valid-build", revision, valid
            )
            self.assertTrue(build_ref.startswith("artifact://presentation-build/"))
            state = delivery.kernel.load()
            self.assertEqual(state.artifact_heads["delivery/build"], build_ref)
            self.assertEqual(state.gate_status["G4"], "open")


if __name__ == "__main__":
    unittest.main()
