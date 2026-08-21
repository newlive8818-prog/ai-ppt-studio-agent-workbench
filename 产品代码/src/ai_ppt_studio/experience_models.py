"""Small immutable records exposed by the shared v2.2 experience store."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ExperienceLayer(str, Enum):
    SAME_TYPE = "same-type"
    GLOBAL = "global"


class ExperienceDomain(str, Enum):
    CONTENT = "content"
    VISUAL = "visual"


class ExperienceResultType(str, Enum):
    MECHANISM = "mechanism"
    ANTI_PATTERN = "anti-pattern"
    PREFERENCE = "preference"


class ExperienceStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    RETIRED = "retired"


class EvaluationOutcome(str, Enum):
    SUCCESS = "success"
    MIXED = "mixed"
    FAILURE = "failure"


@dataclass(frozen=True)
class StoredExperience:
    experience_ref: str
    path: str
    item: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "experience_ref": self.experience_ref,
            "path": self.path,
            **deepcopy(self.item),
        }


@dataclass(frozen=True)
class StoredApplication:
    application_id: str
    experience_ref: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self.payload)


@dataclass(frozen=True)
class StoredEvaluation:
    evaluation_id: str
    application_id: str
    experience_ref: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self.payload)


__all__ = [
    "EvaluationOutcome",
    "ExperienceDomain",
    "ExperienceLayer",
    "ExperienceResultType",
    "ExperienceStatus",
    "StoredApplication",
    "StoredEvaluation",
    "StoredExperience",
]
