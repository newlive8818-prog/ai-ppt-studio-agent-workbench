from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (
    AcceptanceLedger,
    EvidenceIndex,
    extract_numbered_requirements,
)
from scripts import build_acceptance_ledger

SOURCES = (
    (PROJECT / "01-产品需求基线-v1.0.md", "PRD", "验收标准"),
    (PROJECT / "02-系统详细设计-v1.0.md", "SDD", "测试策略"),
    (PROJECT / "03-UI设计与交互规范-v1.0.md", "UI", "UI 验收"),
)

V22_LEDGER_SHA256 = "3f328cd52877ce134ca11a8467c86868fec94bd5973d4d83ce44fbee8adcee8d"
V22_EVIDENCE_SHA256 = "3805ba2e5e09980ec8485b3fff84a40ddb484d6ec90fbccda37f1f3174ce4f14"
V23_REQUIREMENT_IDS = {
    *(f"PRD-ACC-V23-VISUAL-{index:03d}" for index in range(1, 8)),
    *(f"UI-ACC-V23-VISUAL-{index:03d}" for index in range(1, 6)),
}


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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    def test_frozen_v22_ledger_remains_exact_and_excludes_v23(self) -> None:
        ledger_path = ROOT / "requirements" / "v2.2-acceptance-ledger.json"
        evidence_path = ROOT / "requirements" / "v2.2-evidence.json"
        ledger = AcceptanceLedger.from_dict(
            json.loads(ledger_path.read_text(encoding="utf-8"))
        )
        self.assertEqual(file_sha256(ledger_path), V22_LEDGER_SHA256)
        self.assertEqual(file_sha256(evidence_path), V22_EVIDENCE_SHA256)
        self.assertEqual(ledger.version, "2.2")
        self.assertEqual(len(ledger.requirements), 145)
        self.assertFalse(
            any("V23" in item.requirement_id for item in ledger.requirements)
        )

    def test_checked_in_v23_ledger_matches_current_authoritative_sources(self) -> None:
        ledger_path = ROOT / "requirements" / "v2.3-acceptance-ledger.json"
        evidence_path = ROOT / "requirements" / "v2.3-evidence.json"
        self.assertTrue(ledger_path.is_file(), "v2.3 ledger must be checked in")
        self.assertTrue(evidence_path.is_file(), "v2.3 evidence index must exist")
        ledger = AcceptanceLedger.from_dict(
            json.loads(ledger_path.read_text(encoding="utf-8"))
        )
        expected = AcceptanceLedger(
            version="2.3", requirements=authoritative_requirements()
        ).with_evidence(
            EvidenceIndex.from_path(evidence_path)
        )
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(ledger.version, "2.3")
        self.assertEqual(len(ledger.requirements), 157)
        self.assertEqual(evidence, {"schema_version": "1.0", "proofs": []})
        self.assertTrue(ledger.requirements)
        self.assertEqual(ledger.requirement_ids, tuple(dict.fromkeys(ledger.ids)))
        self.assertEqual(ledger.as_dict(), expected.as_dict())
        self.assertEqual(
            {item for item in ledger.requirement_ids if "V23" in item},
            V23_REQUIREMENT_IDS,
        )
        self.assertTrue(
            all(
                re.fullmatch(r"(?:PRD|SDD|UI)-ACC-[A-Z0-9-]+-\d{3}", item)
                for item in ledger.requirement_ids
            )
        )
        self.assertTrue(all(item.status == "unproven" for item in ledger.requirements))
        self.assertTrue(all(not item.proof_refs for item in ledger.requirements))

    def test_v23_generator_does_not_overwrite_v22_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requirements = root / "requirements"
            requirements.mkdir(parents=True)
            v22_ledger = requirements / "v2.2-acceptance-ledger.json"
            v22_evidence = requirements / "v2.2-evidence.json"
            ledger_sentinel = b"frozen-v2.2-ledger\n"
            evidence_sentinel = b'{"schema_version":"1.0","proofs":[]}\n'
            v22_ledger.write_bytes(ledger_sentinel)
            v22_evidence.write_bytes(evidence_sentinel)

            with patch.object(build_acceptance_ledger, "ROOT", root):
                generated, target = build_acceptance_ledger.build()

            self.assertEqual(v22_ledger.read_bytes(), ledger_sentinel)
            self.assertEqual(v22_evidence.read_bytes(), evidence_sentinel)
            self.assertEqual(generated.version, "2.3")
            self.assertEqual(target, requirements / "v2.3-acceptance-ledger.json")
            self.assertTrue((requirements / "v2.3-evidence.json").is_file())

    def test_v23_visual_requirements_retain_visual_proof_obligations(self) -> None:
        requirements = {
            item.requirement_id: item for item in authoritative_requirements()
        }
        visual_ids = sorted(
            item for item in requirements if item.startswith("PRD-ACC-V23-VISUAL-")
        )
        self.assertEqual(len(visual_ids), 7)
        for requirement_id in visual_ids:
            self.assertIn(
                "target-evidence", requirements[requirement_id].required_evidence
            )
            self.assertIn(
                "real-project", requirements[requirement_id].required_evidence
            )

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
