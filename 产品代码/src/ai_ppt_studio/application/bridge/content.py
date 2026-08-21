"""Evidence-first content and full-deck review bridge handlers."""

from __future__ import annotations

from typing import Any, Callable

from ai_ppt_studio.application.bridge import (
    BridgeContext,
    object_value,
    response,
    result,
)
from ai_ppt_studio.application.content_hard_gate_service import ContentHardGateService
from ai_ppt_studio.application.content_evidence_browser_service import (
    ContentEvidenceBrowserService,
)
from ai_ppt_studio.application.content_review import (
    ContentDecisionService,
    ContentReviewBatchService,
    ContentReviewProjectionService,
    ContentRevisionPlanningService,
)
from ai_ppt_studio.application.presales_content_service import PresalesContentService


def _build(
    ctx: BridgeContext,
    request: dict[str, Any],
    method: Callable[[str, int, dict[str, Any]], str],
) -> dict[str, Any]:
    artifact_ref = method(
        ctx.command_id,
        int(request["expected_revision"]),
        object_value(request, "payload"),
    )
    return result(ctx, artifact_ref=artifact_ref)


def build_evidence_book(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _build(ctx, request, PresalesContentService(ctx.kernel).build_evidence_book)


def build_decision_context(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _build(ctx, request, PresalesContentService(ctx.kernel).build_decision_context)


def build_problem_solution_fit(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _build(
        ctx, request, PresalesContentService(ctx.kernel).build_problem_solution_fit
    )


def build_reading_blueprint(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _build(
        ctx,
        request,
        PresalesContentService(ctx.kernel).build_reading_deck_blueprint,
    )


def repair_reading_blueprint(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _build(
        ctx,
        request,
        PresalesContentService(ctx.kernel).repair_reading_deck_blueprint,
    )


def _run_gate(
    ctx: BridgeContext,
    request: dict[str, Any],
    method: Callable[..., tuple[str, dict[str, Any], Any]],
) -> dict[str, Any]:
    gate_ref, gate, state = method(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        semantic_check_results=list(request.get("semantic_check_results") or []),
        reviewer_mode=str(request.get("reviewer_mode") or "isolated-review-task"),
        independent_agent_instance_id=str(
            request.get("independent_agent_instance_id") or ""
        ),
        output_ref=str(request.get("output_ref") or ""),
    )
    return result(ctx, state, gate_ref=gate_ref, gate=gate)


def run_evidence_gate(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _run_gate(ctx, request, ContentHardGateService(ctx.kernel).run_evidence_gate)


def run_reading_gate(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _run_gate(
        ctx, request, ContentHardGateService(ctx.kernel).run_presales_reading_gate
    )


def get_review_projection(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return response(
        ctx,
        review=ContentReviewProjectionService(ctx.kernel).project(
            str(request.get("review_session_id") or "")
        ),
        snapshot_revision=ctx.kernel.load().revision,
    )


def save_page_decision(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    decision_ref, decision, state = ContentDecisionService(ctx.kernel).save(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        review_session_id=str(request.get("review_session_id") or ""),
        source_version=str(request.get("source_version") or ""),
        slide_id=str(request.get("slide_id") or ""),
        decision=str(request.get("decision") or ""),
        comment=str(request.get("comment") or ""),
    )
    return result(ctx, state, decision_ref=decision_ref, decision=decision)


def _batch(
    ctx: BridgeContext,
    request: dict[str, Any],
    method: Callable[..., tuple[str, dict[str, Any], Any]],
) -> dict[str, Any]:
    batch_ref, batch, state = method(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        review_session_id=str(request.get("review_session_id") or ""),
        source_version=str(request.get("source_version") or ""),
    )
    return result(ctx, state, batch_ref=batch_ref, batch=batch)


def submit_review_batch(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    return _batch(ctx, request, ContentReviewBatchService(ctx.kernel).submit)


def withdraw_review_batch(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return _batch(ctx, request, ContentReviewBatchService(ctx.kernel).withdraw)


def save_revision_plan(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    plan_ref, plan, state = ContentRevisionPlanningService(ctx.kernel).save_plan(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        batch_ref=str(request.get("batch_ref") or ""),
        source_version=str(request.get("source_version") or ""),
        plan=object_value(request, "plan"),
    )
    return result(ctx, state, plan_ref=plan_ref, plan=plan)


def confirm_revision_plan(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    confirmation_ref, state = ContentRevisionPlanningService(ctx.kernel).confirm_plan(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        plan_ref=str(request.get("plan_ref") or ""),
        source_version=str(request.get("source_version") or ""),
        user_message_ref=str(request.get("user_message_ref") or ""),
    )
    return result(ctx, state, confirmation_ref=confirmation_ref)


def create_change_set(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    change_ref, change, state = ContentRevisionPlanningService(
        ctx.kernel
    ).create_change_set(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
        plan_ref=str(request.get("plan_ref") or ""),
        confirmation_ref=str(request.get("confirmation_ref") or ""),
        source_version=str(request.get("source_version") or ""),
    )
    return result(ctx, state, change_set_ref=change_ref, change_set=change)


def open_g0_review(ctx: BridgeContext, request: dict[str, Any]) -> dict[str, Any]:
    state = PresalesContentService(ctx.kernel).open_g0_review(
        command_id=ctx.command_id,
        expected_revision=int(request["expected_revision"]),
    )
    return result(ctx, state)


def open_content_evidence_browser(
    ctx: BridgeContext, request: dict[str, Any]
) -> dict[str, Any]:
    return response(
        ctx,
        **ContentEvidenceBrowserService(ctx.kernel).open(
            review_session_id=str(request.get("review_session_id") or ""),
            evidence_ref=str(request.get("evidence_ref") or ""),
        ),
    )


HANDLERS = {
    "build-presales-evidence-book": build_evidence_book,
    "build-customer-decision-context": build_decision_context,
    "build-problem-solution-fit": build_problem_solution_fit,
    "build-reading-deck-blueprint": build_reading_blueprint,
    "repair-reading-deck-blueprint": repair_reading_blueprint,
    "run-content-evidence-gate": run_evidence_gate,
    "run-content-presales-reading-gate": run_reading_gate,
    "get-content-review-projection": get_review_projection,
    "save-content-page-decision": save_page_decision,
    "submit-content-review-batch": submit_review_batch,
    "withdraw-content-review-batch": withdraw_review_batch,
    "save-content-batch-revision-plan": save_revision_plan,
    "confirm-content-batch-revision-plan": confirm_revision_plan,
    "create-content-batch-change-set": create_change_set,
    "open-content-evidence-browser": open_content_evidence_browser,
    "open-g0-review": open_g0_review,
}


__all__ = ["HANDLERS"]
