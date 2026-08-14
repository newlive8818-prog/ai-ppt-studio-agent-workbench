"""Compile bounded, reproducible schema 3 Context Packs for Agent tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_ppt_studio.errors import ArtifactReferenceError, WorkbenchValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel
from ai_ppt_studio.role_registry import RoleRegistry
from ai_ppt_studio.scenario_packs import ScenarioPackRegistry
from ai_ppt_studio.application.mission_readiness import MissionReadinessPolicy
from ai_ppt_studio.application.content_action_policy import (
    BATCH_APPLY_ACTIONS,
    BATCH_PLAN_ACTIONS,
    CONTENT_ACTIONS,
    FRAMEWORK_ACTIONS,
    FULL_DECK_CONTENT_ACTIONS,
    content_action_contract,
    validate_content_action_targets,
)


FOUR_TARGETS = (
    "macos-powerpoint",
    "macos-wps",
    "windows-powerpoint",
    "windows-wps",
)

class ContextCompiler:
    """Build the minimum governed context required by one formal role task."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def compile_role_task(
        self,
        *,
        role_id: str,
        task_type: str,
        project_revision: int,
        target_refs: list[str],
        instructions: str,
        experience_slice_ref: str = "",
        failure_conditions: list[str] | None = None,
        preserve_refs: list[str] | None = None,
        last_valid_result_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self.kernel.load()
        if state.revision != project_revision:
            raise WorkbenchValidationError(
                "Context Pack project_revision must equal the current revision"
            )
        role = RoleRegistry.default().get(role_id)
        action_contract = content_action_contract(task_type)
        if action_contract is not None:
            if role_id != action_contract.role_id:
                raise WorkbenchValidationError(
                    "Context Pack role does not match content action policy"
                )
            validate_content_action_targets(
                task_type, target_refs, state.artifact_heads
            )
        if task_type in FRAMEWORK_ACTIONS:
            MissionReadinessPolicy(self.kernel).require_ready()
        elif task_type in (
            FULL_DECK_CONTENT_ACTIONS
            | BATCH_PLAN_ACTIONS
            | BATCH_APPLY_ACTIONS
        ):
            from ai_ppt_studio.application.content_service import (
                require_full_deck_expansion_authorization,
            )

            require_full_deck_expansion_authorization(self.kernel)
        pack = ScenarioPackRegistry.default().resolve(
            scene="presales", task_type="reading-first"
        )
        experience_ref = experience_slice_ref.strip() or self._current_slice(
            role_id, task_type
        )
        experience_slice = self._experience_slice(
            experience_ref, role_id, task_type
        )
        project_manifest = self._optional_payload(
            "project/manifest", "project-manifest"
        )
        mission = self._optional_payload("mission/draft", "mission-draft")
        materials = self._optional_payload("materials", "material-inventory")
        mission_identity = MissionReadinessPolicy(self.kernel).projection()
        source_rows = materials.get("sources") if materials else []
        sources = source_rows if isinstance(source_rows, list) else []
        production_route = (
            "strict-B"
            if role.role_group in {"visual", "delivery"}
            or "strict-B" in role.tags
            else "content-first"
        )
        if task_type == "generate-image-assets":
            self._require_frozen_native_first()
        target_contract: dict[str, Any] = {
            "required": False,
            "targets": [],
            "same_pptx_sha256_required": False,
        }
        if task_type in {"verify-target-render", "coordinate-delivery"}:
            target_contract = {
                "required": True,
                "targets": list(FOUR_TARGETS),
                "same_pptx_sha256_required": True,
                "desktop_evidence_only": True,
                "preflight_evidence_forbidden": True,
            }
        repair = task_type in {"repair-content", "govern-feedback"}
        repair_contract = {
            "required": repair,
            "failure_conditions": list(failure_conditions or []),
            "preserve_refs": list(preserve_refs or []),
            "last_valid_result_refs": list(last_valid_result_refs or []),
            "whole_project_rewrite_forbidden": repair,
        }
        content_workflow = {
            "framework_ref": state.artifact_heads.get(
                "content/framework-draft", ""
            ),
            "framework_confirmation_ref": state.artifact_heads.get(
                "content/framework-confirmation", ""
            ),
            "full_deck_expansion_authorization_ref": state.artifact_heads.get(
                "content/full-deck-expansion-authorization", ""
            ),
            "review_batch_ref": state.artifact_heads.get(
                "content/review-batch", ""
            ),
            "batch_revision_plan_ref": state.artifact_heads.get(
                "content/batch-revision-plan", ""
            ),
            "batch_plan_confirmation_ref": state.artifact_heads.get(
                "content/batch-plan-confirmation", ""
            ),
        }
        if action_contract is not None:
            workflow_keys_by_slot = {
                "content/framework-draft": "framework_ref",
                "content/framework-confirmation": "framework_confirmation_ref",
                "content/full-deck-expansion-authorization": (
                    "full_deck_expansion_authorization_ref"
                ),
                "content/review-batch": "review_batch_ref",
                "content/batch-revision-plan": "batch_revision_plan_ref",
                "content/batch-plan-confirmation": "batch_plan_confirmation_ref",
            }
            visible_workflow_keys = {
                workflow_keys_by_slot[slot]
                for slot in action_contract.workflow_slots
            }
            content_workflow = {
                key: value if key in visible_workflow_keys else ""
                for key, value in content_workflow.items()
            }
        active_head_slots = (
            set(action_contract.active_head_slots)
            if action_contract is not None
            else None
        )
        return {
            "schema_version": "3.0",
            "project_id": state.project_id,
            "project_revision": project_revision,
            "artifact_version_refs": list(target_refs),
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "layers": {
                "governance": {
                    "stable_governance_version": "ai-ppt-governance/v1.6",
                    "production_route": production_route,
                    "content_before_visual": True,
                    "immutable_references_required": True,
                    "hidden_reasoning_persistence_forbidden": True,
                    "gates": {
                        "G0": "user-chat-confirmed",
                        "G1": "internal-binary",
                        "G2": "internal-binary-four-target",
                        "G3": "user-chat-confirmed",
                        "G4": "user-chat-confirmed-four-target",
                    },
                },
                "scenario_pack": {
                    "pack_id": pack.pack_id,
                    "version": "1.0",
                    "scene": pack.scene,
                    "task_type": pack.task_type,
                    "display_name": pack.display_name,
                },
                "role_contract": {
                    "role_id": role.role_id,
                    "display_name": role.display_name,
                    "version": f"role-contract/{role.role_id}/v1",
                    "authority": role.authority,
                    "isolation_group": role.isolation_group,
                    "can_self_approve": role.can_self_approve,
                    "can_release_gate": role.can_release_gate,
                },
                "task_contract": {
                    "task_type": task_type,
                    "version": f"task-contract/{task_type}/v1",
                    "target_refs": list(target_refs),
                    "instructions": instructions.strip()[:2000],
                    "expected_deliverable": "governed-content-addressed-artifact",
                },
                "current_state": {
                    "revision": state.revision,
                    "gate_status": dict(state.gate_status),
                    "active_head_refs": {
                        key: value
                        for key, value in state.artifact_heads.items()
                        if (
                            key in active_head_slots
                            if active_head_slots is not None
                            else (
                                key in {
                                    "mission/draft",
                                    "mission/confirmation",
                                    "materials",
                                    "human/decision/latest",
                                }
                                or key.startswith("content/")
                                or key.startswith("visual/")
                                or key.startswith("delivery/")
                            )
                        )
                    },
                },
                "project_facts": {
                    "project_name": str(project_manifest.get("name") or state.project_id),
                    "scenario_pack": str(
                        project_manifest.get("scenario_pack")
                        or "reading-first-presales"
                    ),
                    "mission": {
                        key: mission[key]
                        for key in (
                            "topic",
                            "primary_audience",
                            "desired_judgment_or_action",
                        )
                        if key in mission
                    },
                    "mission_identity": mission_identity,
                    "material_summary": {
                        "count": len(sources),
                        "sources": [
                            {
                                key: item.get(key)
                                for key in ("source_id", "kind", "sha256", "locator")
                                if item.get(key)
                            }
                            for item in sources
                            if isinstance(item, dict)
                        ],
                    },
                },
                "content_workflow": content_workflow,
                "experience_slice": experience_slice,
                "repair_contract": repair_contract,
                "target_render_contract": target_contract,
                "tool_contract": {
                    "writeback": "commit through schema 3 MCP/runtime only",
                    "image_2": (
                        "nonsemantic-assets-after-frozen-native-first-only"
                        if task_type == "generate-image-assets"
                        else "not-authorized-by-this-task"
                    ),
                    "pptx": "Codex Presentations only",
                },
                "output_contract": {
                    "format": "governed-artifact",
                    "reference_format": "artifact://<kind>/<sha256>",
                    "must_be_immutable": True,
                    "binary_gate_required": role.authority == "reviewer",
                    "preserve_unchanged_refs": True,
                },
                "exclusions": self._exclusions(role.authority, role.role_group),
            },
        }

    def _payload(self, slot: str, kind: str) -> dict[str, Any]:
        value = self.kernel.load().artifact_heads.get(slot)
        if not value:
            raise ArtifactReferenceError(f"Required artifact head is missing: {slot}")
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(f"Unexpected artifact kind for {slot}")
        return dict(self.kernel.artifacts.resolve(reference)["payload"])

    def _optional_payload(self, slot: str, kind: str) -> dict[str, Any]:
        value = self.kernel.load().artifact_heads.get(slot)
        if not value:
            return {}
        reference = ArtifactReference.parse(value)
        if reference.kind != kind:
            raise ArtifactReferenceError(f"Unexpected artifact kind for {slot}")
        return dict(self.kernel.artifacts.resolve(reference)["payload"])

    def _current_slice(self, role_id: str, task_type: str) -> str:
        state = self.kernel.load()
        exact = state.artifact_heads.get(
            f"experience/slice/{role_id}/{task_type}"
        )
        return str(exact or "")

    def _experience_slice(
        self, value: str, role_id: str, task_type: str
    ) -> dict[str, Any]:
        if not value:
            return {
                "slice_refs": [],
                "status": "not-available",
                "target_role_id": role_id,
                "task_type": task_type,
            }
        reference = ArtifactReference.parse(value)
        if reference.kind != "role-specific-experience-slice":
            raise ArtifactReferenceError(
                "experience_slice_ref must identify a role-specific experience slice"
            )
        payload = self.kernel.artifacts.resolve(reference)["payload"]
        if payload.get("target_role_id") != role_id:
            raise ArtifactReferenceError(
                "Experience slice target role does not match the Agent task"
            )
        return {
            "slice_refs": [value],
            "status": "matched",
            "target_role_id": role_id,
            "task_type": str(payload.get("task_type") or task_type),
            "match_reasons": [
                reason
                for entry in payload.get("experience_entries", [])
                if isinstance(entry, dict)
                for reason in entry.get("match_reasons", [])
                if isinstance(reason, str)
            ],
        }

    def _require_frozen_native_first(self) -> None:
        try:
            anchor = self._payload("visual/anchors", "anchor-slide-set")
        except ArtifactReferenceError as exc:
            raise WorkbenchValidationError(
                "Image 2 assets require a frozen native-first anchor set"
            ) from exc
        if anchor.get("native_first_frozen") is not True:
            raise WorkbenchValidationError(
                "Image 2 assets require the current native-first anchor set to be frozen"
            )

    @staticmethod
    def _exclusions(authority: str, role_group: str) -> list[str]:
        exclusions = [
            "raw_feedback",
            "hidden_reasoning",
            "unrelated_project_history",
            "route-a-c-experiment-artifacts",
        ]
        if authority == "producer":
            exclusions.extend(("review_records", "sibling_reviews"))
        elif authority == "reviewer":
            exclusions.extend(
                ("producer_self_evaluation", "raw_sibling_review_opinions")
            )
        if role_group != "experience":
            exclusions.append("raw_experience_curation_workspace")
        return exclusions


__all__ = ["ContextCompiler", "FOUR_TARGETS"]
