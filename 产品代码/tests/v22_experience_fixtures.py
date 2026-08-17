from __future__ import annotations

from copy import deepcopy


def experience_item(
    *,
    experience_id: str = "exp-reading-path",
    layer: str = "same-type",
    domain: str = "content",
    type_signature: str = "presales:transport:decision",
) -> dict[str, object]:
    return {
        "experience_id": experience_id,
        "version": 1,
        "layer": layer,
        "domain": domain,
        "result_type": "mechanism",
        "mechanism": "先呈现来源事实，再呈现诊断假设与验证动作。",
        "type_signature": type_signature,
        "applicability": {
            "scenes": ["售前解决方案"],
            "audiences": ["客户决策团队"],
            "slide_tasks": ["问题诊断"],
            "conditions": ["阅读优先"],
        },
        "counterexamples": [],
        "failure_boundaries": ["不适用于纯品牌展示"],
        "source_project_ids": ["project-source"],
        "source_refs": ["artifact://content-review-batch/" + "a" * 64],
        "before_after_refs": [
            {
                "before_ref": "artifact://reading-deck-blueprint/" + "b" * 64,
                "after_ref": "artifact://reading-deck-blueprint/" + "c" * 64,
            }
        ],
        "hard_gate_refs": ["artifact://content-hard-gate-record/" + "d" * 64],
        "user_outcomes": [
            {
                "project_id": "project-source",
                "type_signature": type_signature,
                "outcome": "accepted",
                "evidence_ref": "host-message://accepted-feedback-1",
            }
        ],
        "application_count": 0,
        "success_type_signatures": [type_signature],
        "failure_type_signatures": [],
        "excluded_type_signatures": [],
        "sanitized_for_reuse": True,
        "privacy": {
            "contains_client_identifiers": False,
            "contains_client_facts": False,
            "contains_client_assets": False,
            "reuse_scope": "mechanism-only",
        },
        "status": "active",
        "previous_version": None,
        "previous_version_ref": None,
        "rollback_from_version": None,
        "updated_at": "2026-08-15T00:00:00+08:00",
    }


def clone_item(**changes: object) -> dict[str, object]:
    payload = deepcopy(experience_item())
    payload.update(changes)
    return payload
