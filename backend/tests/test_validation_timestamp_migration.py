"""Regression coverage for legacy validation rows with NULL timestamps."""

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
from app.modules.timetable_validation.models import ValidationIssue, ValidationRun
from tests.facilities_test_support import create_facilities_test_context


class ValidationTimestampMigrationTests(unittest.TestCase):
    def test_legacy_null_timestamps_are_repaired_and_serialize_with_cors(self) -> None:
        timestamp_columns = [
            ValidationRun.__table__.c.started_at,
            ValidationRun.__table__.c.completed_at,
            ValidationRun.__table__.c.created_at,
            ValidationIssue.__table__.c.created_at,
        ]
        original_nullable = [column.nullable for column in timestamp_columns]
        for column in timestamp_columns:
            column.nullable = True
        try:
            context = create_facilities_test_context()
        finally:
            for column, nullable in zip(timestamp_columns, original_nullable, strict=True):
                column.nullable = nullable

        client = TestClient(app)
        db = context.session_factory()
        try:
            read_permission = Permission(resource="timetable_validation", action="read")
            db.add(read_permission)
            administrator_role = db.scalar(select(Role).where(Role.name == "Administrator"))
            administrator_role.permissions.append(read_permission)
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

            run_id = uuid4()
            issue_id = uuid4()
            db.execute(
                insert(ValidationRun).values(
                    id=run_id,
                    academic_term_id=term.id,
                    scope_type="COLLEGE",
                    status="FAILED",
                    total_checks=1,
                    passed_checks=0,
                    failed_checks=1,
                    warning_checks=0,
                    started_at=null(),
                    completed_at=null(),
                    created_by=administrator.id,
                    created_at=null(),
                )
            )
            db.execute(
                insert(ValidationIssue).values(
                    id=issue_id,
                    validation_run_id=run_id,
                    severity="ERROR",
                    issue_code="LEGACY_TEST_ISSUE",
                    message="Legacy validation issue",
                    created_at=null(),
                )
            )
            db.commit()

            # SQLite-compatible equivalent of migration 0024's timestamp repair.
            db.execute(text("UPDATE validation_runs SET started_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE started_at IS NULL"))
            db.execute(text("UPDATE validation_runs SET created_at = COALESCE(started_at, CURRENT_TIMESTAMP) WHERE created_at IS NULL"))
            db.execute(text("UPDATE validation_runs SET completed_at = COALESCE(started_at, created_at, CURRENT_TIMESTAMP) WHERE completed_at IS NULL"))
            db.execute(text("UPDATE validation_issues SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
            db.commit()

            origin = "http://localhost:3000"
            response = client.get(
                "/api/v1/timetable-validation/runs?page=1&page_size=1",
                headers=context.headers["administrator"] | {"Origin": origin},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.headers.get("access-control-allow-origin"), origin)
            self.assertEqual(response.json()["total"], 1)
            run = response.json()["items"][0]
            self.assertTrue(run["started_at"])
            self.assertTrue(run["completed_at"])
            self.assertTrue(run["created_at"])

            issues = client.get(
                f"/api/v1/timetable-validation/runs/{run_id}/issues",
                headers=context.headers["administrator"],
            )
            self.assertEqual(issues.status_code, 200, issues.text)
            self.assertEqual(issues.json()["total"], 1)
            self.assertTrue(issues.json()["items"][0]["created_at"])
        finally:
            db.close()
            client.close()
            context.close()


if __name__ == "__main__":
    unittest.main()
