"""Unit tests for Academic Term behavior."""

import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import app.modules.academic_terms.models  # noqa: F401
import app.modules.authentication.models  # noqa: F401
from app.db.base import Base
from app.modules.academic_terms.models import AcademicTerm
from app.modules.academic_terms.schemas import AcademicTermCreate, AcademicTermUpdate
from app.modules.academic_terms.services import AcademicTermService
from app.modules.authentication.models import Role
from scripts import seed as seed_script


class AcademicTermServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.service = AcademicTermService()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def payload(self, **overrides):
        values = {"academic_year": "2026-27", "term_name": "I-I", "year_number": 1, "semester_number": 1, "start_date": date(2026, 7, 1), "end_date": date(2026, 11, 30), "is_active": True, "is_first_year_term": True}
        values.update(overrides)
        return AcademicTermCreate(**values)

    def test_validates_mapping_dates_and_active_duplicate(self) -> None:
        term = self.service.create_term(self.db, self.payload())
        self.assertEqual(term.term_name, "I-I")
        with self.assertRaises(HTTPException) as duplicate:
            self.service.create_term(self.db, self.payload(term_name="I-I"))
        self.assertEqual(duplicate.exception.status_code, 409)
        with self.assertRaises(ValidationError):
            self.payload(term_name="I-II")
        with self.assertRaises(ValidationError):
            self.payload(start_date=date(2026, 12, 1), end_date=date(2026, 11, 30))

    def test_filters_soft_delete_restore_and_update_validation(self) -> None:
        term = self.service.create_term(self.db, self.payload())
        self.service.create_term(self.db, self.payload(term_name="II-I", year_number=2, is_first_year_term=False))
        results = self.service.list_terms(self.db, search="2026", academic_year="2026-27", year_number=1, semester_number=None, is_active=True, is_current=None, page=1, page_size=20)
        self.assertEqual(results.total, 1)
        self.service.soft_delete_term(self.db, term.id)
        self.assertFalse(self.service.get_term(self.db, term.id).is_active)
        self.service.restore_term(self.db, term.id)
        self.assertTrue(self.service.get_term(self.db, term.id).is_active)
        with self.assertRaises(HTTPException):
            self.service.update_term(self.db, term.id, AcademicTermUpdate(term_name="I-II"))

    def test_seed_is_idempotent_and_assigns_permissions(self) -> None:
        original = seed_script.SessionLocal
        seed_script.SessionLocal = sessionmaker(bind=self.engine)
        try:
            seed_script.seed(); seed_script.seed()
        finally:
            seed_script.SessionLocal = original
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AcademicTerm)), 4)
        admin = self.db.scalar(select(Role).where(Role.name == "Administrator"))
        coordinator = self.db.scalar(select(Role).where(Role.name == "Timetable Coordinator"))
        admin_permissions = {(item.resource, item.action) for item in admin.permissions}
        coordinator_permissions = {(item.resource, item.action) for item in coordinator.permissions}
        self.assertTrue({("academic_terms", "read"), ("academic_terms", "manage")} <= admin_permissions)
        self.assertIn(("academic_terms", "read"), coordinator_permissions)
        self.assertNotIn(("academic_terms", "manage"), coordinator_permissions)


if __name__ == "__main__":
    unittest.main()
