"""Domain exceptions shared across the project."""


class PersonaliTreeError(Exception):
    """Base class for every PersonaliTree domain error."""


class ConfigurationError(PersonaliTreeError):
    """Raised when required runtime configuration is missing or invalid."""


class TargetNotFoundError(PersonaliTreeError):
    """Raised when no Target exists for the requested id."""


class TargetAlreadyQueuedError(PersonaliTreeError):
    """Raised when a target already has a scrape in flight."""


class BrowserLaunchError(PersonaliTreeError):
    """Raised when the Playwright browser cannot be started."""


class LLMError(PersonaliTreeError):
    """Base class for LLM request and response failures."""


class UnsupportedProviderError(ConfigurationError):
    """Raised when the configured LLM provider is not supported."""


class MissingCredentialError(LLMError, ConfigurationError):
    """Raised when no API key is configured for the selected provider."""


class LLMProviderError(LLMError):
    """Raised when a provider SDK call fails."""


class LLMResponseError(LLMError):
    """Raised when an LLM response cannot be parsed into score items."""
