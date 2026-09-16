"""Generate the checked-in v2.3 acceptance ledger from current baselines."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (  # noqa: E402
    AcceptanceLedger,
    EvidenceIndex,
    extract_numbered_requirements,
)

SOURCES = (
    (PROJECT / "01-产品需求基线-v1.0.md", "PRD", "验收标准"),
    (PROJECT / "02-系统详细设计-v1.0.md", "SDD", "测试策略"),
    (PROJECT / "03-UI设计与交互规范-v1.0.md", "UI", "UI 验收"),
)
LEDGER_VERSION = "2.3"


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


def build() -> tuple[AcceptanceLedger, Path]:
    requirements = authoritative_requirements()
    evidence_path = ROOT / "requirements" / "v2.3-evidence.json"
    if not evidence_path.is_file():
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(
                {"schema_version": "1.0", "proofs": []},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    ledger = AcceptanceLedger(
        version=LEDGER_VERSION,
        requirements=requirements,
    ).with_evidence(EvidenceIndex.from_path(evidence_path))
    target = ROOT / "requirements" / "v2.3-acceptance-ledger.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(ledger.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return ledger, target


if __name__ == "__main__":
    generated, output = build()
    print(f"wrote {len(generated.requirements)} requirements to {output}")
