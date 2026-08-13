"""SQLAlchemy repositories for the authentication feature."""

from uuid import UUID
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.authentication.models import Permission, Role, User


class UserRepository:
    def get(self, db: Session, user_id: UUID) -> User | None:
        statement: Select[tuple[User]] = select(User).where(User.id == user_id).options(selectinload(User.roles))
        return db.scalar(statement)

    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email.lower()).options(selectinload(User.roles)))

    def list(self, db: Session) -> list[User]:
        return list(db.scalars(select(User).order_by(User.email).options(selectinload(User.roles))))

    def count(self, db: Session) -> int:
        return int(db.scalar(select(func.count()).select_from(User)) or 0)

    def save(self, db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def delete(self, db: Session, user: User) -> None:
        db.delete(user)
        db.commit()


class RoleRepository:
    def get_by_name(self, db: Session, name: str) -> Role | None:
        return db.scalar(select(Role).where(Role.name == name).options(selectinload(Role.permissions)))

    def get(self, db: Session, role_id: UUID) -> Role | None:
        return db.scalar(select(Role).where(Role.id == role_id).options(selectinload(Role.permissions)))

    def get_many(self, db: Session, role_ids: list[UUID]) -> list[Role]:
        if not role_ids:
            return []
        return list(db.scalars(select(Role).where(Role.id.in_(role_ids)).options(selectinload(Role.permissions))))

    def list(self, db: Session) -> list[Role]:
        return list(db.scalars(select(Role).order_by(Role.name).options(selectinload(Role.permissions))))

    def save(self, db: Session, role: Role) -> Role:
        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    def delete(self, db: Session, role: Role) -> None:
        db.delete(role)
        db.commit()


class PermissionRepository:
    def get_many(self, db: Session, permission_ids: list[UUID]) -> list[Permission]:
        if not permission_ids:
            return []
        return list(db.scalars(select(Permission).where(Permission.id.in_(permission_ids))))
