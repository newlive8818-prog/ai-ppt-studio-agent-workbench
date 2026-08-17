from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.v22_experience_fixtures import experience_item


ROOT = Path(__file__).resolve().parents[1]


class ExperienceCliTests(unittest.TestCase):
    def run_cli(
        self, prefix: list[str], cwd: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "ai_ppt_studio", *prefix, *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def write_json(path: Path, payload: dict[str, object]) -> Path:
        path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        return path

    def test_cli_runs_v22_absorb_recommend_apply_evaluate_promote_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            web = base / "web"
            web.mkdir()
            prefix = [
                "--runtime-root",
                str(base / "runtime"),
                "--source-repo-root",
                str(base / "repo"),
                "--install-root",
                str(base / "install"),
                "--upstream-root",
                str(web),
            ]
            target_result = self.run_cli(
                prefix, web, "init", "--name", "目标项目"
            )
            target_root = json.loads(target_result.stdout)["project"][
                "project_root"
            ]
            item_path = self.write_json(
                base / "experience.json", experience_item()
            )
            created = self.run_cli(
                prefix,
                web,
                "experience-absorb-same-type",
                "--input",
                str(item_path),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            experience = json.loads(created.stdout)["experience"]
            original_ref = experience["experience_ref"]

            listed = self.run_cli(
                prefix,
                web,
                "experience-list",
                "--domain",
                "content",
                "--layer",
                "same-type",
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(
                json.loads(listed.stdout)["experiences"][0]["experience_id"],
                "exp-reading-path",
            )

            applicability = self.write_json(
                base / "applicability.json",
                {"conditions": ["阅读优先"]},
            )
            recommended = self.run_cli(
                prefix,
                web,
                "experience-recommend",
                "--domain",
                "content",
                "--type-signature",
                "presales:transport:decision",
                "--input",
                str(applicability),
            )
            self.assertEqual(recommended.returncode, 0, recommended.stderr)
            self.assertEqual(
                json.loads(recommended.stdout)["recommendations"][0][
                    "experience_ref"
                ],
                original_ref,
            )

            application_input = self.write_json(
                base / "application.json",
                {
                    "target_type_signature": "presales:transport:decision",
                    "context": {"conditions": ["阅读优先"]},
                    "evidence_refs": [
                        "artifact://reading-deck-blueprint/" + "1" * 64
                    ],
                    "applied_at": "2026-08-15T01:00:00+08:00",
                },
            )
            applied = self.run_cli(
                prefix,
                web,
                "experience-apply",
                "--project",
                target_root,
                "--experience-ref",
                original_ref,
                "--input",
                str(application_input),
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            application_id = json.loads(applied.stdout)["application"][
                "application_id"
            ]
            evaluation_input = self.write_json(
                base / "evaluation.json",
                {
                    "outcome": "success",
                    "user_outcome_ref": "host-message://accepted-target",
                    "hard_gate_refs": [
                        "artifact://content-hard-gate-record/" + "2" * 64
                    ],
                    "evidence_refs": [
                        "artifact://reading-deck-blueprint/" + "3" * 64
                    ],
                    "evaluated_at": "2026-08-15T02:00:00+08:00",
                },
            )
            evaluated = self.run_cli(
                prefix,
                web,
                "experience-evaluate",
                "--application-id",
                application_id,
                "--input",
                str(evaluation_input),
            )
            self.assertEqual(evaluated.returncode, 0, evaluated.stderr)

            shown = self.run_cli(
                prefix,
                web,
                "experience-show",
                "--domain",
                "content",
                "--layer",
                "same-type",
                "--experience-id",
                "exp-reading-path",
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            current = json.loads(shown.stdout)["experience"]
            self.assertEqual(current["application_count"], 1)

            promoted = self.run_cli(
                prefix,
                web,
                "experience-promote-global",
                "--same-type-ref",
                current["experience_ref"],
                "--user-directive-ref",
                "host-message://use-globally",
                "--promoted-at",
                "2026-08-15T03:00:00+08:00",
            )
            self.assertEqual(promoted.returncode, 0, promoted.stderr)
            self.assertEqual(
                json.loads(promoted.stdout)["experience"]["layer"], "global"
            )

            rolled_back = self.run_cli(
                prefix,
                web,
                "experience-rollback",
                "--experience-ref",
                current["experience_ref"],
                "--target-version-ref",
                original_ref,
                "--reason",
                "恢复首版",
                "--rolled-back-at",
                "2026-08-15T04:00:00+08:00",
            )
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            restored = json.loads(rolled_back.stdout)["experience"]
            self.assertEqual(restored["rollback_from_version"], 1)
            self.assertNotIn("level", restored)

    def test_preflight_reports_evidence_backed_v22_experience_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            web = base / "web"
            web.mkdir()
            prefix = [
                "--runtime-root",
                str(base / "runtime"),
                "--source-repo-root",
                str(base / "repo"),
                "--install-root",
                str(base / "install"),
                "--upstream-root",
                str(web),
            ]
            result = self.run_cli(prefix, web, "preflight")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            evidence = payload["capability_evidence"]["experience_evolution"]
            self.assertTrue(payload["capabilities"]["experience_evolution"])
            self.assertTrue(evidence["ready"])
            self.assertEqual(evidence["schema_version"], "2.2")
            self.assertIn("promote_global", evidence["operations"])
            self.assertNotIn("create_candidate", evidence["operations"])
            self.assertFalse(evidence["stable_kernel_auto_mutation"])
            self.assertTrue(Path(evidence["index_path"]).is_file())
            self.assertTrue(Path(evidence["application_log"]).is_file())
            self.assertTrue(Path(evidence["evaluation_log"]).is_file())
            self.assertTrue(Path(evidence["promotion_log"]).is_file())


if __name__ == "__main__":
    unittest.main()
