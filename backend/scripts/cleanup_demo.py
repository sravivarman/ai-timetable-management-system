"""Remove only records created by scripts.seed_demo; never removes CSE or shared terms."""

from sqlalchemy import delete, select

import app.db.models  # noqa: F401  # Register all ORM tables before using SessionLocal.
from app.db.session import SessionLocal
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course
from app.modules.facilities.models import Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, LaboratorySessionFacultyRule, TheoryFacultyAllocation
from app.modules.programs.models import Program
from app.modules.sections.models import Section


def cleanup_demo() -> None:
    """Delete the exact demo graph, preserving shared CSE department and academic term records."""
    with SessionLocal() as session:
        courses = list(session.scalars(select(Course).where(Course.course_code.in_(("DEMO-THEORY-01", "DEMO-LAB-01")))))
        course_ids = [course.id for course in courses]
        offerings = list(session.scalars(select(CourseOffering).where(CourseOffering.course_id.in_(course_ids)))) if course_ids else []
        offering_ids = [offering.id for offering in offerings]
        lab_allocations = list(session.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id.in_(offering_ids)))) if offering_ids else []
        lab_allocation_ids = [allocation.id for allocation in lab_allocations]
        if lab_allocation_ids:
            session.execute(delete(LaboratorySessionFacultyRule).where(LaboratorySessionFacultyRule.laboratory_faculty_allocation_id.in_(lab_allocation_ids)))
        if offering_ids:
            session.execute(delete(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id.in_(offering_ids)))
            session.execute(delete(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id.in_(offering_ids)))
            session.execute(delete(CourseOffering).where(CourseOffering.id.in_(offering_ids)))
        if course_ids:
            session.execute(delete(Course).where(Course.id.in_(course_ids)))
        session.execute(delete(Faculty).where(Faculty.faculty_code.in_(("VCE003", "VCE004"))))
        session.execute(delete(Section).where(Section.section_code == "CSE-A", Section.program_id.in_(select(Program.id).where(Program.program_code == "CSE-UG"))))
        session.execute(delete(Program).where(Program.program_code == "CSE-UG"))
        session.execute(delete(Laboratory).where(Laboratory.laboratory_code == "CSE-PROG-01"))
        session.commit()
    print("Development demo data removed. Shared CSE department and academic term were preserved.")


if __name__ == "__main__":
    cleanup_demo()
