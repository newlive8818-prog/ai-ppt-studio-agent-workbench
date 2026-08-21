"""Explicit handler-map facade over schema 3.0 application services."""

from __future__ import annotations

from typing import Any

from ai_ppt_studio.application.bridge import context, is_schema3_project
from ai_ppt_studio.application.bridge.content import HANDLERS as CONTENT_HANDLERS
from ai_ppt_studio.application.bridge.delivery_experience import (
    HANDLERS as DELIVERY_EXPERIENCE_HANDLERS,
)
from ai_ppt_studio.application.bridge.project import HANDLERS as PROJECT_HANDLERS
from ai_ppt_studio.application.bridge.review import HANDLERS as REVIEW_HANDLERS
from ai_ppt_studio.application.bridge.visual import HANDLERS as VISUAL_HANDLERS
from ai_ppt_studio.errors import ContractValidationError


HANDLERS = {
    **PROJECT_HANDLERS,
    **CONTENT_HANDLERS,
    **REVIEW_HANDLERS,
    **VISUAL_HANDLERS,
    **DELIVERY_EXPERIENCE_HANDLERS,
}


def dispatch_v16(request: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one public operation through its explicit domain handler."""

    ctx = context(request)
    handler = HANDLERS.get(ctx.operation)
    if handler is None:
        raise ContractValidationError(
            f"Unsupported schema 3.0 operation: {ctx.operation}"
        )
    return handler(ctx, request)


__all__ = ["HANDLERS", "dispatch_v16", "is_schema3_project"]
