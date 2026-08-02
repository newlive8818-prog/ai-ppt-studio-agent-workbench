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


class GateBlockedError(AiPptError):
    """Raised when a user tries to pass a quality gate without its evidence."""

    def __init__(self, gate: str, missing_evidence: tuple[str, ...]) -> None:
        self.gate = gate
        self.missing_evidence = missing_evidence
        super().__init__(
            f"{gate} is missing required evidence: {', '.join(missing_evidence)}"
        )
