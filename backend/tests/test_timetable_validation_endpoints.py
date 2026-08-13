"""Regression tests for validation-run persistence and deterministic listing."""

import os
import unittest
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.academic_terms.models import AcademicTerm
from app.modules.authentication.models import Permission, Role, User
from app.modules.timetable_validation.models import ValidationRun
from tests.facilities_test_support import create_facilities_test_context


class ValidationRunEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = create_facilities_test_context()
        db = self.ctx.session_factory()
        try:
            run_permission = Permission(resource="timetable_validation", action="run")
            read_permission = Permission(resource="timetable_validation", action="read")
            db.add_all([run_permission, read_permission])
            db.flush()
            role = db.scalar(select(Role).where(Role.name == "Administrator"))
            role.permissions.extend([run_permission, read_permission])
            administrator = db.scalar(select(User).where(User.email == "admin.test@vce.ac.in"))
            self.administrator_id = administrator.id
            self.term = AcademicTerm(
                academic_year="2026-27",
                term_name="I-I",
                year_number=1,
                semester_number=1,
                start_date=date(2026, 7, 1),
                end_date=date(2026, 11, 1),
                is_active=True,
            )
            db.add(self.term)
            db.commit()
        finally:
            db.close()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.ctx.close()

    def _persist_run(self, run_id: UUID, status: str, created_at: datetime) -> None:
        db = self.ctx.session_factory()
        try:
            failed = int(status == "FAILED")
            warnings = int(status == "WARNING")
            db.add(ValidationRun(
                id=run_id,
                academic_term_id=self.term.id,
                scope_type="COLLEGE",
                status=status,
                total_checks=1,
                passed_checks=1 - failed - warnings,
                failed_checks=failed,
                warning_checks=warnings,
                started_at=created_at,
                completed_at=created_at,
                created_by=self.administrator_id,
                created_at=created_at,
            ))
            db.commit()
        finally:
            db.close()

    def test_run_response_has_timestamps_and_persisted_summary(self) -> None:
        response = self.client.post(
            "/api/v1/timetable-validation/run",
            json={"academic_term_id": str(self.term.id), "scope_type": "COLLEGE"},
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertTrue(body["started_at"])
        self.assertTrue(body["completed_at"])
        self.assertTrue(body["created_at"])
        issues = self.client.get(
            f"/api/v1/timetable-validation/runs/{body['id']}/issues",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(issues.status_code, 200, issues.text)
        self.assertEqual(issues.json()["total"], body["failed_checks"] + body["warning_checks"])
        self.assertEqual(body["total_checks"], body["passed_checks"] + body["failed_checks"] + body["warning_checks"])
        self.assertTrue(all(item["created_at"] for item in issues.json()["items"]))
        db = self.ctx.session_factory()
        try:
            saved = db.scalar(select(ValidationRun).where(ValidationRun.id == UUID(body["id"])))
            self.assertEqual(body["total_checks"], saved.total_checks)
            self.assertEqual(body["failed_checks"], saved.failed_checks)
        finally:
            db.close()

    def test_dashboard_page_returns_latest_warning_before_older_failed_run(self) -> None:
        timestamp = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
        older_id = UUID("00000000-0000-0000-0000-000000000010")
        latest_id = UUID("00000000-0000-0000-0000-000000000020")
        self._persist_run(older_id, "FAILED", timestamp)
        self._persist_run(latest_id, "WARNING", timestamp + timedelta(hours=1))

        listing = self.client.get(
            "/api/v1/timetable-validation/runs?page=1&page_size=10",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(listing.status_code, 200, listing.text)
        self.assertEqual([item["id"] for item in listing.json()["items"]], [str(latest_id), str(older_id)])

        dashboard = self.client.get(
            "/api/v1/timetable-validation/runs?page=1&page_size=1",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(dashboard.json()["items"][0]["id"], str(latest_id))
        self.assertEqual(dashboard.json()["items"][0]["status"], "WARNING")

        filtered = self.client.get(
            "/api/v1/timetable-validation/runs?status=FAILED&page=1&page_size=1",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(filtered.json()["items"][0]["id"], str(older_id))

    def test_equal_timestamps_use_descending_id_tie_breaker(self) -> None:
        timestamp = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
        lower_id = UUID("00000000-0000-0000-0000-000000000001")
        higher_id = UUID("00000000-0000-0000-0000-000000000002")
        self._persist_run(lower_id, "PASSED", timestamp)
        self._persist_run(higher_id, "PASSED", timestamp)
        response = self.client.get(
            "/api/v1/timetable-validation/runs?page=1&page_size=2",
            headers=self.ctx.headers["administrator"],
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item["id"] for item in response.json()["items"]], [str(higher_id), str(lower_id)])


if __name__ == "__main__":
    unittest.main()
