from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    EvidenceIndex,
    extract_numbered_requirements,
)

SOURCES = (
    (PROJECT / "01-产品需求基线-v1.0.md", "PRD", "验收标准"),
    (PROJECT / "02-系统详细设计-v1.0.md", "SDD", "测试策略"),
    (PROJECT / "03-UI设计与交互规范-v1.0.md", "UI", "UI 验收"),
)


def authoritative_requirements():
    requirements = []
    for path, prefix, section_title in SOURCES:
        requirements.extend(
            extract_numbered_requirements(
                path.read_text(encoding="utf-8"),
                source_prefix=prefix,
                source_file=path.name,
                section_title=section_title,
            )
        )
    return tuple(requirements)


class AcceptanceLedgerTests(unittest.TestCase):
    def test_package_exposes_explicit_quality_scripts(self) -> None:
        scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))[
            "scripts"
        ]
        self.assertEqual(
            scripts["typecheck"], "tsc -p widget/tsconfig.json --noEmit"
        )
        self.assertEqual(
            scripts["test:python"],
            "PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 -m unittest discover -s tests",
        )
        self.assertEqual(
            scripts["quality"],
            "npm run typecheck && npm run build && npm run test:node && npm run test:widget",
        )

    def test_extracts_explicit_ids_source_and_proof_kinds(self) -> None:
        markdown = """# PRD
## 99. 验收标准
### 99.1 产品闭环
1. [PRD-ACC-PRODUCT-001] 恢复项目。
### 99.2 视觉与 PPTX
1. [PRD-ACC-VISUAL-001] 当前目标实机通过。
## 100. 其他
1. [PRD-ACC-OTHER-001] 不应收录。
"""
        entries = extract_numbered_requirements(
            markdown,
            source_prefix="PRD",
            source_file="01-产品需求基线-v1.0.md",
            section_title="验收标准",
        )
        self.assertEqual(
            [entry.requirement_id for entry in entries],
            ["PRD-ACC-PRODUCT-001", "PRD-ACC-VISUAL-001"],
        )
        self.assertEqual(entries[0].source_section, "产品闭环")
        self.assertEqual(entries[0].source_file, "01-产品需求基线-v1.0.md")
        self.assertEqual(
            entries[-1].required_evidence,
            (
                "automated-test",
                "runtime-evidence",
                "target-evidence",
                "real-project",
            ),
        )

    def test_ids_do_not_depend_on_chapter_numbers(self) -> None:
        before = """## 17. 验收标准
### 17.1 产品闭环
1. [PRD-ACC-PRODUCT-001] 恢复项目。
"""
        after = before.replace("17.", "42.")
        kwargs = {
            "source_prefix": "PRD",
            "source_file": "01-产品需求基线-v1.0.md",
            "section_title": "验收标准",
        }
        self.assertEqual(
            extract_numbered_requirements(before, **kwargs),
            extract_numbered_requirements(after, **kwargs),
        )

    def test_rejects_missing_id_text_and_duplicate_ids(self) -> None:
        kwargs = {
            "source_prefix": "PRD",
            "source_file": "01-产品需求基线-v1.0.md",
            "section_title": "验收标准",
        }
        with self.assertRaisesRegex(ValueError, "missing explicit ID"):
            extract_numbered_requirements(
                "## 17. 验收标准\n### 17.1 闭环\n1. 恢复项目。\n",
                **kwargs,
            )
        with self.assertRaisesRegex(ValueError, "missing text"):
            extract_numbered_requirements(
                "## 17. 验收标准\n### 17.1 闭环\n1. [PRD-ACC-PRODUCT-001]\n",
                **kwargs,
            )
        entry = extract_numbered_requirements(
            "## 17. 验收标准\n### 17.1 闭环\n1. [PRD-ACC-PRODUCT-001] 恢复项目。\n",
            **kwargs,
        )[0]
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            AcceptanceLedger(version="2.2", requirements=(entry, entry))

    def test_checked_in_ledger_matches_authoritative_sources(self) -> None:
        ledger = AcceptanceLedger.from_dict(
            json.loads(
                (ROOT / "requirements" / "v2.2-acceptance-ledger.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        expected = AcceptanceLedger(
            version="2.2", requirements=authoritative_requirements()
        ).with_evidence(
            EvidenceIndex.from_path(ROOT / "requirements" / "v2.2-evidence.json")
        )
        self.assertTrue(ledger.requirements)
        self.assertEqual(ledger.requirement_ids, tuple(dict.fromkeys(ledger.ids)))
        self.assertEqual(ledger.as_dict(), expected.as_dict())
        self.assertTrue(
            all(
                re.fullmatch(r"(?:PRD|SDD|UI)-ACC-[A-Z0-9-]+-\d{3}", item)
                for item in ledger.requirement_ids
            )
        )
        self.assertTrue(all(item.status == "unproven" for item in ledger.requirements))
        self.assertTrue(all(not item.proof_refs for item in ledger.requirements))

    def test_current_baselines_exclude_retired_user_surfaces(self) -> None:
        index = (PROJECT / "00-唯一研发基线索引-v1.0.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Codex 当前项目对话成为唯一主入口", index)
        self.assertIn("删除五空间用户架构", index)
        self.assertIn("内容全稿审核页和视觉专业审核页", index)
        self.assertNotIn("11. [内容蓝图侧边栏全稿审核与批次修改设计]", index)

    def test_requirement_passes_only_when_every_proof_kind_resolves(self) -> None:
        requirement = extract_numbered_requirements(
            "## 17. 验收标准\n### 17.1 产品闭环\n1. [PRD-ACC-PRODUCT-001] 恢复项目。\n",
            source_prefix="PRD",
            source_file="01-产品需求基线-v1.0.md",
            section_title="验收标准",
        )[0]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            proofs = []
            for kind in requirement.required_evidence:
                path = base / f"{kind}.json"
                path.write_text('{"passed":true}', encoding="utf-8")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                proofs.append(
                    {
                        "proof_ref": f"proof://{kind}/{digest}",
                        "kind": kind,
                        "path": str(path),
                        "sha256": digest,
                        "requirement_ids": [requirement.requirement_id],
                    }
                )
            index = EvidenceIndex.from_dict(
                {"schema_version": "1.0", "proofs": proofs}
            )
            resolved = AcceptanceLedger("2.2", (requirement,)).with_evidence(index)
            self.assertEqual(resolved.requirements[0].status, "passed")
            unresolved = AcceptanceLedger("2.2", (requirement,)).with_evidence(
                EvidenceIndex.from_dict(
                    {"schema_version": "1.0", "proofs": proofs[:1]}
                )
            )
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
                                "requirement_ids": ["PRD-ACC-PRODUCT-001"],
                            }
                        ],
                    }
                )


if __name__ == "__main__":
    unittest.main()
