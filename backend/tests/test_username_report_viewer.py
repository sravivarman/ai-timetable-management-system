"""Username authentication and read-only Report Viewer endpoint guarantees."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.modules.authentication.models import Permission, Role, User
from tests.facilities_test_support import create_facilities_test_context


class UsernameReportViewerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        db = self.context.session_factory()
        try:
            reports_read = Permission(resource="reports", action="read", description="Read reports")
            users_manage = Permission(resource="users", action="manage", description="Manage users")
            viewer_role = Role(name="REPORT_VIEWER", description="Read-only reports", permissions=[reports_read])
            administrator = db.scalar(select(Role).where(Role.name == "Administrator"))
            administrator.permissions.append(users_manage)
            self.viewer = User(username="reportviewer", email="viewer@vce.ac.in", full_name="Report Viewer", password_hash=hash_password("ViewerPassword123"), roles=[viewer_role])
            db.add_all([viewer_role, self.viewer])
            db.commit()
            self.context.headers["viewer"] = {"Authorization": f"Bearer {create_access_token(self.viewer.id, self.viewer.token_version)}"}
        finally:
            db.close()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.context.close()

    def test_username_only_login_and_safe_failure_message(self) -> None:
        response = self.client.post("/api/v1/auth/login", data={"username": "REPORTVIEWER", "password": "ViewerPassword123"})
        self.assertEqual(response.status_code, 200)
        for username, password in [("viewer@vce.ac.in", "ViewerPassword123"), ("reportviewer", "WrongPassword123")]:
            denied = self.client.post("/api/v1/auth/login", data={"username": username, "password": password})
            self.assertEqual(denied.status_code, 401)
            self.assertEqual(denied.json()["detail"], "Invalid username or password")

    def test_report_viewer_can_use_every_report_and_export_format(self) -> None:
        headers = self.context.headers["viewer"]
        definitions = self.client.get("/api/v1/reports/definitions", headers=headers)
        self.assertEqual(definitions.status_code, 200)
        self.assertEqual(len(definitions.json()), 6)
        options = self.client.get("/api/v1/reports/filter-options", headers=headers)
        self.assertEqual(options.status_code, 200)
        self.assertEqual(set(options.json()), {"academic_terms", "departments", "programs", "sections", "courses", "faculty"})
        for definition in definitions.json():
            payload = {
                "report_key": definition["key"],
                "filters": {},
                "selected_columns": definition["default_columns"],
                "sort_fields": definition["default_sort"],
                "page": 1,
                "page_size": 50,
            }
            self.assertEqual(self.client.post("/api/v1/reports/preview", headers=headers, json=payload).status_code, 200)
            for export_format in ("xlsx", "csv", "docx", "pdf"):
                exported = self.client.post(f"/api/v1/reports/export?format={export_format}", headers=headers, json=payload)
                self.assertEqual(exported.status_code, 200, f"{definition['key']} {export_format}")

    def test_report_viewer_write_and_self_password_change_are_forbidden(self) -> None:
        headers = self.context.headers["viewer"]
        requests = [
            ("post", "/api/v1/faculty"),
            ("post", "/api/v1/courses"),
            ("post", "/api/v1/course-offerings"),
            ("post", "/api/v1/faculty-allocations/theory"),
            ("post", "/api/v1/laboratories"),
            ("post", "/api/v1/timetables"),
            ("post", "/api/v1/users"),
        ]
        for method, path in requests:
            response = getattr(self.client, method)(path, headers=headers, json={})
            self.assertEqual(response.status_code, 403, path)
        change = self.client.post("/api/v1/auth/change-password", headers=headers, json={"current_password": "ViewerPassword123", "new_password": "ViewerPassword456"})
        self.assertEqual(change.status_code, 403)

    def test_administrator_can_reset_report_viewer_password(self) -> None:
        before = self.viewer.password_hash
        response = self.client.put(f"/api/v1/users/{self.viewer.id}", headers=self.context.headers["administrator"], json={"password": "ResetByAdmin123"})
        self.assertEqual(response.status_code, 200)
        db = self.context.session_factory()
        try:
            updated = db.get(User, self.viewer.id)
            self.assertNotEqual(updated.password_hash, before)
            self.assertTrue(verify_password("ResetByAdmin123", updated.password_hash))
        finally:
            db.close()
        login = self.client.post("/api/v1/auth/login", data={"username": "reportviewer", "password": "ResetByAdmin123"})
        self.assertEqual(login.status_code, 200)


if __name__ == "__main__":
    unittest.main()
