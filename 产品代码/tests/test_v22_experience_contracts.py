from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.experience.contracts import validate_experience_item
from ai_ppt_studio.errors import ExperienceValidationError
from tests.v22_experience_fixtures import clone_item, experience_item


class ExperienceItemContractTests(unittest.TestCase):
    def test_accepts_only_two_layers_two_domains_and_three_result_types(self) -> None:
        self.assertEqual(validate_experience_item(experience_item())["layer"], "same-type")
        for change in (
            {"layer": "candidate"},
            {"layer": "personal"},
            {"layer": "stable"},
            {"domain": "delivery"},
            {"result_type": "professional-mechanism-candidate"},
        ):
            with self.subTest(change=change), self.assertRaises(
                ExperienceValidationError
            ):
                validate_experience_item(clone_item(**change))

    def test_requires_traceable_results_and_explicit_reuse_privacy(self) -> None:
        for change in (
            {"source_refs": []},
            {"before_after_refs": []},
            {"hard_gate_refs": []},
            {"user_outcomes": []},
            {"sanitized_for_reuse": False},
            {"privacy": {"contains_client_identifiers": True}},
        ):
            with self.subTest(change=change), self.assertRaises(
                ExperienceValidationError
            ):
                validate_experience_item(clone_item(**change))

    def test_rejects_client_payloads_and_product_or_gate_overrides(self) -> None:
        for field, value in (
            ("client_name", "某轨道集团"),
            ("customer_metric", "增长 35%"),
            ("logo_ref", "materials/client-logo.png"),
            ("whole_page_design_ref", "slides/final-page.png"),
            ("gate_override", "G0=passed"),
            ("permission_override", "producer-can-approve"),
            ("product_policy", "skip evidence gate"),
        ):
            with self.subTest(field=field), self.assertRaises(
                ExperienceValidationError
            ):
                validate_experience_item(clone_item(**{field: value}))


if __name__ == "__main__":
    unittest.main()
