"""Regression coverage for legacy timetable rows with NULL timestamps."""

import os
import unittest
from datetime import date
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient
from sqlalchemy import insert, null, select, text

from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import Permission, Role, User
from app.modules.timetables.models import Timetable
from tests.facilities_test_support import create_facilities_test_context


class TimetableTimestampMigrationTests(unittest.TestCase):
    def test_legacy_null_timestamp_repair_allows_list_serialization(self):
        created_column = Timetable.__table__.c.created_at
        updated_column = Timetable.__table__.c.updated_at
        original_nullable = (created_column.nullable, updated_column.nullable)
        created_column.nullable = True
        updated_column.nullable = True
        try:
            context = create_facilities_test_context()
        finally:
            created_column.nullable, updated_column.nullable = original_nullable

        client = TestClient(app)
        db = context.session_factory()
        try:
            permission = Permission(resource="timetables", action="read")
            db.add(permission)
            administrator_role = db.scalar(select(Role).where(Role.name == "Administrator"))
            administrator_role.permissions.append(permission)
            administrator = db.scalar(select(User).where(User.email == "admin.test@vce.ac.in"))
            term = AcademicTerm(
                academic_year="2026-27",
                term_name="I-I",
                year_number=1,
                semester_number=1,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 11, 1),
                is_active=True,
            )
            db.add(term)
            db.flush()
            legacy_id = uuid4()
            db.execute(
                insert(Timetable).values(
                    id=legacy_id,
                    academic_term_id=term.id,
                    scope_type="COLLEGE",
                    name="Legacy Timetable",
                    status="DRAFT",
                    created_by=administrator.id,
                    created_at=null(),
                    updated_at=null(),
                )
            )
            db.commit()

            # SQLite-compatible equivalent of migration 0020's PostgreSQL repair.
            db.execute(text("UPDATE timetables SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
            db.execute(
                text(
                    "UPDATE timetables SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                    "WHERE updated_at IS NULL"
                )
            )
            db.commit()

            response = client.get("/api/v1/timetables", headers=context.headers["administrator"])
            self.assertEqual(response.status_code, 200, response.text)
            item = next(row for row in response.json()["items"] if row["id"] == str(legacy_id))
            self.assertIsNotNone(item["created_at"])
            self.assertIsNotNone(item["updated_at"])
        finally:
            db.close()
            client.close()
            context.close()


if __name__ == "__main__":
    unittest.main()
