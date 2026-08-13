"""Single governed target and visibility policy for formal content actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ai_ppt_studio.errors import ContentWorkflowError
from ai_ppt_studio.kernel.references import ArtifactReference


LINEAGE_SLOTS = (
    "content/framework-draft",
    "content/framework-confirmation",
    "content/full-deck-expansion-authorization",
)
MISSION_SLOTS = ("mission/draft", "mission/confirmation")
REVIEW_SLOTS = (
    "content/review/presales-reviewer",
    "content/review/decision-maker-reviewer",
    "content/review/evidence-reviewer",
    "content/review/narrative-reviewer",
    "content/review/editorial-reviewer",
)
SLOT_KINDS = {
    "mission/draft": "mission-draft",
    "mission/confirmation": "mission-confirmation",
    "materials": "material-inventory",
    "content/framework-draft": "content-framework-draft",
    "content/framework-confirmation": "content-framework-confirmation",
    "content/full-deck-expansion-authorization": (
        "full-deck-expansion-authorization"
    ),
    "content/strategy": "presales-content-strategy",
    "content/claim-map": "claim-evidence-map",
    "content/argument-map": "deck-argument-map",
    "content/draft": "slide-draft-set",
    **{slot: "content-review-record" for slot in REVIEW_SLOTS},
}


@dataclass(frozen=True)
class ContentActionContract:
    action: str
    role_id: str
    required_slots: tuple[str, ...]
    optional_slots: tuple[str, ...] = ()
    active_head_slots: tuple[str, ...] = ()
    unavailable: bool = False

    def exact_target_slots(self, heads: Mapping[str, str]) -> tuple[str, ...]:
        missing = [slot for slot in self.required_slots if not heads.get(slot)]
        if missing:
            raise ContentWorkflowError(
                "CONTENT_REVIEW_CONFLICT",
                "Content action prerequisites are incomplete",
                {"action_type": self.action, "missing_slots": missing},
            )
        return (
            *self.required_slots,
            *(slot for slot in self.optional_slots if heads.get(slot)),
        )


def _contract(
    action: str,
    role_id: str,
    required: tuple[str, ...],
    *,
    optional: tuple[str, ...] = (),
    active: tuple[str, ...] | None = None,
    unavailable: bool = False,
) -> ContentActionContract:
    target_slots = (*required, *optional)
    return ContentActionContract(
        action=action,
        role_id=role_id,
        required_slots=required,
        optional_slots=optional,
        active_head_slots=active if active is not None else target_slots,
        unavailable=unavailable,
    )


CONTENT_ACTION_CONTRACTS = {
    "build-content-framework": _contract(
        "build-content-framework",
        "presales-content-strategist",
        MISSION_SLOTS,
        optional=("materials", "content/framework-draft"),
    ),
    "expand-full-content-blueprint": _contract(
        "expand-full-content-blueprint",
        "deck-narrative-architect",
        LINEAGE_SLOTS,
    ),
    "build-presales-strategy": _contract(
        "build-presales-strategy",
        "presales-content-strategist",
        (*MISSION_SLOTS, *LINEAGE_SLOTS),
        optional=("materials",),
    ),
    "build-claim-evidence-map": _contract(
        "build-claim-evidence-map",
        "claim-evidence-analyst",
        (*LINEAGE_SLOTS, "content/strategy"),
        optional=("materials",),
    ),
    "build-deck-argument-map": _contract(
        "build-deck-argument-map",
        "deck-narrative-architect",
        (*LINEAGE_SLOTS, "content/strategy", "content/claim-map"),
    ),
    "build-slide-draft-set": _contract(
        "build-slide-draft-set",
        "slide-copywriter",
        (
            *LINEAGE_SLOTS,
            "content/strategy",
            "content/claim-map",
            "content/argument-map",
        ),
    ),
    "repair-content": _contract(
        "repair-content",
        "content-repair-specialist",
        (*LINEAGE_SLOTS, "content/draft"),
    ),
    "review-content-presales": _contract(
        "review-content-presales",
        "presales-content-reviewer",
        (*LINEAGE_SLOTS, "content/draft"),
    ),
    "review-content-decision-maker": _contract(
        "review-content-decision-maker",
        "audience-decision-reviewer",
        (*LINEAGE_SLOTS, "content/draft"),
    ),
    "review-content-evidence": _contract(
        "review-content-evidence",
        "content-fact-checker",
        (*LINEAGE_SLOTS, "content/draft"),
        optional=("materials",),
    ),
    "review-content-narrative": _contract(
        "review-content-narrative",
        "argument-logic-reviewer",
        (*LINEAGE_SLOTS, "content/draft"),
    ),
    "review-content-editorial": _contract(
        "review-content-editorial",
        "reading-experience-reviewer",
        (*LINEAGE_SLOTS, "content/draft"),
    ),
    "aggregate-content-reviews": _contract(
        "aggregate-content-reviews",
        "deck-coherence-editor",
        (*LINEAGE_SLOTS, "content/draft", *REVIEW_SLOTS),
    ),
    "propose-content-batch-revision-plan": _contract(
        "propose-content-batch-revision-plan",
        "deck-coherence-editor",
        (),
        unavailable=True,
    ),
    "apply-content-batch-revision": _contract(
        "apply-content-batch-revision",
        "content-repair-specialist",
        (),
        unavailable=True,
    ),
}

FRAMEWORK_ACTIONS = frozenset({"build-content-framework"})
BATCH_PLAN_ACTIONS = frozenset({"propose-content-batch-revision-plan"})
BATCH_APPLY_ACTIONS = frozenset({"apply-content-batch-revision"})
FULL_DECK_CONTENT_ACTIONS = frozenset(CONTENT_ACTION_CONTRACTS) - (
    FRAMEWORK_ACTIONS | BATCH_PLAN_ACTIONS | BATCH_APPLY_ACTIONS
)
CONTENT_ACTIONS = frozenset(CONTENT_ACTION_CONTRACTS) - FRAMEWORK_ACTIONS


def content_action_contract(action: str) -> ContentActionContract | None:
    return CONTENT_ACTION_CONTRACTS.get(action)


def validate_content_action_targets(
    action: str,
    target_refs: list[str],
    heads: Mapping[str, str],
) -> ContentActionContract:
    contract = CONTENT_ACTION_CONTRACTS[action]
    if contract.unavailable:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            "Batch content actions are unavailable until governed contracts exist",
            {"action_type": action},
        )
    slots = contract.exact_target_slots(heads)
    expected = [heads[slot] for slot in slots]
    if len(target_refs) != len(set(target_refs)) or set(target_refs) != set(expected):
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            "Content action targets must equal the exact current policy set",
            {
                "action_type": action,
                "required_target_refs": expected,
                "actual_target_refs": list(target_refs),
            },
        )
    wrong_kinds = {
        slot: {
            "expected": SLOT_KINDS[slot],
            "actual": ArtifactReference.parse(heads[slot]).kind,
        }
        for slot in slots
        if ArtifactReference.parse(heads[slot]).kind != SLOT_KINDS[slot]
    }
    if wrong_kinds:
        raise ContentWorkflowError(
            "CONTENT_REVIEW_CONFLICT",
            "Content action targets contain an invalid artifact kind",
            {"action_type": action, "wrong_kinds": wrong_kinds},
        )
    return contract


__all__ = [
    "BATCH_APPLY_ACTIONS",
    "BATCH_PLAN_ACTIONS",
    "CONTENT_ACTIONS",
    "CONTENT_ACTION_CONTRACTS",
    "ContentActionContract",
    "FRAMEWORK_ACTIONS",
    "FULL_DECK_CONTENT_ACTIONS",
    "LINEAGE_SLOTS",
    "REVIEW_SLOTS",
    "content_action_contract",
    "validate_content_action_targets",
]
