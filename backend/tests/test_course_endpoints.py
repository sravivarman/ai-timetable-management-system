"""HTTP regression tests for Course master endpoints."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient

from app.main import app
from tests.facilities_test_support import create_facilities_test_context


class CourseEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.context.close()

    def payload(self, code: str) -> dict:
        return {
            "course_code": code,
            "course_name": "Engineering Mathematics",
            "offering_department_id": str(self.context.active_department.id),
            "course_type": "THEORY",
            "weekly_periods": 4,
        }

    def test_authorized_roles_can_manage_course_lifecycle(self) -> None:
        created = self.client.post("/api/v1/courses", json=self.payload("a9001"), headers=self.context.headers["administrator"])
        self.assertEqual(created.status_code, 201, created.text)
        course_id = created.json()["id"]
        coordinator = self.client.post("/api/v1/courses", json=self.payload("A9002"), headers=self.context.headers["coordinator"])
        self.assertEqual(coordinator.status_code, 201, coordinator.text)
        listed = self.client.get("/api/v1/courses?search=mathematics", headers=self.context.headers["hod"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 2)
        deleted = self.client.delete(f"/api/v1/courses/{course_id}", headers=self.context.headers["hod"])
        self.assertEqual(deleted.status_code, 204)
        restored = self.client.post(f"/api/v1/courses/{course_id}/restore", headers=self.context.headers["hod"])
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["course_code"], "A9001")
