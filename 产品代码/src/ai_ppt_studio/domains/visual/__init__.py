"""Strict-route-B visual production contracts and compilation."""

from .compilation import (
    COMPILER_VERSION,
    HANDOFF_VERSION,
    derive_visual_compilation_plan,
    validate_visual_compilation_plan,
)
from .contracts import validate_deck_design_system, validate_visual_brief

__all__ = [
    "COMPILER_VERSION",
    "HANDOFF_VERSION",
    "derive_visual_compilation_plan",
    "validate_deck_design_system",
    "validate_visual_brief",
    "validate_visual_compilation_plan",
]
