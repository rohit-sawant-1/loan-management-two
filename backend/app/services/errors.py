"""
Errors the services raise. Routers turn these into HTTP answers.

Keeping services free of HTTP means the same logic can be called from a test,
a script, or a Phase 5 agent without a web request in sight.
"""


class ServiceError(Exception):
    """Base class. `message` is safe to show to the user."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EmailAlreadyRegistered(ServiceError):
    """Maps to 409 Conflict."""


class InvalidCredentials(ServiceError):
    """Maps to 401. The message never says which field was wrong."""


class NotFound(ServiceError):
    """Maps to 404."""


class RuleViolation(ServiceError):
    """A business rule said no. Maps to 400 or 422 depending on the endpoint."""


class FieldProblems(RuleViolation):
    """
    Piece 33: several fields were wrong at once. `fields` maps each field's
    key to its own message, so the screen can show each one beside its box.
    """

    def __init__(self, message: str, fields: dict[str, str]):
        super().__init__(message)
        self.fields = fields


class Forbidden(ServiceError):
    """The user is real but not allowed to do this. Maps to 403."""
