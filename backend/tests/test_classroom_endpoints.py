"""HTTP integration tests for Classroom endpoints only."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient

from app.main import app
from tests.facilities_test_support import create_facilities_test_context


class ClassroomEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.context.close()

    def payload(self, number: str, department_id=None) -> dict:
        return {
            "room_number": number,
            "room_name": f"Room {number}",
            "building_name": "Academic Block",
            "floor_number": 3,
            "owning_department_id": str(department_id or self.context.active_department.id),
            "is_primary_classroom": True,
            "is_shareable": True,
        }

    def create(self, number: str, headers=None) -> dict:
        response = self.client.post("/api/v1/classrooms", json=self.payload(number), headers=headers or self.context.headers["administrator"])
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_authorization(self) -> None:
        self.create("3201")
        self.create("3202", self.context.headers["coordinator"])
        self.assertEqual(self.client.post("/api/v1/classrooms", json=self.payload("3203"), headers=self.context.headers["hod"]).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/classrooms", json=self.payload("3204"), headers=self.context.headers["unauthorized"]).status_code, 403)

    def test_crud_search_filters_pagination_and_lifecycle(self) -> None:
        first = self.create("3201")
        self.create("3202")
        self.create("4201")

        listed = self.client.get("/api/v1/classrooms", headers=self.context.headers["hod"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 3)

        by_id = self.client.get(f"/api/v1/classrooms/{first['id']}", headers=self.context.headers["hod"])
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_id.json()["room_number"], "3201")

        updated_payload = self.payload("3201") | {"room_name": "Updated Classroom", "is_shareable": False}
        updated = self.client.put(f"/api/v1/classrooms/{first['id']}", json=updated_payload, headers=self.context.headers["administrator"])
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["room_name"], "Updated Classroom")

        search = self.client.get("/api/v1/classrooms?search=4201", headers=self.context.headers["hod"])
        self.assertEqual(search.json()["total"], 1)
        filtered = self.client.get("/api/v1/classrooms?is_shareable=false", headers=self.context.headers["hod"])
        self.assertEqual(filtered.json()["total"], 1)
        paged = self.client.get("/api/v1/classrooms?page=1&page_size=2", headers=self.context.headers["hod"])
        self.assertEqual(len(paged.json()["items"]), 2)

        duplicate = self.client.post("/api/v1/classrooms", json=self.payload("3201"), headers=self.context.headers["administrator"])
        self.assertEqual(duplicate.status_code, 409)
        inactive = self.client.post("/api/v1/classrooms", json=self.payload("9999", self.context.inactive_department.id), headers=self.context.headers["administrator"])
        self.assertEqual(inactive.status_code, 422)

        deleted = self.client.delete(f"/api/v1/classrooms/{first['id']}", headers=self.context.headers["administrator"])
        self.assertEqual(deleted.status_code, 204)
        inactive_list = self.client.get("/api/v1/classrooms?is_active=false", headers=self.context.headers["hod"])
        self.assertEqual(inactive_list.json()["total"], 1)
        restored = self.client.post(f"/api/v1/classrooms/{first['id']}/restore", headers=self.context.headers["administrator"])
        self.assertEqual(restored.status_code, 200)
        self.assertTrue(restored.json()["is_active"])
