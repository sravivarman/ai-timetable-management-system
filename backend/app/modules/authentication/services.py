"""Authentication and authorization use cases."""

from uuid import UUID
import jwt
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.modules.authentication.models import Role, User
from app.modules.authentication.repositories import PermissionRepository, RoleRepository, UserRepository
from app.modules.authentication.schemas import RoleCreate, RoleUpdate, UserCreate, UserUpdate

APPROVED_LOGIN_ROLE_NAMES = {"Administrator", "Principal", "Dean", "Timetable Coordinator", "REPORT_VIEWER"}


class AuthenticationService:
    def __init__(self) -> None:
        self.users = UserRepository()
        self.roles = RoleRepository()
        self.permissions = PermissionRepository()

    def authenticate(self, db: Session, username: str, password: str) -> User:
        user = self.users.get_by_username(db, username)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
        return user

    def token_pair(self, user: User) -> dict[str, str]:
        return {"access_token": create_access_token(user.id, user.token_version), "refresh_token": create_refresh_token(user.id, user.token_version), "token_type": "bearer"}

    def refresh(self, db: Session, refresh_token: str) -> dict[str, str]:
        return self.token_pair(self._token_user(db, refresh_token, "refresh"))

    def logout(self, db: Session, user: User) -> None:
        user.token_version += 1
        self.users.save(db, user)

    def current_user(self, db: Session, access_token: str) -> User:
        return self._token_user(db, access_token, "access")

    def _token_user(self, db: Session, token: str, expected_type: str) -> User:
        try:
            payload = decode_token(token, expected_type)
            user_id, token_version = UUID(payload["sub"]), int(payload["ver"])
        except (jwt.PyJWTError, KeyError, ValueError, TypeError) as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from error
        user = self.users.get(db, user_id)
        if user is None or not user.is_active or user.token_version != token_version:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return user

    def create_user(self, db: Session, data: UserCreate) -> User:
        self._ensure_unique_username(db, data.username)
        self._ensure_unique_email(db, data.email)
        roles = self._roles_or_422(db, data.role_ids)
        if self.users.count(db) == 0 and not roles:
            administrator_role = self.roles.get_by_name(db, "Administrator")
            if administrator_role is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Administrator role is not seeded")
            roles = [administrator_role]
        elif len(roles) != 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A login account must have exactly one approved role")
        return self.users.save(db, User(username=data.username, email=str(data.email).lower(), full_name=data.full_name, password_hash=hash_password(data.password), roles=roles))

    def update_user(self, db: Session, user: User, data: UserUpdate) -> User:
        changes = data.model_dump(exclude_unset=True, exclude={"password", "role_ids"})
        if "username" in changes:
            self._ensure_unique_username(db, changes["username"], exclude_user_id=user.id)
        if "email" in changes:
            self._ensure_unique_email(db, changes["email"], exclude_user_id=user.id)
            changes["email"] = str(changes["email"]).lower()
        for field, value in changes.items():
            setattr(user, field, value)
        if data.password is not None:
            user.password_hash, user.token_version = hash_password(data.password), user.token_version + 1
        if data.role_ids is not None:
            user.roles, user.token_version = self._roles_or_422(db, data.role_ids), user.token_version + 1
        return self.users.save(db, user)

    def change_password(self, db: Session, user: User, current_password: str, new_password: str) -> User:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        user.password_hash = hash_password(new_password)
        user.token_version += 1
        return self.users.save(db, user)

    def create_role(self, db: Session, data: RoleCreate) -> Role:
        permissions = self._permissions_or_422(db, data.permission_ids)
        try:
            return self.roles.save(db, Role(name=data.name, description=data.description, permissions=permissions))
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists") from error

    def update_role(self, db: Session, role: Role, data: RoleUpdate) -> Role:
        for field, value in data.model_dump(exclude_unset=True, exclude={"permission_ids"}).items():
            setattr(role, field, value)
        if data.permission_ids is not None:
            role.permissions = self._permissions_or_422(db, data.permission_ids)
        try:
            return self.roles.save(db, role)
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists") from error

    def _ensure_unique_email(self, db: Session, email: str, exclude_user_id: UUID | None = None) -> None:
        existing = self.users.get_by_email(db, str(email))
        if existing is not None and existing.id != exclude_user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    def _ensure_unique_username(self, db: Session, username: str, exclude_user_id: UUID | None = None) -> None:
        existing = self.users.get_by_username(db, username)
        if existing is not None and existing.id != exclude_user_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already registered")

    def _roles_or_422(self, db: Session, role_ids: list[UUID]) -> list[Role]:
        roles = self.roles.get_many(db, role_ids)
        if len(roles) != len(set(role_ids)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more roles do not exist")
        unsupported = [role.name for role in roles if role.name not in APPROVED_LOGIN_ROLE_NAMES]
        if unsupported:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more roles cannot be assigned to login accounts")
        if role_ids and len(roles) != 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A login account must have exactly one approved role")
        return roles

    def _permissions_or_422(self, db: Session, permission_ids: list[UUID]):
        permissions = self.permissions.get_many(db, permission_ids)
        if len(permissions) != len(set(permission_ids)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more permissions do not exist")
        return permissions


authentication_service = AuthenticationService()
