"""Schema 3 experience fixtures; all application evidence is simulated."""

from __future__ import annotations

from pathlib import Path

from ai_ppt_studio.application.experience_service import ExperienceService
from ai_ppt_studio.kernel.transactions import ProjectKernel


def prepared_experience(
    project: Path,
) -> tuple[ExperienceService, int, dict[str, str]]:
    kernel = ProjectKernel.initialize(
        project, project_id="experience-authority-project"
    )
    experience = ExperienceService(kernel)
    example_ref = str(
        kernel.artifacts.put(
            "preferred-example",
            {
                "identity": "simulated-example-source",
                "contains_client_identifiers": False,
            },
        )
    )
    target_ref = str(
        kernel.artifacts.put(
            "visual-contract",
            {"identity": "simulated-current-target", "status": "reviewable"},
        )
    )
    analysis_ref = str(
        kernel.artifacts.put(
            "experience-analysis",
            {
                "identity": "simulated-professional-analysis",
                "result": "passed",
            },
        )
    )
    return experience, kernel.load().revision, {
        "example": example_ref,
        "target": target_ref,
        "analysis": analysis_ref,
    }


def valid_intake_payload(refs: dict[str, str]) -> dict:
    return {
        "intake_id": "intake-preferred-example",
        "source_type": "preferred-example",
        "source_project_id": "experience-authority-project",
        "source_version": "preferred-example-v1",
        "source_refs": [refs["example"]],
        "target_refs": [refs["target"]],
        "evidence_refs": [refs["analysis"]],
        "privacy_boundary": "sanitized-no-client-identifiers",
        "user_label": "用户明确优选",
        "execution_status": "source-registered",
        "learning_status": "intake-only",
    }


def valid_preference_payload(intake_ref: str, refs: dict[str, str]) -> dict:
    return {
        "result_type": "preference-signal",
        "result_id": "pref-reading-density",
        "intake_ref": intake_ref,
        "source_refs": [refs["example"]],
        "positive_or_negative": "positive",
        "preference_statement": "在合格方案中优先选择阅读路径更清晰的页面",
        "scope": "slide-family",
        "conditions": ["reading-first", "executive-audience"],
        "counterexamples": ["不允许牺牲证据完整性"],
        "confidence_inputs": [refs["analysis"]],
        "version": 1,
    }


def valid_mechanism_payload(intake_ref: str, refs: dict[str, str]) -> dict:
    return {
        "result_type": "professional-mechanism-candidate",
        "result_id": "mechanism-reading-path",
        "intake_ref": intake_ref,
        "source_refs": [refs["example"]],
        "mechanism": "用明确的阅读路径把结论、证据与行动连接起来",
        "scenes": ["presales"],
        "audiences": ["executive"],
        "slide_tasks": ["solution-overview"],
        "conditions": ["reading-first", "strict-B"],
        "evidence_refs": [refs["analysis"]],
        "counterexamples": ["只强调形式而削弱证据"],
        "failure_conditions": ["核心主张与证据断裂"],
        "privacy_boundary": "sanitized-no-client-identifiers",
        "whole_case_copy": False,
        "version": 1,
    }


def valid_anti_pattern_payload(intake_ref: str, refs: dict[str, str]) -> dict:
    return {
        "result_type": "anti-pattern-candidate",
        "result_id": "anti-decoration-without-meaning",
        "intake_ref": intake_ref,
        "source_refs": [refs["example"]],
        "pattern": "无语义装饰掩盖信息层级",
        "symptoms": ["装饰对象抢夺阅读焦点"],
        "root_causes": ["视觉元素未绑定页面任务"],
        "scopes": ["slide", "slide-family"],
        "negative_evidence_refs": [refs["analysis"]],
        "repair_mechanisms": ["删除无语义对象并恢复结论优先级"],
        "exceptions": ["不影响阅读的品牌纹理"],
        "privacy_boundary": "sanitized-no-client-identifiers",
        "whole_case_copy": False,
        "version": 1,
    }


def prepared_learning_results(
    project: Path,
) -> tuple[ExperienceService, int, dict[str, object]]:
    experience, revision, refs = prepared_experience(project)
    intake_ref = experience.register_intake(
        "prepared-experience-intake", revision, valid_intake_payload(refs)
    )
    revision += 1
    result_refs: dict[str, str] = {}
    payloads = {
        "preference": valid_preference_payload(intake_ref, refs),
        "mechanism": valid_mechanism_payload(intake_ref, refs),
        "anti_pattern": valid_anti_pattern_payload(intake_ref, refs),
    }
    for name, payload in payloads.items():
        result_refs[name] = experience.register_learning_result(
            f"prepared-{name}", revision, payload
        )
        revision += 1
    return experience, revision, {
        **refs,
        "intake": intake_ref,
        **result_refs,
    }


def prepared_candidate(
    project: Path,
) -> tuple[ExperienceService, int, dict[str, object]]:
    experience, revision, refs = prepared_learning_results(project)
    candidate_ref = experience.register_candidate(
        "prepared-experience-candidate",
        revision,
        {
            "candidate_id": "candidate-reading-path",
            "learning_result_ref": refs["mechanism"],
            "version": 1,
            "level": "candidate",
        },
    )
    return experience, revision + 1, {**refs, "candidate": candidate_ref}


def application_evidence(
    experience: ExperienceService,
    project_id: str,
    target_context: dict[str, object],
    *,
    simulation: bool = False,
) -> str:
    return str(
        experience.kernel.artifacts.put(
            "experience-application-evidence",
            {
                "project_id": project_id,
                "target_context": target_context,
                "evidence_identity": (
                    "simulated-contract-only"
                    if simulation
                    else "real-project-runtime"
                ),
                "simulation": simulation,
                "captured_at": "2026-08-09T15:00:00+08:00",
            },
        )
    )


def valid_application_payload(
    refs: dict[str, object],
    *,
    application_id: str,
    project_id: str,
    runtime_evidence_ref: str,
) -> dict:
    return {
        "application_id": application_id,
        "candidate_ref": refs["candidate"],
        "application_project_id": project_id,
        "target_context": {
            "scene": "presales",
            "audience": "executive",
            "slide_task": "solution-overview",
            "conditions": ["reading-first", "strict-B"],
        },
        "match_reasons": ["scene", "audience", "slide-task", "conditions"],
        "match_result": "matched",
        "runtime_evidence_ref": runtime_evidence_ref,
    }


def valid_evaluation_payload(
    experience: ExperienceService,
    application_ref: str,
    *,
    result: str = "success",
) -> dict:
    review_ref = str(
        experience.kernel.artifacts.put(
            "experience-professional-review",
            {"application_ref": application_ref, "result": "passed"},
        )
    )
    evidence_ref = str(
        experience.kernel.artifacts.put(
            "experience-result-evidence",
            {"application_ref": application_ref, "result": result},
        )
    )
    success = result == "success"
    return {
        "application_ref": application_ref,
        "professional_review_refs": [review_ref],
        "professional_result": "passed" if success else "failed",
        "user_outcome": "accepted" if success else "rejected",
        "evidence_refs": [evidence_ref],
        "application_result": result,
        "context_match_result": "matched",
    }
