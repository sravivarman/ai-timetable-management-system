"""Isolated database and authentication helpers for Facilities endpoint tests."""

from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.modules.academic_terms.models  # noqa: F401
import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.facilities.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
import app.modules.course_offerings.models  # noqa: F401
import app.modules.faculty_allocations.models  # noqa: F401
import app.modules.facilities_constraints.models  # noqa: F401
import app.modules.faculty.models  # noqa: F401
import app.modules.faculty_scheduling.models  # noqa: F401
import app.modules.programs.models  # noqa: F401
import app.modules.schedule_configuration.models  # noqa: F401
import app.modules.sections.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.authentication.models import Permission, Role, User
from app.modules.departments.models import Department


@dataclass
class FacilitiesTestContext:
    """Resources shared by an isolated Facilities HTTP test case."""

    session_factory: sessionmaker[Session]
    active_department: Department
    inactive_department: Department
    headers: dict[str, dict[str, str]]

    def close(self) -> None:
        app.dependency_overrides.pop(get_db, None)


def create_facilities_test_context() -> FacilitiesTestContext:
    """Create an in-memory schema and override FastAPI's database dependency."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    session = session_factory()
    try:
        facilities_permissions = [
            Permission(resource="classrooms", action="read"),
            Permission(resource="classrooms", action="manage"),
            Permission(resource="laboratories", action="read"),
            Permission(resource="laboratories", action="manage"),
            Permission(resource="courses", action="read"),
            Permission(resource="courses", action="manage"),
            Permission(resource="course_offerings", action="read"),
            Permission(resource="course_offerings", action="manage"),
            Permission(resource="faculty_allocations", action="read"),
            Permission(resource="faculty_allocations", action="manage"),
        ]
        administrator = Role(name="Administrator", permissions=list(facilities_permissions))
        coordinator = Role(name="Timetable Coordinator", permissions=facilities_permissions[:-1])
        hod = Role(name="HOD", permissions=[facilities_permissions[0], facilities_permissions[2], facilities_permissions[4], facilities_permissions[5], facilities_permissions[6], facilities_permissions[7], facilities_permissions[8], facilities_permissions[9]])
        unprivileged = Role(name="Faculty")
        session.add_all([administrator, coordinator, hod, unprivileged])
        active_department = Department(department_code="TST", department_name="Test Department", short_name="TST")
        inactive_department = Department(department_code="INA", department_name="Inactive Department", short_name="INA", is_active=False)
        session.add_all([active_department, inactive_department])
        session.flush()

        users = {
            "administrator": User(email="admin.test@vce.ac.in", full_name="Test Administrator", password_hash=hash_password("TestPassword123"), roles=[administrator]),
            "coordinator": User(email="coordinator.test@vce.ac.in", full_name="Test Coordinator", password_hash=hash_password("TestPassword123"), roles=[coordinator]),
            "hod": User(email="hod.test@vce.ac.in", full_name="Test HOD", password_hash=hash_password("TestPassword123"), roles=[hod]),
            "unauthorized": User(email="faculty.test@vce.ac.in", full_name="Test Faculty", password_hash=hash_password("TestPassword123"), roles=[unprivileged]),
        }
        session.add_all(users.values())
        session.commit()
        headers = {
            name: {"Authorization": f"Bearer {create_access_token(user.id, user.token_version)}"}
            for name, user in users.items()
        }
        return FacilitiesTestContext(session_factory, active_department, inactive_department, headers)
    finally:
        session.close()
