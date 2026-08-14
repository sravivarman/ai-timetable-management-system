"""Regression coverage for browser access from the Next.js development server."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi.testclient import TestClient

from app.main import app
from tests.facilities_test_support import create_facilities_test_context


class CorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_facilities_test_context()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.context.close()

    def test_nextjs_origin_can_preflight_and_login(self) -> None:
        origin = "http://localhost:3000"
        preflight = self.client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(preflight.status_code, 200, preflight.text)
        self.assertEqual(preflight.headers.get("access-control-allow-origin"), origin)
        self.assertIn("POST", preflight.headers.get("access-control-allow-methods", ""))
        self.assertEqual(preflight.headers.get("access-control-allow-credentials"), "true")

        login = self.client.post(
            "/api/v1/auth/login",
            data={"username": "test-administrator", "password": "TestPassword123"},
            headers={"Origin": origin},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.headers.get("access-control-allow-origin"), origin)
        self.assertIn("access_token", login.json())


if __name__ == "__main__":
    unittest.main()
