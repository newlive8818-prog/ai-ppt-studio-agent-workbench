from __future__ import annotations


SEMANTIC_CHECK_IDS = {
    "evidence": (
        "selective-evidence-risk",
        "unsupported-causality",
        "unsupported-capability-result-commitment",
    ),
    "presales-reading": (
        "customer-decision-position",
        "problem-completeness",
        "whole-deck-coherence-and-repetition",
        "boundary-risk-validation-next-step",
    ),
}


def semantic_checks(
    gate_type: str,
    blueprint_ref: str,
    *,
    failed_check_id: str = "",
) -> list[dict]:
    return [
        {
            "check_id": check_id,
            "applicability": "applicable",
            "result": "failed" if check_id == failed_check_id else "passed",
            "hard": True,
            "evidence_refs": [blueprint_ref],
            "failure_reason": (
                f"{check_id} requires chief repair"
                if check_id == failed_check_id
                else ""
            ),
        }
        for check_id in SEMANTIC_CHECK_IDS[gate_type]
    ]
