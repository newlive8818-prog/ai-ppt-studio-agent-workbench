from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    EvidenceIndex,
    extract_numbered_requirements,
)
from scripts.build_acceptance_ledger import build

REPLACED_REQUIREMENT_IDS = frozenset(
    {
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
    }
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

    def test_builder_preserves_version_bound_requirement_inventory(self) -> None:
        markdown = "## 17. 标准\n### 17.1 闭环\n1. 恢复项目。\n"
        requirement = extract_numbered_requirements(
            markdown, source_prefix="PRD", section_prefix="17"
        )[0]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            proof = base / "automated.json"
            proof.write_text('{"passed":true}', encoding="utf-8")
            digest = hashlib.sha256(proof.read_bytes()).hexdigest()
            evidence = base / "evidence.json"
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "proofs": [
                            {
                                "proof_ref": f"proof://automated-test/{digest}",
                                "kind": "automated-test",
                                "path": str(proof),
                                "sha256": digest,
                                "requirement_ids": [requirement.requirement_id],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ledger_path = base / "acceptance-ledger.json"
            ledger_path.write_text(
                json.dumps(
                    AcceptanceLedger("test-version", (requirement,)).as_dict()
                ),
                encoding="utf-8",
            )

            generated, output = build(
                ledger_path=ledger_path,
                evidence_path=evidence,
            )

            self.assertEqual(output, ledger_path)
            self.assertEqual(generated.version, "test-version")
            self.assertEqual(generated.ids, (requirement.requirement_id,))
            self.assertEqual(generated.requirements[0].status, "unproven")

    def test_checked_in_v16_ledger_matches_its_evidence_contract(self) -> None:
        payload = json.loads(
            (ROOT / "requirements" / "v1.6-acceptance-ledger.json").read_text(
                encoding="utf-8"
            )
        )
        ledger = AcceptanceLedger.from_dict(payload)
        requirements = tuple(
            replace(
                requirement,
                proof_refs=(),
                missing_evidence=(),
                status="unproven",
            )
            for requirement in ledger.requirements
        )
        expected = AcceptanceLedger(
            version=ledger.version, requirements=requirements
        ).with_evidence(
            EvidenceIndex.from_path(ROOT / "requirements" / "v1.6-evidence.json")
        )
        self.assertEqual(ledger.version, "1.6")
        self.assertTrue(ledger.requirements)
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
        for requirement_id in REPLACED_REQUIREMENT_IDS:
            self.assertEqual(by_id[requirement_id].status, "unproven")

        evidence_payload = json.loads(
            (ROOT / "requirements" / "v1.6-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        for proof in evidence_payload["proofs"]:
            residual_ids = set(proof["requirement_ids"]) & REPLACED_REQUIREMENT_IDS
            self.assertFalse(
                residual_ids,
                f"{proof['proof_ref']} still maps replaced IDs: {sorted(residual_ids)}",
            )

    def test_v22_review_contract_boundaries_are_explicit(self) -> None:
        index = (ROOT.parent / "00-唯一研发基线索引-v1.0.md").read_text(
            encoding="utf-8"
        )
        sdd = (ROOT.parent / "02-系统详细设计-v1.0.md").read_text(
            encoding="utf-8"
        )
        ui = (ROOT.parent / "03-UI设计与交互规范-v1.0.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("内容审核业务交互历史专项为", index)
        self.assertIn("文件名及正文中的“内容蓝图”“侧边栏”“空间”和固定入口身份均已被 v2.2 取代", index)
        self.assertIn("Codex 当前项目对话是唯一主入口", index)
        self.assertIn("内容 Browser 作为完整内容审核主表面", index)
        self.assertIn("review_type：`content-full-deck | visual-professional`", sdd)
        self.assertIn("host_notification_status", sdd)
        self.assertIn("ai_receipt_status", sdd)
        self.assertIn("内容全稿审核页和视觉专业审核页共享统一会话外壳", sdd)
        self.assertNotIn("content-framework-confirmation", sdd)
        self.assertNotIn("content-full-deck-expansion-authorization", sdd)

        self.assertIn("Codex 当前项目对话是唯一主入口", ui)
        self.assertIn("内容全稿审核页", ui)
        self.assertIn("视觉专业审核页", ui)
        self.assertIn("判断按钮的最小高度为 42 CSS px", ui)
        self.assertIn("两类反馈状态隔离，保存不等于 G3", ui)
        upstream_state = ui.split("### 8.2 上游状态", 1)[1].split(
            "### 8.3 Review ready", 1
        )[0]
        self.assertIn("UI 不显示", upstream_state)
        self.assertIn("待授权展开全部页面", upstream_state)
        self.assertIn("框架确认按钮", upstream_state)
        self.assertIn("整稿展开授权按钮", upstream_state)

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
