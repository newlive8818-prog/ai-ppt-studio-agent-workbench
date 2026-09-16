from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "ai_ppt_studio" / "application"
KERNEL = ROOT / "src" / "ai_ppt_studio" / "kernel"


class RuntimeShapeTests(unittest.TestCase):
    def test_bridge_is_an_explicit_handler_map_split_by_domain(self) -> None:
        bridge_root = APP / "bridge"
        expected = {
            "__init__.py",
            "project.py",
            "content.py",
            "review.py",
            "visual.py",
            "delivery_experience.py",
        }
        self.assertEqual(
            {path.name for path in bridge_root.glob("*.py")},
            expected,
        )
        dispatcher = (APP / "v16_bridge.py").read_text(encoding="utf-8")
        self.assertIn("HANDLERS", dispatcher)
        self.assertNotIn('if operation == "', dispatcher)
        self.assertLessEqual(len(dispatcher.splitlines()), 120)

    def test_retired_content_result_methods_are_physically_absent(self) -> None:
        project_service = (APP / "project_service.py").read_text(encoding="utf-8")
        for retired in (
            "preflight_content_agent_result",
            "replay_content_agent_result",
            "commit_content_agent_result",
        ):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, project_service)

    def test_shared_guards_and_kernel_pure_responsibilities_exist(self) -> None:
        self.assertTrue((APP / "artifact_guards.py").is_file())
        self.assertTrue((KERNEL / "persistence.py").is_file())
        self.assertTrue((KERNEL / "confirmation_history.py").is_file())
        transactions = (KERNEL / "transactions.py").read_text(encoding="utf-8")
        self.assertIn("from ai_ppt_studio.kernel.persistence import", transactions)
        self.assertIn(
            "from ai_ppt_studio.kernel.confirmation_history import", transactions
        )


if __name__ == "__main__":
    unittest.main()
