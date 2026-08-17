"""Read-only evidence URL resolution for the current content ReviewSession."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ai_ppt_studio.application.content_review.projection_service import (
    ContentReviewProjectionService,
)
from ai_ppt_studio.errors import ArtifactReferenceError, ContractValidationError
from ai_ppt_studio.kernel.references import ArtifactReference
from ai_ppt_studio.kernel.transactions import ProjectKernel


class ContentEvidenceBrowserService:
    """Resolve one source-bound evidence reference without persisting judgment."""

    def __init__(self, kernel: ProjectKernel) -> None:
        self.kernel = kernel

    def open(
        self, *, review_session_id: str, evidence_ref: str
    ) -> dict[str, Any]:
        projection = ContentReviewProjectionService(self.kernel).project(
            review_session_id
        )
        blueprint = self._payload(
            projection["reading_blueprint_ref"], "reading-deck-blueprint"
        )
        evidence_book = self._payload(
            blueprint["evidence_book_ref"], "presales-evidence-book"
        )
        allowed = self._source_refs(blueprint) | self._source_refs(evidence_book)
        if evidence_ref not in allowed:
            raise ContractValidationError(
                "Evidence reference is not bound to the current content review"
            )
        evidence = self._payload(evidence_ref)
        url = next(
            (
                value.strip()
                for field in ("read_only_url", "source_url", "url", "locator")
                if isinstance((value := evidence.get(field)), str)
                and value.strip()
            ),
            "",
        )
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ContractValidationError(
                "CONTENT_EVIDENCE_BROWSER_UNAVAILABLE: "
                "current evidence has no safe HTTPS read-only source"
            )
        return {
            "review_session_id": review_session_id,
            "evidence_ref": evidence_ref,
            "url": url,
            "read_only": True,
            "proof_eligible": False,
            "real_browser_evidence": False,
        }

    def _payload(
        self, reference: str, expected_kind: str = ""
    ) -> dict[str, Any]:
        try:
            parsed = ArtifactReference.parse(reference)
            if expected_kind and parsed.kind != expected_kind:
                raise ArtifactReferenceError(
                    f"Expected {expected_kind}, got {parsed.kind}"
                )
            record = self.kernel.artifacts.resolve(parsed)
            payload = record["payload"]
            if not isinstance(payload, dict):
                raise TypeError("payload must be an object")
            return dict(payload)
        except (ArtifactReferenceError, KeyError, TypeError) as error:
            raise ContractValidationError(
                f"Content evidence cannot be resolved: {reference}"
            ) from error

    @staticmethod
    def _source_refs(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"source_ref", "source_refs", "evidence_refs"}:
                    values = child if isinstance(child, list) else [child]
                    found.update(
                        item
                        for item in values
                        if isinstance(item, str) and item
                    )
                else:
                    found.update(ContentEvidenceBrowserService._source_refs(child))
        elif isinstance(value, list):
            for child in value:
                found.update(ContentEvidenceBrowserService._source_refs(child))
        return found


__all__ = ["ContentEvidenceBrowserService"]
