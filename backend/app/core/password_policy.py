"""Shared policy for credentials set by users, administrators, and seeds."""

from typing import Annotated

from pydantic import StringConstraints, ValidatorFunctionWrapHandler, WrapValidator
from pydantic_core import PydanticCustomError


MINIMUM_PASSWORD_LENGTH = 8
PASSWORD_MINIMUM_MESSAGE = "Password must be at least 8 characters."
MAXIMUM_PASSWORD_LENGTH = 128


def validate_new_password(password: str) -> str:
    """Validate a newly assigned password without affecting existing hashes."""
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise PydanticCustomError("password_too_short", PASSWORD_MINIMUM_MESSAGE)
    return password


def _validate_new_password_schema(value: object, handler: ValidatorFunctionWrapHandler) -> str:
    if isinstance(value, str):
        validate_new_password(value)
    return handler(value)


NewPassword = Annotated[
    str,
    StringConstraints(min_length=MINIMUM_PASSWORD_LENGTH, max_length=MAXIMUM_PASSWORD_LENGTH),
    WrapValidator(_validate_new_password_schema),
]
