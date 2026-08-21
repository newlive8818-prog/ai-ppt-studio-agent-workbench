from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    EvidenceIndex,
    extract_numbered_requirements,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from scripts.acceptance.verify_release import verify_final_acceptance
from tests.v16_delivery_fixtures import (
    package_artifacts,
    prepared_delivery_ready,
    valid_package_payload,
)
from tests.host_confirmation_fixtures import gate_confirmation_kwargs


SOURCES = (
    (PROJECT / "01-产品需求基线-v1.0.md", "PRD", "17"),
    (PROJECT / "02-系统详细设计-v1.0.md", "SDD", "21"),
    (PROJECT / "03-UI设计与交互规范-v1.0.md", "UI", "23"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_project(base: Path) -> Path:
    project = base / "runtime" / "projects" / "v16-real-project"
    delivery, revision, refs = prepared_delivery_ready(project, slide_count=2)
    artifacts = package_artifacts(delivery, refs)
    package_ref = delivery.register_delivery_package(
        "final-verifier-package",
        revision,
        valid_package_payload(refs, artifacts),
    )
    sent = delivery.record_chat_delivery(
        "final-verifier-chat-send",
        revision + 1,
        {
            "delivery_type": "pptx",
            "build_ref": refs["build"],
            "package_ref": package_ref,
            "pptx_ref": refs["final_pptx"],
            "pptx_sha256": refs["pptx_sha256"],
            "artifact_refs": [package_ref, refs["final_pptx"]],
            "message_ref": "chat://message/final-verifier-pptx",
            "send_status": "sent",
            "sent_at": "2026-08-10T10:00:00+08:00",
            "retry_of": "",
        },
    )
    from ai_ppt_studio.application.gate_confirmation import GateConfirmationPolicy

    context = GateConfirmationPolicy(delivery.kernel).context("G4")
    delivery.confirm_g4(
        "final-verifier-g4",
        sent.revision,
        **gate_confirmation_kwargs(
            context,
            identity_type="verified-message",
            identity_ref="chat://message/final-verifier-accepted",
        ),
    )
    return project


def closed_ledger(base: Path) -> tuple[Path, Path]:
    requirements = []
    for path, prefix, section in SOURCES:
        requirements.extend(
            extract_numbered_requirements(
                path.read_text(encoding="utf-8"),
                source_prefix=prefix,
                section_prefix=section,
            )
        )
    self_unproven = AcceptanceLedger("1.6", tuple(requirements))
    proofs = []
    for kind in sorted(
        {value for item in requirements for value in item.required_evidence}
    ):
        proof_file = base / "proofs" / f"{kind}.json"
        proof_file.parent.mkdir(parents=True, exist_ok=True)
        proof_file.write_text(
            json.dumps(
                {
                    "evidence_identity": "deterministic-contract-fixture",
                    "kind": kind,
                    "simulation": True,
                    "proof_eligible": False,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        proofs.append(
            {
                "proof_ref": f"proof://{kind}/{sha(proof_file)}",
                "kind": kind,
                "path": str(proof_file),
                "sha256": sha(proof_file),
                "requirement_ids": [
                    item.requirement_id
                    for item in requirements
                    if kind in item.required_evidence
                ],
            }
        )
    evidence_path = base / "v1.6-evidence.json"
    evidence_path.write_text(
        json.dumps({"schema_version": "1.0", "proofs": proofs}, indent=2),
        encoding="utf-8",
    )
    closed = self_unproven.with_evidence(EvidenceIndex.from_path(evidence_path))
    ledger_path = base / "v1.6-acceptance-ledger.json"
    ledger_path.write_text(
        json.dumps(closed.as_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return ledger_path, evidence_path


def installed_release(base: Path) -> Path:
    cache = base / "installed" / "ai-ppt-studio"
    cache.mkdir(parents=True)
    plugin_file = cache / "plugin.txt"
    plugin_file.write_text("verified-plugin", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "plugin_name": "ai-ppt-studio",
        "plugin_version": "0.4.0-test",
        "hash_algorithm": "sha256",
        "files": {"plugin.txt": sha(plugin_file)},
    }
    manifest_path = cache / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    evidence = base / "install-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "evidence_identity": "deterministic-contract-fixture",
                "installed_cache_root": str(cache),
                "release_manifest_sha256": sha(manifest_path),
                "official_plugin_validation": "passed",
                "runtime_recovery_test": "passed",
                "installed_probe": {
                    "status": "passed",
                    "source_repository_pythonpath": False,
                    "tool_count": 18,
                    "chat_ui_template_count": 0,
                    "ordinary_tools_data_only": True,
                    "sidebar_capability_code": "HOST_SIDEBAR_UNAVAILABLE",
                    "browser_capability_code": "BROWSER_REVIEW_UNAVAILABLE",
                    "sidebar_real_host_evidence": False,
                    "browser_real_host_evidence": False,
                },
                "simulation": True,
                "proof_eligible": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return evidence


class FinalAcceptanceVerifierTests(unittest.TestCase):
    def test_fixture_exercises_full_verifier_but_cannot_become_formal_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = accepted_project(base)
            ledger, evidence = closed_ledger(base)
            install = installed_release(base)
            result = verify_final_acceptance(
                project,
                ledger,
                evidence_index_path=evidence,
                install_evidence_path=install,
                fixture_mode=True,
            )
            self.assertEqual(result["requirement_count"], 104)
            self.assertEqual(result["passed_requirement_count"], 104)
            self.assertEqual(result["g2_pptx_sha256"], result["g4_pptx_sha256"])
            self.assertTrue(result["release_target_policy_ref"].startswith(
                "artifact://release-target-policy/"
            ))
            self.assertEqual(result["required_target_ids"], ["macos-powerpoint"])
            self.assertEqual(
                result["deferred_target_ids"],
                ["macos-wps", "windows-powerpoint", "windows-wps"],
            )
            self.assertEqual(
                result["compatibility_claim_scope"], ["macos-powerpoint"]
            )
            self.assertFalse(result["proof_eligible"])

            with self.assertRaises(ValueError):
                verify_final_acceptance(
                    project,
                    ledger,
                    evidence_index_path=evidence,
                    install_evidence_path=install,
                )

    def test_rejects_changed_installed_file_or_mixed_gate_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = accepted_project(base)
            ledger, evidence = closed_ledger(base)
            install = installed_release(base)
            install_payload = json.loads(install.read_text(encoding="utf-8"))
            (Path(install_payload["installed_cache_root"]) / "plugin.txt").write_text(
                "tampered", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                verify_final_acceptance(
                    project,
                    ledger,
                    evidence_index_path=evidence,
                    install_evidence_path=install,
                    fixture_mode=True,
                )

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = accepted_project(base)
            ledger, evidence = closed_ledger(base)
            install = installed_release(base)
            state = json.loads(
                (project / "kernel" / "state.json").read_text(encoding="utf-8")
            )
            from ai_ppt_studio.kernel.transactions import ProjectKernel

            kernel = ProjectKernel(project, project_id=state["project_id"])
            slot = "delivery/target-evidence/G4/macos-powerpoint"
            current = kernel.artifacts.resolve(
                ArtifactReference.parse(state["artifact_heads"][slot])
            )["payload"]
            changed = dict(current)
            changed["pptx_sha256"] = "9" * 64
            changed["sha256_before"] = "9" * 64
            changed["sha256_after"] = "9" * 64
            kernel.commit(
                command_id="inject-mixed-hash-for-negative-test",
                expected_revision=state["revision"],
                event_type="test.invalid-target-evidence",
                artifact_updates={slot: ("target-render-evidence", changed)},
            )
            with self.assertRaises(ValueError):
                verify_final_acceptance(
                    project,
                    ledger,
                    evidence_index_path=evidence,
                    install_evidence_path=install,
                    fixture_mode=True,
                )


if __name__ == "__main__":
    unittest.main()
