"""HTTP integration tests for Laboratory endpoints only."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient

from app.main import app
from tests.facilities_test_support import create_facilities_test_context


class LaboratoryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.context.close()

    def payload(self, code: str, room_number: str, department_id=None) -> dict:
        return {
            "laboratory_code": code,
            "laboratory_name": f"{code} Laboratory",
            "room_number": room_number,
            "owning_department_id": str(department_id or self.context.active_department.id),
            "is_shareable_across_departments": True,
            "is_available_all_periods": True,
        }

    def create(self, code: str, room_number: str, headers=None) -> dict:
        response = self.client.post(
            "/api/v1/laboratories",
            json=self.payload(code, room_number),
            headers=headers or self.context.headers["administrator"],
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_authorization(self) -> None:
        self.create("CSELAB1", "L101")
        self.create("CSELAB2", "L102", self.context.headers["coordinator"])
        self.assertEqual(
            self.client.post(
                "/api/v1/laboratories",
                json=self.payload("CSELAB3", "L103"),
                headers=self.context.headers["hod"],
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/laboratories",
                json=self.payload("CSELAB4", "L104"),
                headers=self.context.headers["unauthorized"],
            ).status_code,
            403,
        )

    def test_crud_search_filters_pagination_and_lifecycle(self) -> None:
        first = self.create("CSELAB1", "L101")
        self.create("ECELAB1", "L102")
        self.create("MECLAB1", "L201")

        listed = self.client.get("/api/v1/laboratories", headers=self.context.headers["hod"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["total"], 3)

        by_id = self.client.get(f"/api/v1/laboratories/{first['id']}", headers=self.context.headers["hod"])
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_id.json()["laboratory_code"], "CSELAB1")

        updated_payload = self.payload("CSELAB1", "L101") | {
            "laboratory_name": "Updated CSE Laboratory",
            "is_shareable_across_departments": False,
        }
        updated = self.client.put(
            f"/api/v1/laboratories/{first['id']}",
            json=updated_payload,
            headers=self.context.headers["administrator"],
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["laboratory_name"], "Updated CSE Laboratory")

        search = self.client.get("/api/v1/laboratories?search=MECLAB1", headers=self.context.headers["hod"])
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["total"], 1)
        filtered = self.client.get(
            "/api/v1/laboratories?is_shareable_across_departments=false",
            headers=self.context.headers["hod"],
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["total"], 1)
        paged = self.client.get("/api/v1/laboratories?page=1&page_size=2", headers=self.context.headers["hod"])
        self.assertEqual(paged.status_code, 200)
        self.assertEqual(len(paged.json()["items"]), 2)

        duplicate_code = self.client.post(
            "/api/v1/laboratories",
            json=self.payload("CSELAB1", "L999"),
            headers=self.context.headers["administrator"],
        )
        self.assertEqual(duplicate_code.status_code, 409)
        duplicate_room = self.client.post(
            "/api/v1/laboratories",
            json=self.payload("CSELAB9", "L101"),
            headers=self.context.headers["administrator"],
        )
        self.assertEqual(duplicate_room.status_code, 409)
        inactive_department = self.client.post(
            "/api/v1/laboratories",
            json=self.payload("CSELAB8", "L888", self.context.inactive_department.id),
            headers=self.context.headers["administrator"],
        )
        self.assertEqual(inactive_department.status_code, 422)

        deleted = self.client.delete(f"/api/v1/laboratories/{first['id']}", headers=self.context.headers["administrator"])
        self.assertEqual(deleted.status_code, 204)
        inactive_list = self.client.get("/api/v1/laboratories?is_active=false", headers=self.context.headers["hod"])
        self.assertEqual(inactive_list.status_code, 200)
        self.assertEqual(inactive_list.json()["total"], 1)
        restored = self.client.post(f"/api/v1/laboratories/{first['id']}/restore", headers=self.context.headers["administrator"])
        self.assertEqual(restored.status_code, 200)
        self.assertTrue(restored.json()["is_active"])

    def test_generic_availability_modes_preserve_legacy_boolean_contract(self) -> None:
        selected = self.payload("SELECTED", "L301") | {"availability_mode": "ONLY_SELECTED"}
        created = self.client.post("/api/v1/laboratories", json=selected, headers=self.context.headers["administrator"])
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["availability_mode"], "ONLY_SELECTED")
        self.assertFalse(created.json()["is_available_all_periods"])

        legacy = self.payload("LEGACY", "L302") | {"is_available_all_periods": False}
        legacy.pop("availability_mode", None)
        response = self.client.post("/api/v1/laboratories", json=legacy, headers=self.context.headers["administrator"])
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["availability_mode"], "EXCEPT_BLOCKED")

        filtered = self.client.get("/api/v1/laboratories?availability_mode=ONLY_SELECTED", headers=self.context.headers["hod"])
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual([row["laboratory_code"] for row in filtered.json()["items"]], ["SELECTED"])
