import os
import unittest
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/timetable_db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-at-least-thirty-two-bytes")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.db.models  # noqa: F401 - register every ForeignKey target
from app.db.base import Base
from app.modules.authentication.models import Role
from app.modules.authentication.schemas import UserCreate, UserUpdate
from app.modules.authentication.services import authentication_service


class UserAccessModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.roles = {name: Role(name=name) for name in ["Administrator", "Principal", "Dean", "Timetable Coordinator", "Faculty", "Student"]}
        self.db.add_all(self.roles.values())
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create(self, role_name: str, email: str):
        return authentication_service.create_user(self.db, UserCreate(email=email, full_name="Approved User", password="StrongPassword123", role_ids=[self.roles[role_name].id]))

    def test_each_approved_login_role_is_accepted(self):
        for index, role_name in enumerate(["Administrator", "Principal", "Dean", "Timetable Coordinator"]):
            user = self.create(role_name, f"approved{index}@vce.ac.in")
            self.assertEqual([role.name for role in user.roles], [role_name])

    def test_faculty_student_and_unknown_roles_are_rejected(self):
        for role_name in ["Faculty", "Student"]:
            with self.assertRaises(HTTPException) as raised:
                self.create(role_name, f"{role_name.lower()}@vce.ac.in")
            self.assertEqual(raised.exception.status_code, 422)
        with self.assertRaises(HTTPException):
            authentication_service.create_user(self.db, UserCreate(email="unknown@vce.ac.in", full_name="Unknown", password="StrongPassword123", role_ids=[uuid4()]))

    def test_existing_user_cannot_be_reassigned_to_an_unapproved_role(self):
        user = self.create("Administrator", "admin2@vce.ac.in")
        with self.assertRaises(HTTPException) as raised:
            authentication_service.update_user(self.db, user, UserUpdate(role_ids=[self.roles["Faculty"].id]))
        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
