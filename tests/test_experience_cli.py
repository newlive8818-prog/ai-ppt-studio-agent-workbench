from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExperienceCliTests(unittest.TestCase):
    def run_cli(self, prefix: list[str], cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_cli_runs_create_recommend_apply_evaluate_and_inspect_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            web = base / "web"
            web.mkdir()
            runtime = base / "runtime"
            prefix = [
                "--runtime-root", str(runtime),
                "--source-repo-root", str(base / "repo"),
                "--install-root", str(base / "install"),
                "--upstream-root", str(web),
            ]
            source_result = self.run_cli(prefix, web, "init", "--name", "来源项目")
            target_result = self.run_cli(prefix, web, "init", "--name", "目标项目")
            source = json.loads(source_result.stdout)["project"]["project_root"]
            target = json.loads(target_result.stdout)["project"]["project_root"]
            candidate_path = self.write_json(
                base / "candidate.json",
                {
                    "name": "案例问题建设成效叙事",
                    "experience_type": "content-strategy",
                    "mechanism": "案例页先回答原有问题，再说明建设内容，最后用结果证明能力。",
                    "model_interpretation": "单独罗列数据不能证明交付能力。",
                    "source_refs": ["reviews/feedback/v0003.json"],
                    "scope": {
                        "scenes": ["售前方案"],
                        "audiences": ["国企决策者"],
                        "slide_tasks": ["项目案例"],
                        "conditions": ["已验收"],
                    },
                    "evidence_refs": [],
                    "before_after_refs": [],
                    "counterexamples": ["只有指标数字，没有建设内容"],
                    "privacy_level": "private",
                    "portable_scope": "personal-installation",
                    "sanitized_for_reuse": True,
                },
            )
            context_path = self.write_json(
                base / "context.json",
                {
                    "scene": "售前方案",
                    "audience": "国企决策者",
                    "slide_task": "项目案例",
                    "conditions": ["已验收"],
                },
            )

            created = self.run_cli(
                prefix,
                web,
                "experience-create",
                "--project", source,
                "--input", str(candidate_path),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            experience = json.loads(created.stdout)["experience"]

            listed = self.run_cli(prefix, web, "experience-list", "--level", "candidate")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(json.loads(listed.stdout)["experiences"][0]["experience_id"], experience["experience_id"])

            recommended = self.run_cli(
                prefix, web, "experience-recommend", "--input", str(context_path)
            )
            self.assertEqual(recommended.returncode, 0, recommended.stderr)
            self.assertIn("slide_task:项目案例", json.loads(recommended.stdout)["recommendations"][0]["match_reasons"])

            applied = self.run_cli(
                prefix,
                web,
                "experience-apply",
                "--project", target,
                "--experience", experience["experience_id"],
                "--input", str(context_path),
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)
            application_id = json.loads(applied.stdout)["application"]["application_id"]
            evaluation_path = self.write_json(
                base / "evaluation.json",
                {
                    "outcome": "success",
                    "user_accepted": True,
                    "notes": "案例可信度明显提升",
                    "evidence_refs": ["reviews/delivery-review.html"],
                },
            )
            evaluated = self.run_cli(
                prefix,
                web,
                "experience-evaluate",
                "--application", application_id,
                "--input", str(evaluation_path),
            )
            self.assertEqual(evaluated.returncode, 0, evaluated.stderr)
            self.assertEqual(json.loads(evaluated.stdout)["experience"]["success_count"], 1)

            shown = self.run_cli(
                prefix,
                web,
                "experience-show",
                "--experience", experience["experience_id"],
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertGreater(json.loads(shown.stdout)["experience"]["version"], 1)

            disabled = self.run_cli(
                prefix,
                web,
                "experience-set-level",
                "--experience", experience["experience_id"],
                "--level", "disabled",
                "--reason", "验证禁用命令",
            )
            self.assertEqual(disabled.returncode, 0, disabled.stderr)
            self.assertFalse(json.loads(disabled.stdout)["experience"]["enabled"])

            rolled_back = self.run_cli(
                prefix,
                web,
                "experience-rollback",
                "--experience", experience["experience_id"],
                "--version", "1",
                "--reason", "验证恢复首版",
            )
            self.assertEqual(rolled_back.returncode, 0, rolled_back.stderr)
            restored = json.loads(rolled_back.stdout)["experience"]
            self.assertEqual(restored["level"], "candidate")
            self.assertEqual(restored["rollback_from_version"], 1)

    def test_preflight_reports_evidence_backed_experience_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            web = base / "web"
            web.mkdir()
            prefix = [
                "--runtime-root", str(base / "runtime"),
                "--source-repo-root", str(base / "repo"),
                "--install-root", str(base / "install"),
                "--upstream-root", str(web),
            ]
            result = self.run_cli(prefix, web, "preflight")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            evidence = payload["capability_evidence"]["experience_evolution"]
            self.assertTrue(payload["capabilities"]["experience_evolution"])
            self.assertTrue(evidence["ready"])
            self.assertIn("rollback", evidence["operations"])
            self.assertFalse(evidence["stable_kernel_auto_mutation"])
            self.assertTrue(Path(evidence["index_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
