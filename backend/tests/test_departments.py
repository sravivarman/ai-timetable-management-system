"""Unit tests for Department feature behavior."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
from app.db.base import Base
from app.modules.authentication.models import Role
from app.modules.departments.models import Department
from app.modules.departments.schemas import DepartmentCreate, DepartmentUpdate
from app.modules.departments.services import DepartmentService
from scripts import seed as seed_script


class DepartmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.service = DepartmentService()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_create_normalizes_code_and_rejects_duplicates(self) -> None:
        department = self.service.create_department(
            self.db,
            DepartmentCreate(department_code=" cse ", department_name="Computer Science", short_name="CSE"),
        )
        self.assertEqual(department.department_code, "CSE")

        with self.assertRaises(HTTPException) as error:
            self.service.create_department(
                self.db,
                DepartmentCreate(department_code="CSE", department_name="Duplicate", short_name="DUP"),
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_search_pagination_soft_delete_and_restore(self) -> None:
        cse = self.service.create_department(
            self.db,
            DepartmentCreate(department_code="CSE", department_name="Computer Science and Engineering", short_name="CSE"),
        )
        self.service.create_department(
            self.db,
            DepartmentCreate(department_code="ECE", department_name="Electronics and Communication Engineering", short_name="ECE"),
        )
        self.service.create_department(
            self.db,
            DepartmentCreate(department_code="MEC", department_name="Mechanical Engineering", short_name="MEC"),
        )

        results = self.service.list_departments(
            self.db, search="computer", include_inactive=False, page=1, page_size=1
        )
        self.assertEqual(results.total, 1)
        self.assertEqual(results.items[0].department_code, "CSE")

        self.service.soft_delete_department(self.db, cse.id)
        self.assertFalse(self.service.get_department(self.db, cse.id).is_active)
        self.assertEqual(
            self.service.list_departments(self.db, search=None, include_inactive=False, page=1, page_size=20).total,
            2,
        )
        self.service.restore_department(self.db, cse.id)
        self.assertTrue(self.service.get_department(self.db, cse.id).is_active)

        updated = self.service.update_department(
            self.db,
            cse.id,
            DepartmentUpdate(department_code="csx", short_name="CSX"),
        )
        self.assertEqual(updated.department_code, "CSX")

    def test_seed_is_idempotent_for_departments(self) -> None:
        original_session_local = seed_script.SessionLocal
        seed_script.SessionLocal = sessionmaker(bind=self.engine)
        try:
            seed_script.seed()
            seed_script.seed()
        finally:
            seed_script.SessionLocal = original_session_local

        self.assertEqual(self.db.scalar(select(func.count()).select_from(Department)), 8)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(Department).where(Department.department_code == "CSE")),
            1,
        )
        administrator = self.db.scalar(select(Role).where(Role.name == "Administrator"))
        timetable_coordinator = self.db.scalar(select(Role).where(Role.name == "Timetable Coordinator"))
        administrator_permissions = {(item.resource, item.action) for item in administrator.permissions}
        coordinator_permissions = {(item.resource, item.action) for item in timetable_coordinator.permissions}
        self.assertTrue({("departments", "view"), ("departments", "manage")} <= administrator_permissions)
        self.assertIn(("departments", "view"), coordinator_permissions)
        self.assertNotIn(("departments", "manage"), coordinator_permissions)


if __name__ == "__main__":
    unittest.main()
