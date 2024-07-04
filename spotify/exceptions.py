from spotify.types.errors import ErrorSeverity, error_severity


class ParentException(Exception):
    def __init__(self, message: str, error: str = str) -> None:
        super().__init__(message)
        self.error = error
        self.severity = (
            error_severity[self.error]["status"]
            if self.error in error_severity
            else None
        )

        self.resource = (
            error_severity[self.error]["resource"]
            if self.severity == ErrorSeverity.Retry
            else None
        )


# Runtime exceptions (API errors)
class CaptchaException(ParentException):
    pass


# Final exceptions
class SolverError(ParentException):
    pass


# Login.py exceptions
class LoginError(ParentException):
    pass


# User.py exceptions
class UserError(ParentException):
    pass


class PlaylistError(ParentException):
    pass
