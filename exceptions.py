"""
Custom exceptions for AEGIS CLI tool.
Defines exception hierarchy for different error types.
"""


class AegisError(Exception):
    """Base exception for AEGIS."""

    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self):
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ClusterDiscoveryError(AegisError):
    """Cluster discovery related errors."""

    pass


class QuestionnaireError(AegisError):
    """Questionnaire related errors."""

    pass


class CatalogError(AegisError):
    """Policy catalog related errors."""

    pass


class AISelectionError(AegisError):
    """AI policy selection related errors."""

    pass


class ValidationError(AegisError):
    """Policy validation related errors."""

    pass


class ConfigurationError(AegisError):
    """Configuration related errors."""

    pass


class NetworkError(AegisError):
    """Network and external service related errors."""

    pass


class FileSystemError(AegisError):
    """File system operation related errors."""

    pass
