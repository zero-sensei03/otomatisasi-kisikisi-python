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
        provider_error_type: str | None = None,
        provider_error_code: str | int | None = None,
        provider_error_status: str | None = None,
        provider_error_message: str | None = None,
        provider_error_details: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.diagnostic = diagnostic
        self.response_body = response_body
        self.response_metadata = response_metadata or {}
        self.request_duration_ms = request_duration_ms
        self.provider_error_type = provider_error_type
        self.provider_error_code = provider_error_code
        self.provider_error_status = provider_error_status
        self.provider_error_message = provider_error_message
        self.provider_error_details = provider_error_details
