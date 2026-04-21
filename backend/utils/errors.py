"""Custom exceptions for the ship dataset pipeline."""


class PipelineError(Exception):
    """Base class for all pipeline-specific failures."""


class ConfigurationError(PipelineError):
    """Raised when runtime configuration is invalid."""


class EarthEnginePipelineError(PipelineError):
    """Raised for Earth Engine initialization or export failures."""


class ProcessingError(PipelineError):
    """Raised for local file and image-processing failures."""
