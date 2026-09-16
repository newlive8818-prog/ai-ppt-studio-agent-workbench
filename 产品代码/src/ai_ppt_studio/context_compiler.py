"""Compile bounded, reproducible schema 3 Context Packs for Agent tasks."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from pathlib import Path
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

from ai_ppt_studio.domains.visual.compilation import (
    COMPILER_VERSION,
    HANDOFF_VERSION,
    IMAGE_LED_COMPILER_VERSION,
    IMAGE_LED_HANDOFF_VERSION,
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
TASK_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HANDOFF_CONTENT_EXCLUSIONS = {
    "visible_copy_blocks",
    "speaker_notes",
    "facts",
    "data",
    "source_text",
    "core_claim",
    "page_title",
    "slide_order",
}
VISUAL_HANDOFF_FIELDS = {
    "task_id",
    "handoff_version",
    "compiler_version",
    "visual_compilation_plan_ref",
    "reading_blueprint_ref",
    "visual_brief_ref",
    "deck_design_system_ref",
    "visual_contract_set_ref",
    "release_target_policy_ref",
    "source_version",
    "source_revision",
    "reading_blueprint",
    "visual_brief",
    "deck_design_system",
    "slide_visual_contracts",
    "compilation_slides",
    "required_target_ids",
    "deferred_target_ids",
    "output_paths",
    "result_expected_revision",
    "authorization_scope",
    "authoring_contract",
    "evidence_contract",
}
VISUAL_HANDOFF_AUTHORIZATION_SCOPE = {
    "action_type": "build-native-first",
    "allowed_result_kind": "native-anchor-set",
    "required_anchor_count": 3,
    "authorizing_gate": "G1-passed",
    "whole_deck_build_forbidden": True,
    "gate_advance_forbidden": True,
}
VISUAL_HANDOFF_AUTHORING_CONTRACT = {
    "pptx_tool": "Codex Presentations only",
    "implementation": "@oai/artifact-tool JavaScript ES module",
    "semantic_objects_native": True,
    "whole_slide_bitmap_forbidden": True,
    "baked_factual_text_forbidden": True,
    "connectors_before_nodes": True,
    "separate_replaceable_image_layers": True,
    "target_application": "macos-powerpoint",
    "source_notes": "[Sources] blocks required in speaker notes",
}
VISUAL_HANDOFF_EVIDENCE_CONTRACT = {
    "render_every_slide": True,
    "inspect_every_slide_full_size": True,
    "montage_is_rhythm_only": True,
    "overflow_check_required": True,
    "editability_check_required": True,
    "target_powerpoint_check_separate": True,
    "user_visual_judgment_separate": True,
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
        task_id: str = "",
    ) -> dict[str, Any]:
        state = self.kernel.load()
        if state.revision != project_revision:
            raise WorkbenchValidationError(
                "Context Pack project_revision must equal the current revision"
            )
        role = RoleRegistry.default().get(role_id)
        if task_type == 'build-native-diagnostic':
            from ai_ppt_studio.application.image_led_diagnostic import ImageLedDiagnosticService
            from ai_ppt_studio.domains.materials.image_input_contracts import fail
            if role_id != 'native-first-engineer' or len(target_refs) != 2 or not task_id:
                fail('DIAGNOSTIC', 'native diagnostic needs native-first role and current selection/regions')
            service = ImageLedDiagnosticService(self.kernel)
            input_payload = service.compile_input(task_id=task_id, project_revision=project_revision, target_refs=target_refs)
            input_ref = str(self.kernel.artifacts.reference_for('image-led-native-diagnostic-input', input_payload))
            handoff = service.compile_handoff(input_payload=input_payload, diagnostic_ref=input_ref, project_revision=project_revision)
            return {
                'schema_version': '3.0', 'project_id': state.project_id,
                'project_revision': project_revision, 'artifact_version_refs': list(target_refs),
                'layers': {
                    'role_contract': {'role_id': role_id},
                    'task_contract': {'task_type': task_type, 'target_refs': list(target_refs)},
                    'image_led_diagnostic_input': {**input_payload, 'diagnostic_ref': input_ref},
                    'visual_handoff': handoff,
                    'output_contract': {'artifact_type': 'image-led-native-diagnostic-result',
                        'purpose': 'region-diagnostic', 'g1_promotion_forbidden': True},
                },
            }
        if task_type == 'generate-slide-images':
            from ai_ppt_studio.application.image_led_service import ImageLedService
            from ai_ppt_studio.domains.materials.image_input_contracts import fail, digest
            if (role_id != 'image-asset-producer' or len(target_refs) != 1
                    or not re.fullmatch(r'(?!active$)[A-Za-z0-9_-]{1,128}', task_id)):
                fail('REQUEST', 'Image 2 task needs one current pack and an exact request identity')
            service = ImageLedService(self.kernel)
            payload, binding = service.compile_request(target_refs[0], with_binding=True)
            return {
                'schema_version': '3.0', 'project_id': state.project_id,
                'project_revision': project_revision, 'artifact_version_refs': list(target_refs),
                'layers': {
                    'role_contract': {'role_id': role_id},
                    'task_contract': {'task_type': task_type, 'target_refs': list(target_refs)},
                    'image_led_request': {'request_id': task_id, **service.request_identity(target_refs[0]),
                        'payload_sha256': digest(payload), 'payload': payload,
                        **({'semantic_binding': binding} if binding is not None else {})},
                    'output_contract': {'artifact_type': 'image-led-candidate',
                        'design_authority': 'image-2', 'requires_user_selection': True},
                },
            }
        if (task_type == 'review-visual-engineering' and len(target_refs) == 1
                and ArtifactReference.parse(target_refs[0]).kind == 'image-led-generation-response'):
            from ai_ppt_studio.application.image_led_repair import ImageLedRepairService
            from ai_ppt_studio.domains.materials.image_input_contracts import fail
            if role_id != 'visual-engineering-reviewer':
                fail('REPAIR_REVIEW', 'image diagnosis requires the independent engineering reviewer')
            target = ImageLedRepairService(self.kernel).review_input(target_refs[0])
            return {'schema_version': '3.0', 'project_id': state.project_id,
                'project_revision': project_revision, 'artifact_version_refs': list(target_refs),
                'layers': {'role_contract': {'role_id': role_id},
                    'task_contract': {'task_type': task_type, 'target_refs': list(target_refs)},
                    'image_led_diagnostic': target,
                    'output_contract': {'artifact_type': 'image-led-content-diagnostic',
                        'exclusion_review_required': True, 'does_not_select_candidate': True}}}
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
        context = {
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
        if task_type == "build-native-first":
            from ai_ppt_studio.application.image_led_service import is_image_led
            if is_image_led(self.kernel) and role_id != "native-first-engineer":
                raise WorkbenchValidationError("IMAGE_LED_HANDOFF: only the formal native builder may receive this task")
            context["layers"]["visual_handoff"] = self._compile_visual_handoff(
                project_revision=project_revision,
                target_refs=target_refs,
                task_id=task_id,
            )
        return context

    def _compile_visual_handoff(
        self,
        *,
        project_revision: int,
        target_refs: list[str],
        task_id: str,
    ) -> dict[str, Any]:
        """Compile one closed, current, PowerPoint-specific handoff projection."""

        return self._build_visual_handoff(
            project_revision=project_revision,
            target_refs=target_refs,
            task_id=task_id,
            require_output_paths_absent=True,
        )

    def validate_visual_handoff_for_result(
        self,
        handoff: dict[str, Any],
        *,
        project_revision: int,
        expected_revision: int,
        target_refs: list[str],
        task_id: str,
    ) -> None:
        """Re-resolve the complete handoff contract before accepting a result."""

        expected = self._build_visual_handoff(
            project_revision=project_revision,
            target_refs=target_refs,
            task_id=task_id,
            require_output_paths_absent=False,
        )
        if expected["result_expected_revision"] != expected_revision:
            raise WorkbenchValidationError(
                "build-native-first visual handoff result revision is stale"
            )
        if handoff != expected:
            raise WorkbenchValidationError(
                "build-native-first visual handoff contract is stale or inconsistent"
            )

    def _build_visual_handoff(
        self,
        *,
        project_revision: int,
        target_refs: list[str],
        task_id: str,
        require_output_paths_absent: bool,
    ) -> dict[str, Any]:
        """Build the canonical handoff shape from exact current artifacts."""

        if not TASK_ID_PATTERN.fullmatch(task_id):
            raise WorkbenchValidationError(
                "build-native-first requires a 64-character lowercase hexadecimal task_id"
            )
        from ai_ppt_studio.application.image_led_service import is_image_led
        if is_image_led(self.kernel):
            return self._build_image_led_handoff(
                project_revision=project_revision, target_refs=target_refs,
                task_id=task_id, require_output_paths_absent=require_output_paths_absent)
        state = self.kernel.load()
        blockers: list[str] = []
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator

        plan_ref, plan = GateEvaluator(self.kernel)._current_visual_compilation_plan(
            blockers
        )
        if not plan_ref or not isinstance(plan, dict):
            raise WorkbenchValidationError(
                "build-native-first requires the exact current visual compilation plan"
            )
        if (
            plan.get("compiler_version") != COMPILER_VERSION
            or plan.get("handoff_version") != HANDOFF_VERSION
        ):
            raise WorkbenchValidationError(
                "build-native-first visual handoff compiler version is invalid"
            )
        if target_refs != [plan_ref]:
            raise WorkbenchValidationError(
                "build-native-first requires the exact current visual compilation plan"
            )

        current_refs = {
            "reading_blueprint_ref": state.artifact_heads.get(
                "content/reading-blueprint", ""
            ),
            "visual_brief_ref": state.artifact_heads.get("visual/brief", ""),
            "deck_design_system_ref": state.artifact_heads.get(
                "visual/design-system", ""
            ),
            "visual_contract_set_ref": state.artifact_heads.get(
                "visual/contracts", ""
            ),
        }
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        expected_refs = {
            **current_refs,
            "release_target_policy_ref": policy_ref,
        }
        if any(not value for value in expected_refs.values()):
            raise WorkbenchValidationError(
                "build-native-first visual handoff inputs are incomplete"
            )
        for field, value in expected_refs.items():
            if plan.get(field) != value:
                raise WorkbenchValidationError(
                    f"build-native-first visual handoff ref is stale: {field}"
                )

        blueprint = self._payload(
            "content/reading-blueprint", "reading-deck-blueprint"
        )
        visual_brief = self._payload("visual/brief", "visual-brief")
        design_system = self._payload("visual/design-system", "deck-design-system")
        contract_set = self._payload("visual/contracts", "visual-contract-set")
        source_revision = plan.get("source_revision")
        if (
            isinstance(source_revision, bool)
            or not isinstance(source_revision, int)
            or source_revision <= 0
            or source_revision > project_revision
        ):
            raise WorkbenchValidationError(
                "build-native-first visual handoff source_revision is invalid"
            )

        output_root = self.kernel.project_root.resolve()
        output_paths = {
            "pptx": str(
                output_root / "delivery" / "anchors" / task_id / "native-anchors.pptx"
            ),
            "render_dir": str(output_root / "renders" / "anchors" / task_id),
            "montage": str(
                output_root / "renders" / "anchors" / task_id / "montage.png"
            ),
        }
        for path_value in output_paths.values():
            path = Path(path_value)
            try:
                path.resolve().relative_to(output_root)
            except ValueError as exc:
                raise WorkbenchValidationError(
                    "build-native-first output path escaped the project root"
                ) from exc
            if task_id not in path.parts:
                raise WorkbenchValidationError(
                    "build-native-first output path must contain the task_id"
                )
            if require_output_paths_absent and path.exists():
                raise WorkbenchValidationError(
                    "build-native-first output path must be absent before authoring"
                )

        def visual_projection(payload: dict[str, Any]) -> dict[str, Any]:
            return {
                key: deepcopy(value)
                for key, value in payload.items()
                if key not in HANDOFF_CONTENT_EXCLUSIONS
            }

        reading_slides: list[dict[str, Any]] = []
        for slide in blueprint.get("slides") or []:
            if not isinstance(slide, dict):
                raise WorkbenchValidationError(
                    "build-native-first reading blueprint slides are invalid"
                )
            reading_slides.append(
                {
                    key: deepcopy(slide[key])
                    for key in (
                        "slide_id",
                        "section_id",
                        "order",
                        "neutral_title",
                        "page_task",
                        "reading_question",
                        "previous_relation",
                        "next_relation",
                        "reading_quality",
                    )
                    if key in slide
                }
            )
        reading_projection = {
            key: deepcopy(blueprint[key])
            for key in ("project_id", "source_version", "material_mode", "section_flow")
            if key in blueprint
        }
        reading_projection["slides"] = reading_slides

        slide_contracts = [
            visual_projection(slide)
            for slide in contract_set.get("slide_contracts") or []
            if isinstance(slide, dict)
        ]
        handoff = {
            "task_id": task_id,
            "handoff_version": plan["handoff_version"],
            "compiler_version": plan["compiler_version"],
            "visual_compilation_plan_ref": plan_ref,
            "reading_blueprint_ref": current_refs["reading_blueprint_ref"],
            "visual_brief_ref": current_refs["visual_brief_ref"],
            "deck_design_system_ref": current_refs["deck_design_system_ref"],
            "visual_contract_set_ref": current_refs["visual_contract_set_ref"],
            "release_target_policy_ref": policy_ref,
            "source_version": plan["source_version"],
            "source_revision": source_revision,
            "reading_blueprint": reading_projection,
            "visual_brief": visual_projection(visual_brief),
            "deck_design_system": visual_projection(design_system),
            "slide_visual_contracts": slide_contracts,
            "compilation_slides": deepcopy(plan["slides"]),
            "required_target_ids": list(policy.required_target_ids),
            "deferred_target_ids": list(policy.deferred_target_ids),
            "output_paths": output_paths,
            "result_expected_revision": project_revision + 1,
            "authorization_scope": deepcopy(VISUAL_HANDOFF_AUTHORIZATION_SCOPE),
            "authoring_contract": deepcopy(VISUAL_HANDOFF_AUTHORING_CONTRACT),
            "evidence_contract": deepcopy(VISUAL_HANDOFF_EVIDENCE_CONTRACT),
        }
        if set(handoff) != VISUAL_HANDOFF_FIELDS:
            raise WorkbenchValidationError(
                "build-native-first visual handoff schema is not closed"
            )
        return handoff

    def _build_image_led_handoff(
        self, *, project_revision: int, target_refs: list[str], task_id: str,
        require_output_paths_absent: bool,
    ) -> dict[str, Any]:
        """Resolve formal dependencies and emit the renderer's exact closed input.

        Governance metadata stays in the wrapper so the renderer never has to
        interpret a source blueprint, free-form instructions, or legacy layout.
        This method performs no business or output-file writes.
        """
        import base64
        import hashlib
        from io import BytesIO
        from PIL import Image
        from ai_ppt_studio.application.image_led_native import ImageLedNativeService

        service = ImageLedNativeService(self.kernel)
        if require_output_paths_absent:
            service.require_g0()
        state = self.kernel.load()
        if state.gate_status.get("G0") != "passed":
            raise WorkbenchValidationError("IMAGE_LED_HANDOFF: current G0 must remain passed")
        if state.gate_status.get("G1") != "passed":
            raise WorkbenchValidationError("IMAGE_LED_HANDOFF: current G1 must pass before native build")
        _, plan = service.current_contract_plan()
        plan_ref = state.artifact_heads.get("visual/compilation-plan", "")
        if target_refs != [plan_ref]:
            raise WorkbenchValidationError(
                "build-native-first requires the exact current visual compilation plan")
        from ai_ppt_studio.domains.visual.compilation import (IMAGE_LED_COMPILER_VERSION_V2, IMAGE_LED_HANDOFF_VERSION_V2,
            IMAGE_LED_COMPILER_VERSION_V3, IMAGE_LED_HANDOFF_VERSION_V3)
        if (plan["compiler_version"], plan["handoff_version"]) not in {
                (IMAGE_LED_COMPILER_VERSION, IMAGE_LED_HANDOFF_VERSION),
                (IMAGE_LED_COMPILER_VERSION_V2, IMAGE_LED_HANDOFF_VERSION_V2),
                (IMAGE_LED_COMPILER_VERSION_V3, IMAGE_LED_HANDOFF_VERSION_V3)}:
            raise WorkbenchValidationError("IMAGE_LED_HANDOFF: independent compiler version differs")
        if (type(plan["source_revision"]) is not int
                or not 0 < plan["source_revision"] <= project_revision):
            raise WorkbenchValidationError("IMAGE_LED_HANDOFF: source revision differs")
        policy_ref, policy = ReleaseTargetPolicyService(self.kernel).current()
        expected_refs = {
            "reading_blueprint_ref": state.artifact_heads.get("content/reading-blueprint"),
            "visual_brief_ref": state.artifact_heads.get("visual/brief"),
            "deck_design_system_ref": state.artifact_heads.get("visual/design-system"),
            "visual_contract_set_ref": state.artifact_heads.get("visual/contracts"),
            "release_target_policy_ref": policy_ref,
            "selection_ref": state.artifact_heads.get("visual/image-led/selection"),
            "region_inventory_ref": state.artifact_heads.get("visual/image-led/regions"),
        }
        if any(not value or plan.get(field) != value for field, value in expected_refs.items()):
            raise WorkbenchValidationError("IMAGE_LED_HANDOFF: current dependency refs differ")
        output_root = self.kernel.project_root.resolve()
        directory = output_root / task_id
        pptx = directory / "native-anchors.pptx"
        # The renderer creates exactly one new task directory. No parent mkdir is
        # needed before the Agent task transaction has been accepted.
        for path in (directory, pptx):
            if path.is_symlink() or (require_output_paths_absent and path.exists()):
                raise WorkbenchValidationError("IMAGE_LED_HANDOFF: output path must be absent and not a symlink")
            if not path.resolve().is_relative_to(output_root):
                raise WorkbenchValidationError("IMAGE_LED_HANDOFF: output path escaped project")

        required_assets: dict[str, str] = {}
        def require_asset(ref: str, digest: str) -> None:
            if ref in required_assets and required_assets[ref] != digest:
                raise WorkbenchValidationError("IMAGE_LED_HANDOFF: one asset ref has conflicting hashes")
            required_assets[ref] = digest

        for slide in plan["slides"]:
            target = slide["target_binding"]
            require_asset(target["target_image_ref"], target["target_image_sha256"])
            for region in slide["regions"]:
                if region["kind"] in {"image", "decoration"}:
                    require_asset(region["appearance"]["asset_ref"], region["appearance"]["asset_sha256"])
        assets: dict[str, Any] = {}
        for ref, expected_hash in required_assets.items():
            value = self.kernel.artifacts.resolve(ArtifactReference.parse(ref))["payload"]
            try:
                raw = base64.b64decode(value["data_base64"], validate=True)
                if (hashlib.sha256(raw).hexdigest() != expected_hash
                        or value.get("sha256") != expected_hash):
                    raise ValueError("asset bytes hash mismatch")
                with Image.open(BytesIO(raw)) as decoded:
                    decoded.load()
                    expected_mime = {"PNG": "image/png", "JPEG": "image/jpeg"}.get(decoded.format)
                if not expected_mime or value.get("mime_type") != expected_mime:
                    raise ValueError("CapabilityGap: native image assets require exact PNG/JPEG bytes")
            except (KeyError, ValueError, OSError) as exc:
                raise WorkbenchValidationError("IMAGE_LED_HANDOFF: invalid or unsupported exact image asset: " + str(exc)) from exc
            assets[ref] = {"sha256": expected_hash, "data_base64": value["data_base64"],
                           "mime_type": expected_mime}
        renderer_handoff = {
            "handoff_version": plan['handoff_version'],
            "compiler_version": plan['compiler_version'],
            "project_id": self.kernel.project_id,
            "selection_ref": plan["selection_ref"],
            "region_inventory_ref": plan["region_inventory_ref"],
            "plan_ref": plan_ref, "task_id": task_id,
            "slides": deepcopy(plan["slides"]), "assets": assets,
            "output_paths": {"directory": str(directory), "pptx": str(pptx)},
        }
        selection = service.current_selection(plan["selection_ref"])
        selection_context = {}
        if selection.get("selection_origin") == "delegated-ai-working-selection":
            delegation = self.kernel.artifacts.resolve(
                ArtifactReference.parse(selection["delegation_ref"]))["payload"]
            # Kept outside the renderer's closed v1/v2 contract. This context is
            # still re-derived and compared exactly when the result is accepted.
            selection_context["selection_provenance"] = {
                "selection_ref": plan["selection_ref"],
                **{key: selection[key] for key in ("selection_origin", "scope", "delegation_ref",
                    "human_image_approval", "final_human_acceptance")},
                "delegation": deepcopy(delegation["delegation"]),
            }
        return {
            "task_id": task_id, "compiler_version": plan['compiler_version'],
            "handoff_version": plan['handoff_version'],
            "visual_compilation_plan_ref": plan_ref,
            **{field: plan[field] for field in (
                "reading_blueprint_ref", "visual_brief_ref", "deck_design_system_ref",
                "visual_contract_set_ref", "release_target_policy_ref", "source_version", "source_revision")},
            "result_expected_revision": project_revision + 1,
            "required_target_ids": list(policy.required_target_ids),
            "deferred_target_ids": list(policy.deferred_target_ids),
            "renderer_handoff": renderer_handoff,
            **selection_context,
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
        blockers: list[str] = []
        from ai_ppt_studio.application.gate_evaluator import GateEvaluator

        current_plan_ref, _plan = GateEvaluator(self.kernel)._current_visual_compilation_plan(
            blockers
        )
        if not current_plan_ref:
            raise WorkbenchValidationError(
                "Image 2 assets require the current visual compilation plan"
            )
        if anchor.get("visual_compilation_plan_ref") != current_plan_ref:
            raise WorkbenchValidationError(
                "Image 2 assets require the current native-first anchor plan"
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
