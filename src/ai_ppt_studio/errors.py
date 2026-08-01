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
