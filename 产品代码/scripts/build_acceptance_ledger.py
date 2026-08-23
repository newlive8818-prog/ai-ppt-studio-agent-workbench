"""Rebuild a version-bound acceptance ledger from its evidence index."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_ppt_studio.acceptance.ledger import (  # noqa: E402
    AcceptanceLedger,
    EvidenceIndex,
)

def build(
    *,
    ledger_path: Path | None = None,
    evidence_path: Path | None = None,
) -> tuple[AcceptanceLedger, Path]:
    target = ledger_path or ROOT / "requirements" / "v1.6-acceptance-ledger.json"
    checked_in = AcceptanceLedger.from_dict(
        json.loads(target.read_text(encoding="utf-8"))
    )
    requirements = tuple(
        replace(
            requirement,
            proof_refs=(),
            missing_evidence=(),
            status="unproven",
        )
        for requirement in checked_in.requirements
    )
    ledger = AcceptanceLedger(
        version=checked_in.version,
        requirements=requirements,
    )
    evidence = evidence_path or ROOT / "requirements" / "v1.6-evidence.json"
    if evidence.is_file():
        ledger = ledger.with_evidence(EvidenceIndex.from_path(evidence))
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
