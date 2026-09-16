"""Shared current-head invalidation rules for v2.3 visual lineage."""

from __future__ import annotations

from typing import Mapping


VISUAL_REVIEW_SESSION_SLOT = "review/session/visual-professional"


def visual_downstream_slots(
    heads: Mapping[str, str], *, keep: set[str]
) -> tuple[str, ...]:
    """Return visual and delivery heads that are stale after an upstream change."""

    return tuple(
        sorted(
            slot
            for slot in heads
            if (
                slot.startswith("visual/")
                or slot.startswith("delivery/")
                or slot == VISUAL_REVIEW_SESSION_SLOT
            )
            and slot != "delivery/build"
            and slot not in keep
        )
    )


__all__ = ["VISUAL_REVIEW_SESSION_SLOT", "visual_downstream_slots"]
