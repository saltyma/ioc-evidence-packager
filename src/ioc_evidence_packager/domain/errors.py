"""Domain and application errors safe to present to an analyst."""


class IOCEvidencePackagerError(Exception):
    """Base class for expected application errors."""


class ValidationError(IOCEvidencePackagerError):
    """Raised when user-supplied case metadata is invalid."""


class CaseNotFoundError(IOCEvidencePackagerError):
    """Raised when a requested case does not exist."""


class SchemaVersionError(IOCEvidencePackagerError):
    """Raised when a database schema cannot be opened safely."""
