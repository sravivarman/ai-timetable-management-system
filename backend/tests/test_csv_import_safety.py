"""Regression tests for reviewed CSV mutation stale-data protection."""

import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.authentication.models import Permission, Role
from app.modules.departments.models import Department
from tests.facilities_test_support import create_facilities_test_context


class CsvImportSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        with self.context.session_factory() as db:
            role = db.scalar(select(Role).where(Role.name == "Administrator"))
            role.permissions.extend([
                Permission(resource="departments", action="view"),
                Permission(resource="departments", action="manage"),
            ])
            department = db.get(Department, self.context.active_department.id)
            department.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            db.commit()
            self.department_id = str(department.id)
            self.baseline = department.updated_at.isoformat()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.context.close()

    def test_matching_import_baseline_uses_normal_domain_update(self) -> None:
        headers = {
            **self.context.headers["administrator"],
            "X-Import-Target-Id": self.department_id,
            "X-Import-Expected-Updated-At": self.baseline,
        }
        response = self.client.put(f"/api/v1/departments/{self.department_id}", json={"department_name": "Updated Department"}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["department_name"], "Updated Department")

    def test_stale_import_baseline_returns_conflict_without_overwrite(self) -> None:
        with self.context.session_factory() as db:
            department = db.get(Department, self.context.active_department.id)
            department.department_name = "Concurrent Administrator Change"
            department.updated_at = datetime.fromisoformat(self.baseline) + timedelta(minutes=1)
            db.commit()
        headers = {
            **self.context.headers["administrator"],
            "X-Import-Target-Id": self.department_id,
            "X-Import-Expected-Updated-At": self.baseline,
        }
        response = self.client.put(f"/api/v1/departments/{self.department_id}", json={"department_name": "Imported Change"}, headers=headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("changed since import preview", response.json()["detail"])
        with self.context.session_factory() as db:
            self.assertEqual(db.get(Department, self.context.active_department.id).department_name, "Concurrent Administrator Change")


if __name__ == "__main__":
    unittest.main()
