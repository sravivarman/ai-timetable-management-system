"""Regression tests for the reusable Facilities endpoint test infrastructure."""

import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from tests.facilities_test_support import create_facilities_test_context


class FacilitiesInfrastructureTests(unittest.TestCase):
    def test_context_provisions_departments_and_role_tokens(self) -> None:
        context = create_facilities_test_context()
        try:
            self.assertTrue(context.active_department.is_active)
            self.assertFalse(context.inactive_department.is_active)
            self.assertEqual(set(context.headers), {"administrator", "coordinator", "hod", "unauthorized"})
        finally:
            context.close()
