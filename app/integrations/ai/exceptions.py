class AIProviderError(Exception):
    """Provider integration failure."""

class AIConfigurationError(AIProviderError):
    pass

class AIResponseError(AIProviderError):
    def __init__(self, message: str, *, repair_context: dict | None = None):
        super().__init__(message)
        self.repair_context = repair_context


class AIProviderHTTPError(AIProviderError):
    def __init__(self, status_code: int, message: str, *, retryable: bool):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
