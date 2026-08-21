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
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)
from ai_ppt_studio.application.release_policy_service import (
    ReleaseTargetPolicyService,
)

V22_CONTENT_TASK_ROLES = {
    "build-presales-evidence-book": "presales-solution-chief",
    "build-customer-decision-context": "presales-solution-chief",
    "build-problem-solution-fit": "presales-solution-chief",
    "build-reading-deck-blueprint": "presales-solution-chief",
    "repair-reading-deck-blueprint": "presales-solution-chief",
    "run-content-evidence-gate": "content-evidence-gate-reviewer",
    "run-content-presales-reading-gate": "content-presales-reading-gate-reviewer",
}
V22_CONTENT_OUTPUT_KINDS = {
    "build-presales-evidence-book": "presales-evidence-book",
    "build-customer-decision-context": "customer-decision-context",
    "build-problem-solution-fit": "problem-solution-fit-map",
    "build-reading-deck-blueprint": "reading-deck-blueprint",
    "repair-reading-deck-blueprint": "reading-deck-blueprint",
    "run-content-evidence-gate": "content-hard-gate-record",
    "run-content-presales-reading-gate": "content-hard-gate-record",
}

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
        experience_type_signature: str = "",
        experience_applicability: dict[str, Any] | None = None,
        experience_limit: int = 8,
    ) -> dict[str, Any]:
        state = self.kernel.load()
        if state.revision != project_revision:
            raise WorkbenchValidationError(
                "Context Pack project_revision must equal the current revision"
            )
        role = RoleRegistry.default().get(role_id)
        if task_type in V22_CONTENT_TASK_ROLES:
            return self._compile_v22_content_task(
                role=role,
                role_id=role_id,
                task_type=task_type,
                project_revision=project_revision,
                target_refs=target_refs,
                instructions=instructions,
                experience_type_signature=experience_type_signature,
                experience_applicability=experience_applicability,
                experience_limit=experience_limit,
            )
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
            policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
            target_contract = {
                "required": True,
                "release_target_policy_ref": policy_ref,
                "required_target_ids": list(policy.required_target_ids),
                "deferred_target_ids": list(policy.deferred_target_ids),
                "targets": list(policy.required_target_ids),
                "same_pptx_sha256_required": True,
                "desktop_evidence_only": True,
                "preflight_evidence_forbidden": True,
                "deferred_compatibility_claims_forbidden": True,
            }
        repair = task_type in {"repair-content", "govern-feedback"}
        repair_contract = {
            "required": repair,
            "failure_conditions": list(failure_conditions or []),
            "preserve_refs": list(preserve_refs or []),
            "last_valid_result_refs": list(last_valid_result_refs or []),
            "whole_project_rewrite_forbidden": repair,
        }
        content_review = {
            "reading_blueprint_ref": state.artifact_heads.get(
                "content/reading-blueprint", ""
            ),
            "review_batch_ref": state.artifact_heads.get(
                "content/review-batch", ""
            ),
            "revision_plan_ref": state.artifact_heads.get(
                "content/revision-plan", ""
            ),
        }
        return {
            "schema_version": "3.0",
            "project_id": state.project_id,
            "project_revision": project_revision,
            "artifact_version_refs": list(target_refs),
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "layers": {
                "governance": {
                    "stable_governance_version": "ai-ppt-governance/v2.2",
                    "production_route": production_route,
                    "content_before_visual": True,
                    "immutable_references_required": True,
                    "hidden_reasoning_persistence_forbidden": True,
                    "gates": {
                        "G0": "user-chat-confirmed",
                        "G1": "internal-binary",
                        "G2": "internal-binary-release-target",
                        "G3": "user-chat-confirmed",
                        "G4": "user-chat-confirmed-release-target",
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
                "content_review": content_review,
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

    def _compile_v22_content_task(
        self,
        *,
        role: Any,
        role_id: str,
        task_type: str,
        project_revision: int,
        target_refs: list[str],
        instructions: str,
        experience_type_signature: str,
        experience_applicability: dict[str, Any] | None,
        experience_limit: int,
    ) -> dict[str, Any]:
        expected_role = V22_CONTENT_TASK_ROLES[task_type]
        if role_id != expected_role:
            raise WorkbenchValidationError(
                "Context Pack role does not match the v2.2 content task"
            )
        state = self.kernel.load()
        current_refs = set(state.artifact_heads.values())
        if any(reference not in current_refs for reference in target_refs):
            raise ArtifactReferenceError(
                "v2.2 content context accepts current artifact references only"
            )
        reviewer = role.authority == "reviewer"
        if not isinstance(experience_limit, int) or isinstance(
            experience_limit, bool
        ) or not 1 <= experience_limit <= 50:
            raise WorkbenchValidationError(
                "experience_limit must be an integer from 1 to 50"
            )
        recommendations: list[dict[str, Any]] = []
        if experience_type_signature.strip():
            from ai_ppt_studio.application.experience_service import (
                ExperienceService,
            )

            recommendations = ExperienceService(self.kernel).recommend(
                domain="content",
                type_signature=experience_type_signature.strip(),
                applicability=dict(experience_applicability or {}),
                top_n=experience_limit,
            )
        experience_slice = {
            "status": "available" if recommendations else "not-available",
            "layers": ["same-type", "global"],
            "domain": "content",
            "type_signature": experience_type_signature.strip(),
            "limit": experience_limit,
            "items": recommendations,
        }
        return {
            "schema_version": "3.0",
            "project_id": state.project_id,
            "project_revision": project_revision,
            "artifact_version_refs": list(target_refs),
            "compiled_at": datetime.now(timezone.utc).isoformat(),
            "layers": {
                "governance": {
                    "stable_governance_version": "ai-ppt-governance/v2.2",
                    "production_route": "content-first",
                    "content_before_visual": True,
                    "immutable_references_required": True,
                    "hidden_reasoning_persistence_forbidden": True,
                },
                "scenario_pack": {
                    "scene": "presales",
                    "task_type": "reading-first",
                },
                "project_facts": {
                    "mission_confirmation_ref": state.artifact_heads.get(
                        "mission/confirmation", ""
                    ),
                    "material_inventory_ref": state.artifact_heads.get(
                        "materials", ""
                    ),
                },
                "role_contract": {
                    "role_id": role.role_id,
                    "display_name": role.display_name,
                    "authority": role.authority,
                    "isolation_group": role.isolation_group,
                },
                "task_contract": {
                    "task_type": task_type,
                    "instructions": instructions.strip(),
                    "reviewer_cannot_edit": reviewer,
                },
                "current_content_refs": list(target_refs),
                "experience_slice": experience_slice,
                "tool_contract": {
                    "writeback": "authoritative-runtime-only",
                    "pptx": "not-authorized-by-content-task",
                },
                "output_contract": {
                    "format": "governed-artifact",
                    "allowed_kind": V22_CONTENT_OUTPUT_KINDS[task_type],
                    "must_be_immutable": True,
                    "binary_gate_required": reviewer,
                },
                "exclusions": self._exclusions(role.authority, role.role_group),
            },
        }

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


__all__ = ["ContextCompiler"]
