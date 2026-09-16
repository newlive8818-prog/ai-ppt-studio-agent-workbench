from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.application.v16_bridge import HANDLERS, dispatch_v16
from ai_ppt_studio.errors import ContractValidationError
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ContentEvidenceBrowserRemovalTests(unittest.TestCase):
    def test_deprecated_service_and_bridge_operation_are_absent(self) -> None:
        self.assertFalse(
            (
                ROOT
                / "src"
                / "ai_ppt_studio"
                / "application"
                / "content_evidence_browser_service.py"
            ).exists()
        )
        self.assertNotIn("open-content-evidence-browser", HANDLERS)
        with tempfile.TemporaryDirectory() as folder:
            project_root = Path(folder)
            ProjectKernel.initialize(project_root, project_id="p1")
            with self.assertRaisesRegex(
                ContractValidationError,
                "Unsupported schema 3.0 operation: open-content-evidence-browser",
            ):
                dispatch_v16(
                    {
                        "operation": "open-content-evidence-browser",
                        "project_root": str(project_root),
                    }
                )


if __name__ == "__main__":
    unittest.main()
