"""Declarative SQLAlchemy metadata shared by future ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM entities."""
