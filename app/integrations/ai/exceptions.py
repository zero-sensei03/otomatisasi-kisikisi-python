class AIProviderError(Exception):
    """Provider integration failure."""

class AIConfigurationError(AIProviderError):
    pass

class AIResponseError(AIProviderError):
    def __init__(self, message: str, *, repair_context: dict | None = None):
        super().__init__(message)
        self.repair_context = repair_context


class AIProviderHTTPError(AIProviderError):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        retryable: bool,
        diagnostic: str | None = None,
        response_body: str | None = None,
        response_metadata: dict | None = None,
        request_duration_ms: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.diagnostic = diagnostic
        self.response_body = response_body
        self.response_metadata = response_metadata or {}
        self.request_duration_ms = request_duration_ms
