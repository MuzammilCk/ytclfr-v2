"""Custom exception hierarchy for YTCLFR."""


class YTCLFRError(Exception):
    """Base exception for domain-specific failures."""


class ConfigurationError(YTCLFRError):
    """Raised when configuration is missing or invalid."""


class ExternalCommandError(YTCLFRError):
    """Raised when an external process exits with failure."""


class VideoProcessingError(YTCLFRError):
    """Raised when video download or frame extraction fails."""


class OCRProcessingError(YTCLFRError):
    """Raised when OCR processing fails."""


class AIParsingError(YTCLFRError):
    """Raised when AI parsing fails."""


class SpotifyIntegrationError(YTCLFRError):
    """Raised when Spotify API integration fails."""


class RepositoryError(YTCLFRError):
    """Raised when persistence operations fail."""
