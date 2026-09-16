"""Read-only adapters for historical product contracts."""

from .experience_v16 import LegacyExperienceV16Adapter
from .content_v16 import read_legacy_content
from .workspace_v16 import project_legacy_workspace

__all__ = [
    "LegacyExperienceV16Adapter",
    "project_legacy_workspace",
    "read_legacy_content",
]
