from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.domains.presentation.targets import TargetRenderEvidence
from scripts.acceptance.verify_target_evidence import verify_target_evidence


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def evidence_package(base: Path, target_id: str = "macos-powerpoint") -> tuple[Path, Path]:
    evidence = base / target_id
    pptx = base / "delivery" / "same.pptx"
    pptx.parent.mkdir(parents=True)
    pptx.write_bytes(b"deterministic-pptx-contract-fixture")
    (evidence / "exports").mkdir(parents=True)
    (evidence / "pages").mkdir()
    (evidence / "exports" / "deck.pdf").write_bytes(b"pdf-export")
    (evidence / "pages" / "s1.png").write_bytes(b"page-one")
    operating_system = "macOS" if target_id.startswith("macos") else "Windows 11"
    application = "WPS Office" if target_id.endswith("wps") else "Microsoft PowerPoint"
    write_json(
        evidence / "environment.json",
        {
            "target_id": target_id,
            "operating_system": operating_system,
            "operating_system_version": "test-os-version",
            "application": application,
            "application_version": "test-app-version",
            "application_check_result": "passed",
            "executor": "independent-desktop-reviewer",
            "exported_at": "2026-08-10T08:00:00+08:00",
            "tool_version": "desktop-capture/test",
            "overall_result": "passed",
        },
    )
    write_json(evidence / "font-inventory.json", {"fonts": ["Aptos", "Microsoft YaHei"]})
    write_json(evidence / "font-substitution-plan.json", {"substitutions": [], "result": "passed"})
    write_json(
        evidence / "slide-checks.json",
        [
            {
                "slide_id": "s1",
                "semantic_result": "passed",
                "aesthetic_result": "passed",
                "engineering_result": "passed",
                "target_render_result": "passed",
                "page_image": "pages/s1.png",
                "evidence_files": ["pages/s1.png"],
            }
        ],
    )
    write_json(
        evidence / "reviewer-attestation.json",
        {
            "reviewer_id": "independent-desktop-reviewer",
            "reviewer_role": "桌面目标独立审查员",
            "independent_from_producer": True,
            "application_check_result": "passed",
            "font_check_result": "passed",
            "reviewed_at": "2026-08-10T08:00:00+08:00",
            "slide_checks_file": "slide-checks.json",
        },
    )
    files = [
        "environment.json",
        "font-inventory.json",
        "font-substitution-plan.json",
        "slide-checks.json",
        "reviewer-attestation.json",
        "exports/deck.pdf",
        "pages/s1.png",
    ]
    write_json(
        evidence / "evidence-package.json",
        {
            "schema_version": "1.0",
            "capture_mode": "desktop-evidence",
            "source_pptx_sha256": sha(pptx),
            "source_pptx_kind": "final-pptx",
            "files": {name: sha(evidence / name) for name in files},
            "export_files": ["exports/deck.pdf"],
            "page_image_files": ["pages/s1.png"],
        },
    )
    return evidence, pptx


class TargetEvidenceImportTests(unittest.TestCase):
    def test_each_supported_profile_remains_independently_verifiable(self) -> None:
        for target_id in (
            "macos-powerpoint",
            "macos-wps",
            "windows-powerpoint",
            "windows-wps",
        ):
            with self.subTest(target_id=target_id), tempfile.TemporaryDirectory() as temp:
                evidence, pptx = evidence_package(Path(temp), target_id)
                payload = verify_target_evidence(evidence, pptx)
                self.assertEqual(payload["target_id"], target_id)
                self.assertTrue(payload["proof_eligible"])

    def test_verifies_every_file_but_marks_deterministic_fixture_non_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp))
            payload = verify_target_evidence(evidence, pptx, fixture_mode=True)
            self.assertEqual(payload["simulation"], True)
            self.assertEqual(payload["proof_eligible"], False)
            self.assertEqual(payload["application_check_result"], "passed")
            with self.assertRaises(ValueError):
                TargetRenderEvidence.from_payload(payload)

            formal = verify_target_evidence(evidence, pptx, fixture_mode=False)
            parsed = TargetRenderEvidence.from_payload(formal)
            self.assertEqual(parsed.target_id, "macos-powerpoint")
            self.assertEqual(parsed.pptx_sha256, sha(pptx))
            self.assertEqual(parsed.application_check_result, "passed")
            self.assertEqual(parsed.font_check_result, "passed")
            self.assertTrue(
                parsed.reviewer_attestation_ref.startswith(
                    "artifact://desktop-review-attestation/"
                )
            )
            self.assertTrue(formal["proof_eligible"])

    def test_rejects_changed_pptx_export_or_application_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp))
            pptx.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_target_evidence(evidence, pptx)

    def test_rejects_uncovered_page_invalid_time_or_mismatched_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp))
            extra = evidence / "pages" / "s2.png"
            extra.write_bytes(b"uncovered-page")
            package = json.loads(
                (evidence / "evidence-package.json").read_text(encoding="utf-8")
            )
            package["files"]["pages/s2.png"] = sha(extra)
            package["page_image_files"].append("pages/s2.png")
            write_json(evidence / "evidence-package.json", package)
            with self.assertRaises(ValueError):
                verify_target_evidence(evidence, pptx)

        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp))
            environment = json.loads(
                (evidence / "environment.json").read_text(encoding="utf-8")
            )
            environment["exported_at"] = "not-a-timestamp"
            write_json(evidence / "environment.json", environment)
            package = json.loads(
                (evidence / "evidence-package.json").read_text(encoding="utf-8")
            )
            package["files"]["environment.json"] = sha(evidence / "environment.json")
            write_json(evidence / "evidence-package.json", package)
            with self.assertRaises(ValueError):
                verify_target_evidence(evidence, pptx, fixture_mode=True)

        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp))
            attestation = json.loads(
                (evidence / "reviewer-attestation.json").read_text(encoding="utf-8")
            )
            attestation["font_check_result"] = "failed"
            write_json(evidence / "reviewer-attestation.json", attestation)
            package = json.loads(
                (evidence / "evidence-package.json").read_text(encoding="utf-8")
            )
            package["files"]["reviewer-attestation.json"] = sha(
                evidence / "reviewer-attestation.json"
            )
            write_json(evidence / "evidence-package.json", package)
            with self.assertRaises(ValueError):
                verify_target_evidence(evidence, pptx)

        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp))
            (evidence / "exports" / "deck.pdf").write_bytes(b"changed-export")
            with self.assertRaises(ValueError):
                verify_target_evidence(evidence, pptx)

        with tempfile.TemporaryDirectory() as temp:
            evidence, pptx = evidence_package(Path(temp), "windows-wps")
            environment = json.loads((evidence / "environment.json").read_text(encoding="utf-8"))
            environment["application"] = "Microsoft PowerPoint"
            write_json(evidence / "environment.json", environment)
            package = json.loads((evidence / "evidence-package.json").read_text(encoding="utf-8"))
            package["files"]["environment.json"] = sha(evidence / "environment.json")
            write_json(evidence / "evidence-package.json", package)
            with self.assertRaises(ValueError):
                verify_target_evidence(evidence, pptx)


if __name__ == "__main__":
    unittest.main()
