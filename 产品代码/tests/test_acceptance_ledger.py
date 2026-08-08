from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    extract_numbered_requirements,
)


class AcceptanceLedgerTests(unittest.TestCase):
    def test_extracts_stable_ids_and_proof_kinds(self) -> None:
        markdown = """# PRD
## 17. 研发验收标准
### 17.1 产品闭环
1. 恢复项目。
2. 状态一致。
### 17.3 视觉与 PPTX
1. 四目标实机通过。
## 18. 其他
1. 不应收录。
"""
        entries = extract_numbered_requirements(
            markdown, source_prefix="PRD", section_prefix="17"
        )
        self.assertEqual(
            [entry.requirement_id for entry in entries],
            ["PRD-17.1-01", "PRD-17.1-02", "PRD-17.3-01"],
        )
        self.assertEqual(
            entries[-1].required_evidence,
            (
                "automated-test",
                "runtime-evidence",
                "target-evidence",
                "real-project",
            ),
        )

    def test_rejects_duplicate_ids_and_missing_proof(self) -> None:
        markdown = "## 17. 标准\n### 17.1 闭环\n1. 恢复项目。\n"
        entry = extract_numbered_requirements(
            markdown, source_prefix="PRD", section_prefix="17"
        )[0]
        with self.assertRaises(ValueError):
            AcceptanceLedger(version="1.6", requirements=(entry, entry))

    def test_checked_in_ledger_matches_authoritative_sources(self) -> None:
        payload = json.loads(
            (ROOT / "requirements" / "v1.6-acceptance-ledger.json").read_text(
                encoding="utf-8"
            )
        )
        ledger = AcceptanceLedger.from_dict(payload)
        self.assertGreaterEqual(len(ledger.requirements), 60)
        self.assertEqual(len(ledger.requirements), len(set(ledger.ids)))
        self.assertTrue(
            all(item.status == "unproven" for item in ledger.requirements)
        )


if __name__ == "__main__":
    unittest.main()
