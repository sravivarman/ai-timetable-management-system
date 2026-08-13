"""Authentication, user, and role API endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user, require_permission, require_user_management_or_bootstrap
from app.modules.authentication.models import User
from app.modules.authentication.schemas import RefreshRequest, RoleCreate, RoleRead, RoleUpdate, TokenPair, UserCreate, UserRead, UserUpdate
from app.modules.authentication.services import authentication_service

router = APIRouter()
auth_router = APIRouter(prefix="/auth", tags=["authentication"])
roles_router = APIRouter(prefix="/roles", tags=["roles"])
users_router = APIRouter(prefix="/users", tags=["users"])
manage_roles = Depends(require_permission("roles", "manage"))
manage_users = Depends(require_permission("users", "manage"))


@auth_router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in with OAuth2 password flow and receive a token pair",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenPair:
    """Authenticate using OAuth2's form fields; ``username`` is the user's email."""
    user = authentication_service.authenticate(db, form_data.username, form_data.password)
    return TokenPair.model_validate(authentication_service.token_pair(user))


@auth_router.post("/refresh", response_model=TokenPair, summary="Refresh an access and refresh token pair")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    return TokenPair.model_validate(authentication_service.refresh(db, payload.refresh_token))


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Invalidate all tokens for the current user")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    authentication_service.logout(db, current_user)


@auth_router.get("/me", response_model=UserRead, summary="Get the current user")
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@roles_router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED, dependencies=[manage_roles])
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    return authentication_service.create_role(db, payload)


@roles_router.get("", response_model=list[RoleRead], dependencies=[manage_roles])
def list_roles(db: Session = Depends(get_db)):
    return authentication_service.roles.list(db)


@roles_router.put("/{role_id}", response_model=RoleRead, dependencies=[manage_roles])
def update_role(role_id: UUID, payload: RoleUpdate, db: Session = Depends(get_db)):
    role = authentication_service.roles.get(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return authentication_service.update_role(db, role, payload)


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_roles])
def delete_role(role_id: UUID, db: Session = Depends(get_db)) -> Response:
    role = authentication_service.roles.get(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    authentication_service.roles.delete(db, role)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User | None = Depends(require_user_management_or_bootstrap)) -> User:
    return authentication_service.create_user(db, payload)


@users_router.get("", response_model=list[UserRead], dependencies=[manage_users])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return authentication_service.users.list(db)


@users_router.get("/{user_id}", response_model=UserRead, dependencies=[manage_users])
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    user = authentication_service.users.get(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@users_router.put("/{user_id}", response_model=UserRead, dependencies=[manage_users])
def update_user(user_id: UUID, payload: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = authentication_service.users.get(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return authentication_service.update_user(db, user, payload)


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[manage_users])
def delete_user(user_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    user = authentication_service.users.get(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Users cannot delete themselves")
    authentication_service.users.delete(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(auth_router)
router.include_router(roles_router)
router.include_router(users_router)
