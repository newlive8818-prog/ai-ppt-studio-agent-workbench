from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.presentation.targets import (
    REQUIRED_TARGET_IDS,
    TargetRenderEvidence,
    validate_required_targets,
)
from ai_ppt_studio.domains.presentation.release_policy import SUPPORTED_TARGET_IDS
from ai_ppt_studio.errors import GateBlockedError


def evidence_payload(
    target: str, sha: str = "a" * 64, result: str = "passed"
) -> dict:
    return {
        "target_id": target,
        "evidence_identity": "formal-target-render",
        "operating_system": (
            "macOS" if target.startswith("macos") else "Windows 11"
        ),
        "operating_system_version": (
            "15.6" if target.startswith("macos") else "24H2"
        ),
        "application": (
            "WPS Office" if target.endswith("wps") else "Microsoft PowerPoint"
        ),
        "application_version": "test-version",
        "application_check_result": result,
        "font_check_result": result,
        "font_inventory_ref": f"artifact://font-inventory/{'c' * 64}",
        "font_substitution_plan_ref": f"artifact://font-plan/{'d' * 64}",
        "reviewer_attestation_ref": f"artifact://desktop-review-attestation/{'3' * 64}",
        "source_pptx_ref": f"artifact://native-pptx/{'e' * 64}",
        "pptx_sha256": sha,
        "sha256_before": sha,
        "sha256_after": sha,
        "export_refs": [f"artifact://target-export/{'f' * 64}"],
        "page_image_refs": [f"artifact://target-page-image/{'1' * 64}"],
        "slide_checks": [
            {
                "slide_id": "s1",
                "semantic_result": result,
                "aesthetic_result": result,
                "engineering_result": result,
                "target_render_result": result,
                "evidence_refs": [f"artifact://slide-check/{'2' * 64}"],
                **(
                    {
                        "failure_reason": "目标软件渲染未通过",
                        "repair_instruction": "修复后重新实机导出",
                    }
                    if result == "failed"
                    else {}
                ),
            }
        ],
        "executor": "desktop-qa-operator",
        "exported_at": "2026-08-09T12:00:00+08:00",
        "tool_version": "target-capture/1.0",
        "overall_result": result,
        "evidence_ref": f"artifact://target-render-capture/{'b' * 64}",
    }


def evidence(
    target: str, sha: str = "a" * 64, result: str = "passed"
) -> TargetRenderEvidence:
    return TargetRenderEvidence.from_payload(evidence_payload(target, sha, result))


class TargetEvidenceMatrixTests(unittest.TestCase):
    def test_round_trip_preserves_independent_application_and_font_results(self) -> None:
        parsed = evidence("macos-powerpoint")
        payload = parsed.as_payload()
        self.assertEqual(payload["application_check_result"], "passed")
        self.assertEqual(payload["font_check_result"], "passed")
        self.assertTrue(
            payload["reviewer_attestation_ref"].startswith(
                "artifact://desktop-review-attestation/"
            )
        )

        application_failure = evidence_payload("macos-powerpoint", result="passed")
        application_failure["application_check_result"] = "failed"
        application_failure["overall_result"] = "failed"
        failed = TargetRenderEvidence.from_payload(application_failure)
        self.assertEqual(failed.overall_result, "failed")

    def test_accepts_all_four_targets_for_same_hash(self) -> None:
        result = validate_required_targets(
            [evidence(target) for target in SUPPORTED_TARGET_IDS],
            SUPPORTED_TARGET_IDS,
        )
        self.assertEqual(result.pptx_sha256, "a" * 64)
        self.assertEqual(result.target_ids, SUPPORTED_TARGET_IDS)

    def test_single_required_target_forms_complete_matrix(self) -> None:
        result = validate_required_targets(
            [evidence("macos-powerpoint")],
            ("macos-powerpoint",),
        )

        self.assertEqual(result.pptx_sha256, "a" * 64)
        self.assertEqual(result.target_ids, ("macos-powerpoint",))

    def test_deferred_evidence_cannot_replace_or_join_required_target(self) -> None:
        for values in (
            [evidence("macos-wps")],
            [evidence("macos-powerpoint"), evidence("macos-wps")],
        ):
            with self.subTest(values=values), self.assertRaises(GateBlockedError):
                validate_required_targets(values, ("macos-powerpoint",))

    def test_rejects_missing_failed_duplicate_or_mismatched_hash(self) -> None:
        cases = (
            [evidence(target) for target in SUPPORTED_TARGET_IDS[:-1]],
            [
                evidence(
                    target,
                    result="failed" if target == "macos-wps" else "passed",
                )
                for target in SUPPORTED_TARGET_IDS
            ],
            [
                evidence(
                    target,
                    sha="b" * 64 if target == "windows-wps" else "a" * 64,
                )
                for target in SUPPORTED_TARGET_IDS
            ],
            [evidence(target) for target in SUPPORTED_TARGET_IDS]
            + [evidence("macos-wps")],
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(GateBlockedError):
                validate_required_targets(values, SUPPORTED_TARGET_IDS)

    def test_rejects_empty_duplicate_or_unsupported_required_target_ids(self) -> None:
        for required in (
            (),
            ("macos-powerpoint", "macos-powerpoint"),
            ("linux-libreoffice",),
        ):
            with self.subTest(required=required), self.assertRaises(GateBlockedError):
                validate_required_targets([], required)

    def test_rejects_incomplete_preflight_or_wrong_target_identity(self) -> None:
        invalid_payloads = []
        for field in (
            "operating_system_version",
            "application_check_result",
            "font_check_result",
            "font_inventory_ref",
            "font_substitution_plan_ref",
            "reviewer_attestation_ref",
            "source_pptx_ref",
            "export_refs",
            "page_image_refs",
            "slide_checks",
            "executor",
            "exported_at",
            "tool_version",
            "evidence_ref",
        ):
            payload = evidence_payload("macos-powerpoint")
            payload.pop(field)
            invalid_payloads.append(payload)
        preflight = evidence_payload("macos-powerpoint")
        preflight["evidence_identity"] = "preflight-only"
        invalid_payloads.append(preflight)
        wrong_application = evidence_payload("windows-wps")
        wrong_application["application"] = "Microsoft PowerPoint"
        invalid_payloads.append(wrong_application)
        wrong_os = evidence_payload("macos-wps")
        wrong_os["operating_system"] = "Windows 11"
        invalid_payloads.append(wrong_os)
        changed_hash = evidence_payload("windows-powerpoint")
        changed_hash["sha256_after"] = "9" * 64
        invalid_payloads.append(changed_hash)
        failed_slide = evidence_payload("macos-powerpoint")
        failed_slide["slide_checks"][0]["engineering_result"] = "failed"
        failed_slide["slide_checks"][0]["failure_reason"] = "对象错位"
        invalid_payloads.append(failed_slide)
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                TargetRenderEvidence.from_payload(payload)


if __name__ == "__main__":
    unittest.main()
