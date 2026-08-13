"""Public runtime exceptions."""


class AiPptError(Exception):
    """Base error for user-recoverable AI PPT runtime failures."""


class ConfigurationError(AiPptError):
    """Raised when workspace configuration is invalid."""


class ProtectedPathError(AiPptError):
    """Raised before a write can touch a protected location."""


class ProjectNotFoundError(AiPptError):
    """Raised when a managed project cannot be found."""


class InvalidTransitionError(AiPptError):
    """Raised when a project attempts to skip a state gate."""


class MaterialImportError(AiPptError):
    """Raised when user-provided source material cannot be imported safely."""


class ArtifactValidationError(AiPptError):
    """Raised when a project artifact lacks required semantic content."""


class ArtifactReferenceError(AiPptError):
    """Raised when an immutable artifact reference cannot be resolved safely."""


class ProjectIdentityError(AiPptError):
    """Raised when a kernel is opened with the wrong project identity."""


class GateMutationError(AiPptError):
    """Raised when code attempts to forge or corrupt a gate transition."""


class ContractValidationError(AiPptError):
    """Raised when a schema 3.0 domain contract is invalid."""


class MissionNotConfirmedError(AiPptError):
    """Raised before formal content work without a current user confirmation."""


class MaterialModeUnconfirmedError(AiPptError):
    """Raised when neither current materials nor an explicit empty mode is bound."""


class ProposalOnlyIdentityViolationError(AiPptError):
    """Raised when no-material content is presented as sourced customer truth."""


class FeedbackGovernanceError(AiPptError):
    """Raised when feedback bypasses its required governance state."""


class ContentWorkflowError(AiPptError):
    """Raised when the content-review workflow cannot safely advance."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)


class ConfirmationTransactionError(AiPptError):
    """Reject an untrusted, stale, replayed, or corrupt confirmation commit."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ExperienceValidationError(AiPptError):
    """Raised when personal experience data or an evolution action is invalid."""


class WorkbenchValidationError(AiPptError):
    """Raised when a workbench request is structurally invalid."""


class RevisionConflictError(AiPptError):
    """Raised when a workbench write targets an obsolete project revision."""

    def __init__(self, expected_revision: int, actual_revision: int) -> None:
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            f"Expected revision {expected_revision}, current revision is {actual_revision}"
        )


class ReviewSourceStaleError(AiPptError):
    """Raised when marks target a professional-review source that has changed."""

    def __init__(self, expected_source: str, actual_source: str) -> None:
        self.expected_source = expected_source
        self.actual_source = actual_source
        super().__init__(
            f"Review source {expected_source} is stale; current source is {actual_source}"
        )


class ReviewMarkSaveError(AiPptError):
    """Raised when a valid review-mark write fails at the persistence boundary."""


class ChatDeliveryError(AiPptError):
    """Raised when a valid chat-delivery receipt cannot be persisted."""


class GateBlockedError(AiPptError):
    """Raised when a user tries to pass a quality gate without its evidence."""

    def __init__(self, gate: str, missing_evidence: tuple[str, ...]) -> None:
        self.gate = gate
        self.missing_evidence = missing_evidence
        super().__init__(
            f"{gate} is missing required evidence: {', '.join(missing_evidence)}"
        )
