"""Authentication feature dependencies."""

from collections.abc import Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.authentication.models import User
from app.modules.authentication.services import authentication_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False)


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    return authentication_service.current_user(db, token)


def require_permission(resource: str, action: str) -> Callable[..., User]:
    required = (resource, action)

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        granted = {(permission.resource, permission.action) for role in current_user.roles for permission in role.permissions}
        if required not in granted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


def require_user_management_or_bootstrap(db: Session = Depends(get_db), token: str | None = Depends(optional_oauth2_scheme)) -> User | None:
    if authentication_service.users.count(db) == 0:
        return None
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    current_user = authentication_service.current_user(db, token)
    granted = {(permission.resource, permission.action) for role in current_user.roles for permission in role.permissions}
    if ("users", "manage") not in granted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user
