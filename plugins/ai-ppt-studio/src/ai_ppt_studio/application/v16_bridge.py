"""Explicit handler-map facade over schema 3.0 application services."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.bridge import context, is_schema3_project
from ai_ppt_studio.application.bridge.content import HANDLERS as CONTENT_HANDLERS
from ai_ppt_studio.application.bridge.delivery_experience import (
    HANDLERS as DELIVERY_EXPERIENCE_HANDLERS,
)
from ai_ppt_studio.application.bridge.project import HANDLERS as PROJECT_HANDLERS
from ai_ppt_studio.application.bridge.review import (
    HANDLERS as REVIEW_HANDLERS,
    PRIVATE_HANDLERS as PRIVATE_REVIEW_HANDLERS,
)
from ai_ppt_studio.application.bridge.visual import HANDLERS as VISUAL_HANDLERS
from ai_ppt_studio.errors import ContractValidationError


# Keep the optimization tool identities public without importing image/OOXML
# dependencies for ordinary project and content operations.
OPTIMIZATION_OPERATIONS = (
    "optimization-begin", "optimization-external-scope",
    "optimization-register-request", "optimization-register-historical-design",
    "optimization-execute-request", "optimization-recover-request",
    "optimization-withdraw-unsent-request", "optimization-supersede-unselected-response",
    "optimization-register-local-media-composition", "optimization-review-response",
    "optimization-select-internal", "optimization-register-plan",
    "optimization-compile-handoff", "optimization-register-result",
    "optimization-register-target-evidence", "optimization-register-qa",
    "optimization-status",
    "optimization-preview-image",
)


def _optimization_handler(ctx, request):
    from ai_ppt_studio.application.optimization_bridge import INTERNAL_HANDLERS
    return INTERNAL_HANDLERS[ctx.operation](ctx, request)


HANDLERS = {
    **PROJECT_HANDLERS,
    **CONTENT_HANDLERS,
    **REVIEW_HANDLERS,
    **VISUAL_HANDLERS,
    **DELIVERY_EXPERIENCE_HANDLERS,
    **{operation: _optimization_handler for operation in OPTIMIZATION_OPERATIONS},
}
INTERNAL_HANDLERS = {**HANDLERS, **PRIVATE_REVIEW_HANDLERS}


def dispatch_v16(request: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one public operation through its explicit domain handler."""

    ctx = context(request)
    handler = INTERNAL_HANDLERS.get(ctx.operation)
    if handler is None:
        raise ContractValidationError(
            f"Unsupported schema 3.0 operation: {ctx.operation}"
        )
    return handler(ctx, request)


__all__ = ["HANDLERS", "dispatch_v16", "is_schema3_project"]
