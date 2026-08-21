"""Generate the checked-in v2.2 acceptance ledger from authoritative baselines."""

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


def build() -> tuple[AcceptanceLedger, Path]:
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

    ledger = AcceptanceLedger(version="2.2", requirements=tuple(requirements))
    evidence_path = ROOT / "requirements" / "v2.2-evidence.json"
    if evidence_path.is_file():
        ledger = ledger.with_evidence(EvidenceIndex.from_path(evidence_path))
    target = ROOT / "requirements" / "v2.2-acceptance-ledger.json"
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
