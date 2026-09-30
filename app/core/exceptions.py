class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
    ) -> None:
        self.message = message
        self.status_code = status_code

        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(
            message=message,
            status_code=404,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(
            message=message,
            status_code=403,
        )