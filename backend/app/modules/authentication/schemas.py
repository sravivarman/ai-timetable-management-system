"""Authentication feature request and response schemas."""

from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"


class UsernameMixin(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=USERNAME_PATTERN)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    resource: str
    action: str
    description: str | None


class RoleBase(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class RoleCreate(RoleBase):
    permission_ids: list[UUID] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    permission_ids: list[UUID] | None = None


class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    permissions: list[PermissionRead]


class UserCreate(UsernameMixin):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    role_ids: list[UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100, pattern=USERNAME_PATTERN)
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    is_active: bool | None = None
    role_ids: list[UUID] | None = None

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    email: EmailStr
    full_name: str
    is_active: bool
    roles: list[RoleRead]


class LoginRequest(UsernameMixin):
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
