"""Unit tests for Program feature behavior."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.programs.models  # noqa: F401
from app.db.base import Base
from app.modules.authentication.models import Role
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.programs.schemas import ProgramCreate, ProgramUpdate
from app.modules.programs.services import ProgramService
from scripts import seed as seed_script


class ProgramServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.active_department = Department(
            department_code="CSE",
            department_name="Computer Science and Engineering",
            short_name="CSE",
        )
        self.inactive_department = Department(
            department_code="ECE",
            department_name="Electronics and Communication Engineering",
            short_name="ECE",
            is_active=False,
        )
        self.db.add_all([self.active_department, self.inactive_department])
        self.db.commit()
        self.service = ProgramService()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_create_normalizes_code_and_enforces_v1_rules(self) -> None:
        program = self.service.create_program(
            self.db,
            ProgramCreate(
                department_id=self.active_department.id,
                program_code=" btech-cse ",
                program_name="Bachelor of Technology in Computer Science and Engineering",
            ),
        )
        self.assertEqual(program.program_code, "BTECH-CSE")
        self.assertEqual(program.degree_type, "UG")
        self.assertEqual(program.duration_years, 4)

        with self.assertRaises(HTTPException) as duplicate_error:
            self.service.create_program(
                self.db,
                ProgramCreate(
                    department_id=self.active_department.id,
                    program_code="BTECH-CSE",
                    program_name="Duplicate Program",
                ),
            )
        self.assertEqual(duplicate_error.exception.status_code, 409)

        with self.assertRaises(HTTPException) as inactive_error:
            self.service.create_program(
                self.db,
                ProgramCreate(
                    department_id=self.inactive_department.id,
                    program_code="BTECH-ECE",
                    program_name="Bachelor of Technology in Electronics and Communication Engineering",
                ),
            )
        self.assertEqual(inactive_error.exception.status_code, 422)

        with self.assertRaises(ValidationError):
            ProgramCreate(
                department_id=self.active_department.id,
                program_code="MTECH-CSE",
                program_name="Master of Technology",
                degree_type="PG",
            )

    def test_search_filter_soft_delete_and_restore(self) -> None:
        cse_program = self.service.create_program(
            self.db,
            ProgramCreate(
                department_id=self.active_department.id,
                program_code="BTECH-CSE",
                program_name="Bachelor of Technology in Computer Science and Engineering",
            ),
        )
        self.service.create_program(
            self.db,
            ProgramCreate(
                department_id=self.active_department.id,
                program_code="BTECH-AIML",
                program_name="Bachelor of Technology in Artificial Intelligence",
            ),
        )

        results = self.service.list_programs(
            self.db,
            search="computer science",
            department_id=self.active_department.id,
            include_inactive=False,
            page=1,
            page_size=1,
        )
        self.assertEqual(results.total, 1)
        self.assertEqual(results.items[0].program_code, "BTECH-CSE")

        self.service.soft_delete_program(self.db, cse_program.id)
        self.assertFalse(self.service.get_program(self.db, cse_program.id).is_active)
        self.assertEqual(
            self.service.list_programs(
                self.db,
                search=None,
                department_id=self.active_department.id,
                include_inactive=False,
                page=1,
                page_size=20,
            ).total,
            1,
        )
        self.service.restore_program(self.db, cse_program.id)
        self.assertTrue(self.service.get_program(self.db, cse_program.id).is_active)

        updated = self.service.update_program(
            self.db,
            cse_program.id,
            ProgramUpdate(program_code="btech-csx"),
        )
        self.assertEqual(updated.program_code, "BTECH-CSX")

    def test_seed_is_idempotent_for_programs(self) -> None:
        self.inactive_department.is_active = True
        self.db.commit()
        original_session_local = seed_script.SessionLocal
        seed_script.SessionLocal = sessionmaker(bind=self.engine)
        try:
            seed_script.seed()
            seed_script.seed()
        finally:
            seed_script.SessionLocal = original_session_local

        self.assertEqual(self.db.scalar(select(func.count()).select_from(Program)), 8)
        self.assertEqual(
            self.db.scalar(select(func.count()).select_from(Program).where(Program.program_code == "BTECH-CSE")),
            1,
        )
        administrator = self.db.scalar(select(Role).where(Role.name == "Administrator"))
        timetable_coordinator = self.db.scalar(select(Role).where(Role.name == "Timetable Coordinator"))
        administrator_permissions = {(item.resource, item.action) for item in administrator.permissions}
        coordinator_permissions = {(item.resource, item.action) for item in timetable_coordinator.permissions}
        self.assertTrue({("programs", "read"), ("programs", "manage")} <= administrator_permissions)
        self.assertIn(("programs", "read"), coordinator_permissions)
        self.assertNotIn(("programs", "manage"), coordinator_permissions)


if __name__ == "__main__":
    unittest.main()
