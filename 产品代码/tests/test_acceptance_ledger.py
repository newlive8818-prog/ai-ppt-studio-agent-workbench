from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    EvidenceIndex,
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
        requirements = []
        for path, prefix, section in (
            (ROOT.parent / "01-产品需求基线-v1.0.md", "PRD", "17"),
            (ROOT.parent / "02-系统详细设计-v1.0.md", "SDD", "21"),
            (ROOT.parent / "03-UI设计与交互规范-v1.0.md", "UI", "23"),
        ):
            requirements.extend(
                extract_numbered_requirements(
                    path.read_text(encoding="utf-8"),
                    source_prefix=prefix,
                    section_prefix=section,
                )
            )
        expected = AcceptanceLedger(
            version="1.6", requirements=tuple(requirements)
        ).with_evidence(
            EvidenceIndex.from_path(ROOT / "requirements" / "v1.6-evidence.json")
        )
        self.assertEqual(len(ledger.requirements), 104)
        self.assertEqual(len(ledger.requirements), len(set(ledger.ids)))
        self.assertEqual(ledger.as_dict(), expected.as_dict())
        self.assertEqual(
            sum(item.status == "passed" for item in ledger.requirements), 22
        )
        self.assertTrue(
            all(
                item.status == "unproven"
                for item in ledger.requirements
                if "target-evidence" in item.required_evidence
            )
        )
        by_id = {item.requirement_id: item for item in ledger.requirements}
        self.assertIn("目录框架", by_id["PRD-17.2-03"].text)
        self.assertIn("冻结批次", by_id["PRD-17.2-09"].text)
        self.assertIn("最大宽度侧边栏", by_id["UI-23.2-04"].text)
        self.assertIn("全部页面", by_id["UI-23.2-07"].text)
        self.assertIn("修改方案", by_id["SDD-21.3-13"].text)
        self.assertIn("requires_blueprint_revision", by_id["SDD-21.3-13"].text)
        self.assertIn("全部认可", by_id["SDD-21.3-13"].text)
        self.assertIn("无需修改", by_id["SDD-21.3-13"].text)
        for requirement_id in (
            "PRD-17.1-01",
            "PRD-17.1-03",
            "SDD-21.3-01",
            "SDD-21.3-02",
            "UI-23.2-01",
            "UI-23.2-04",
            "UI-23.2-25",
        ):
            self.assertEqual(by_id[requirement_id].status, "unproven")
        for requirement_id in (
            "PRD-17.1-04",
            "PRD-17.2-03",
            "PRD-17.2-04",
            "PRD-17.2-05",
            "PRD-17.2-06",
            "PRD-17.2-07",
            "PRD-17.2-08",
            "PRD-17.2-09",
            "PRD-17.2-10",
            "PRD-17.5-04",
            "PRD-17.5-07",
            "UI-23.2-05",
            "UI-23.2-07",
            "UI-23.2-08",
            "UI-23.2-09",
        ):
            self.assertEqual(by_id[requirement_id].status, "unproven")

    def test_requirement_passes_only_when_every_proof_kind_resolves(self) -> None:
        markdown = "## 17. 标准\n### 17.1 闭环\n1. 恢复项目。\n"
        requirement = extract_numbered_requirements(
            markdown, source_prefix="PRD", section_prefix="17"
        )[0]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            automated = base / "automated.json"
            runtime = base / "runtime.json"
            automated.write_text('{"passed":true}', encoding="utf-8")
            runtime.write_text('{"passed":true}', encoding="utf-8")
            automated_sha = hashlib.sha256(automated.read_bytes()).hexdigest()
            runtime_sha = hashlib.sha256(runtime.read_bytes()).hexdigest()
            index = EvidenceIndex.from_dict(
                {
                    "schema_version": "1.0",
                    "proofs": [
                        {
                            "proof_ref": f"proof://automated-test/{automated_sha}",
                            "kind": "automated-test",
                            "path": str(automated),
                            "sha256": automated_sha,
                            "requirement_ids": [requirement.requirement_id],
                        },
                        {
                            "proof_ref": f"proof://runtime-evidence/{runtime_sha}",
                            "kind": "runtime-evidence",
                            "path": str(runtime),
                            "sha256": runtime_sha,
                            "requirement_ids": [requirement.requirement_id],
                        },
                    ],
                }
            )
            resolved = AcceptanceLedger(
                version="1.6", requirements=(requirement,)
            ).with_evidence(index)
            self.assertEqual(resolved.requirements[0].status, "passed")
            self.assertEqual(len(resolved.requirements[0].proof_refs), 2)

            missing = EvidenceIndex.from_dict(
                {"schema_version": "1.0", "proofs": [index.proofs[0].as_dict()]}
            )
            unresolved = AcceptanceLedger(
                version="1.6", requirements=(requirement,)
            ).with_evidence(missing)
            self.assertEqual(unresolved.requirements[0].status, "unproven")

    def test_evidence_index_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "proof.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                EvidenceIndex.from_dict(
                    {
                        "schema_version": "1.0",
                        "proofs": [
                            {
                                "proof_ref": "proof://bad/hash",
                                "kind": "automated-test",
                                "path": str(path),
                                "sha256": "0" * 64,
                                "requirement_ids": ["PRD-17.1-01"],
                            }
                        ],
                    }
                )

            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                EvidenceIndex.from_dict(
                    {
                        "schema_version": "1.0",
                        "proofs": [
                            {
                                "proof_ref": "proof://automated-test/not-content-addressed",
                                "kind": "automated-test",
                                "path": str(path),
                                "sha256": digest,
                                "requirement_ids": ["PRD-17.1-01"],
                            }
                        ],
                    }
                )


if __name__ == "__main__":
    unittest.main()
