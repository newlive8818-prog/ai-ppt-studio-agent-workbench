"""Complete content review projection and revision-safe mark persistence."""

from __future__ import annotations

import copy
import re
from typing import Any

from ai_ppt_studio.errors import (
    ContractValidationError,
    ReviewSourceStaleError,
)
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.state import KernelState
from ai_ppt_studio.kernel.transactions import ProjectKernel


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9一-鿿]+", "-", str(value).lower()).strip("-")
    return text or "field"


def _plain_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(_plain_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_plain_text(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class ReviewService:
    """Project the authoritative content blueprint and save its exact marks."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def content_projection(self) -> dict[str, Any]:
        state = self.kernel.load()
        source_version = state.artifact_heads.get("content/blueprint")
        if not source_version:
            raise ContractValidationError("No user-reviewable content blueprint")
        reference = ArtifactReference.parse(source_version)
        if reference.kind != "content-blueprint":
            raise ContractValidationError("Content blueprint head has the wrong kind")
        payload = copy.deepcopy(self.kernel.artifacts.resolve(reference)["payload"])
        sections = self._sections(payload)
        project_name = self._project_name(state)
        return {
            "review_type": "content",
            "display_policy": "professional-review",
            "project_id": state.project_id,
            "project_name": project_name,
            "title": str(payload.get("title") or project_name),
            "revision": state.revision,
            "source_version": source_version,
            "source_refs": [source_version],
            "status": payload.get("status"),
            "gate_status": {"G0": state.gate_status.get("G0", "locked")},
            "sections": sections,
            "outline": [
                {"anchor": item["anchor"], "title": item["title"]}
                for item in sections
            ],
            "mark_set": self._current_mark_set(
                state, "content", source_version
            ),
        }

    def visual_projection(self) -> dict[str, Any]:
        state = self.kernel.load()
        source_version = state.artifact_heads.get("visual/contract")
        if not source_version:
            raise ContractValidationError("No user-reviewable visual contract")
        reference = ArtifactReference.parse(source_version)
        if reference.kind != "visual-contract":
            raise ContractValidationError("Visual contract head has the wrong kind")
        payload = copy.deepcopy(self.kernel.artifacts.resolve(reference)["payload"])
        sections = self._visual_sections(payload)
        project_name = self._project_name(state)
        design_system = payload.get("deck_design_system")
        design_system_row = (
            design_system if isinstance(design_system, dict) else {}
        )
        return {
            "review_type": "visual",
            "display_policy": "professional-review",
            "project_id": state.project_id,
            "project_name": project_name,
            "title": str(
                design_system_row.get("theme_proposition") or project_name
            ),
            "revision": state.revision,
            "source_version": source_version,
            "source_refs": [source_version],
            "status": payload.get("status"),
            "gate_status": {
                gate: state.gate_status.get(gate, "locked")
                for gate in ("G1", "G2", "G3")
            },
            "sections": sections,
            "outline": [
                {"anchor": item["anchor"], "title": item["title"]}
                for item in sections
            ],
            "mark_set": self._current_mark_set(
                state, "visual", source_version
            ),
        }

    def save_marks(
        self,
        *,
        command_id: str,
        expected_revision: int,
        source_version: str,
        marks: list[dict[str, Any]],
        review_type: str = "content",
    ) -> KernelState:
        if review_type not in {"content", "visual"}:
            raise ContractValidationError("review_type must be content or visual")
        state = self.kernel.load()
        source_slot = (
            "content/blueprint" if review_type == "content" else "visual/contract"
        )
        current_source = state.artifact_heads.get(source_slot, "")
        if source_version != current_source:
            raise ReviewSourceStaleError(source_version, current_source)
        projection = (
            self.content_projection()
            if review_type == "content"
            else self.visual_projection()
        )
        normalized = self._normalize_marks(marks, projection)
        current = projection["mark_set"]
        merged = {
            item["mark_id"]: dict(item) for item in current.get("marks", [])
        }
        for item in normalized:
            merged[item["mark_id"]] = item
        payload = {
            "project_id": state.project_id,
            "review_type": review_type,
            "source_version": source_version,
            "revision": int(current.get("revision", 0)) + 1,
            "status": "pending-governance",
            "marks": list(merged.values()),
        }
        return self.kernel.commit(
            command_id=command_id,
            expected_revision=expected_revision,
            event_type=f"review.{review_type}-marks.saved",
            artifact_updates={
                f"review-marks/{review_type}": ("review-mark-set", payload)
            },
        )

    def _current_mark_set(
        self, state: KernelState, review_type: str, source_version: str
    ) -> dict[str, Any]:
        mark_ref = state.artifact_heads.get(f"review-marks/{review_type}")
        if mark_ref:
            payload = self.kernel.artifacts.resolve(
                ArtifactReference.parse(mark_ref)
            )["payload"]
            if payload.get("source_version") == source_version:
                return copy.deepcopy(payload)
        return {
            "project_id": state.project_id,
            "review_type": review_type,
            "source_version": source_version,
            "revision": 0,
            "status": "draft",
            "marks": [],
        }

    def _project_name(self, state: KernelState) -> str:
        mission_ref = state.artifact_heads.get("mission/draft", "")
        if not mission_ref:
            return state.project_id
        reference = ArtifactReference.parse(mission_ref)
        if reference.kind != "mission-draft":
            return state.project_id
        payload = self.kernel.artifacts.resolve(reference).get("payload")
        if not isinstance(payload, dict):
            return state.project_id
        return str(payload.get("topic") or state.project_id)

    @staticmethod
    def _sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        overview = {
            key: copy.deepcopy(value)
            for key, value in payload.items()
            if key != "slides"
        }
        sections.append(
            {
                "anchor": "content-overview",
                "title": "整套内容与论证结构",
                "fields": [
                    {
                        "anchor": f"content-{_slug(key)}",
                        "label": key,
                        "value": value,
                    }
                    for key, value in overview.items()
                ],
            }
        )
        for index, slide in enumerate(payload.get("slides") or [], start=1):
            if not isinstance(slide, dict):
                raise ContractValidationError("Blueprint slides must be objects")
            slide_id = _slug(slide.get("slide_id") or index)
            anchor = f"slide-{slide_id}"
            sections.append(
                {
                    "anchor": anchor,
                    "title": f"第 {index} 页 · {slide.get('title') or slide_id}",
                    "fields": [
                        {
                            "anchor": f"{anchor}-{_slug(key)}",
                            "label": key,
                            "value": copy.deepcopy(value),
                        }
                        for key, value in slide.items()
                    ],
                }
            )
        return sections

    @staticmethod
    def _visual_sections(payload: dict[str, Any]) -> list[dict[str, Any]]:
        framework = {
            key: copy.deepcopy(value)
            for key, value in payload.items()
            if key not in {"deck_design_system", "slide_contracts"}
        }
        evidence_identity_fields = (
            "target_id",
            "operating_system",
            "operating_system_version",
            "application",
            "application_version",
            "font_inventory_ref",
            "font_substitution_plan_ref",
            "source_pptx_ref",
            "pptx_sha256",
            "overall_result",
            "evidence_ref",
        )
        evidence_rows = framework.get("target_evidence_identities")
        if isinstance(evidence_rows, list):
            framework["target_evidence_identities"] = [
                {
                    key: copy.deepcopy(item.get(key))
                    for key in evidence_identity_fields
                }
                for item in evidence_rows
                if isinstance(item, dict)
            ]
        design_system = payload.get("deck_design_system")
        design_system_row = (
            copy.deepcopy(design_system)
            if isinstance(design_system, dict)
            else {}
        )
        sections: list[dict[str, Any]] = [
            {
                "anchor": "visual-framework",
                "title": "整套视觉框架",
                "fields": [
                    {
                        "anchor": f"visual-framework-{_slug(key)}",
                        "label": key,
                        "value": value,
                    }
                    for key, value in framework.items()
                ],
            },
            {
                "anchor": "deck-design-system",
                "title": "Deck Design System",
                "fields": [
                    {
                        "anchor": f"deck-design-system-{_slug(key)}",
                        "label": key,
                        "value": value,
                    }
                    for key, value in design_system_row.items()
                ],
            },
        ]
        for index, contract in enumerate(
            payload.get("slide_contracts") or [], start=1
        ):
            if not isinstance(contract, dict):
                raise ContractValidationError("Visual slide contracts must be objects")
            slide_id = _slug(contract.get("slide_id") or index)
            anchor = f"visual-slide-{slide_id}"
            sections.append(
                {
                    "anchor": anchor,
                    "title": f"第 {index} 页视觉合同 · {contract.get('title') or slide_id}",
                    "fields": [
                        {
                            "anchor": f"{anchor}-{_slug(key)}",
                            "label": key,
                            "value": copy.deepcopy(value),
                        }
                        for key, value in contract.items()
                    ],
                }
            )
        return sections

    @staticmethod
    def _normalize_marks(
        marks: list[dict[str, Any]], projection: dict[str, Any]
    ) -> list[dict[str, str]]:
        if not isinstance(marks, list) or not marks:
            raise ContractValidationError("At least one review mark is required")
        anchor_text: dict[str, str] = {}
        for section in projection["sections"]:
            field_texts: list[str] = []
            for field in section["fields"]:
                text = _plain_text(field.get("value"))
                anchor_text[field["anchor"]] = text
                field_texts.append(text)
            anchor_text[section["anchor"]] = "\n".join(field_texts)
        normalized: list[dict[str, str]] = []
        seen: set[str] = set()
        for mark in marks:
            if not isinstance(mark, dict):
                raise ContractValidationError("Review marks must be objects")
            item = {
                "mark_id": str(mark.get("mark_id") or "").strip(),
                "field_anchor": str(
                    mark.get("field_anchor") or ""
                ).strip(),
                "exact_text": str(mark.get("exact_text") or ""),
                "prefix": str(mark.get("prefix") or ""),
                "suffix": str(mark.get("suffix") or ""),
                "comment": str(mark.get("comment") or "").strip(),
            }
            if (
                not item["mark_id"]
                or item["mark_id"] in seen
                or item["field_anchor"] not in anchor_text
                or not item["comment"]
            ):
                raise ContractValidationError(
                    "Review mark ID, current anchor, and comment are required"
                )
            exact = item["exact_text"]
            if exact:
                source_text = anchor_text[item["field_anchor"]]
                positions: list[int] = []
                cursor = 0
                while True:
                    position = source_text.find(exact, cursor)
                    if position < 0:
                        break
                    positions.append(position)
                    cursor = position + max(1, len(exact))
                if not positions:
                    raise ContractValidationError(
                        "Selected review text is not present at the current anchor"
                    )
                prefix = item["prefix"]
                suffix = item["suffix"]
                matching = [
                    position
                    for position in positions
                    if (
                        not prefix
                        or source_text[:position].rstrip().endswith(
                            prefix.rstrip()
                        )
                    )
                    and (
                        not suffix
                        or source_text[position + len(exact) :]
                        .lstrip()
                        .startswith(suffix.lstrip())
                    )
                ]
                if len(positions) > 1 and not prefix and not suffix:
                    raise ContractValidationError(
                        "Duplicate exact review text requires prefix/suffix context"
                    )
                if len(matching) != 1:
                    raise ContractValidationError(
                        "Review quote context does not identify one occurrence"
                    )
            seen.add(item["mark_id"])
            normalized.append(item)
        return normalized
