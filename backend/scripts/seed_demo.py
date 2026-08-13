"""Create one idempotent development-only faculty-allocation demo scenario."""

from datetime import date

from sqlalchemy import select

import app.db.models  # noqa: F401  # Register all ORM tables before using SessionLocal.
from app.db.session import SessionLocal
from app.modules.academic_terms.models import AcademicTerm
from app.modules.course_offerings.models import CourseOffering
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.departments.models import Department
from app.modules.facilities.models import Laboratory
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import LaboratoryFacultyAllocation, TheoryFacultyAllocation
from app.modules.programs.models import Program
from app.modules.sections.models import Section


def _get_or_create(session, model, where, **values):
    record = session.scalar(select(model).where(*where))
    if record is None:
        record = model(**values)
        session.add(record)
        session.flush()
    return record


def seed_demo() -> dict[str, object]:
    """Create or reuse the exact CSE demo records, without invoking core seed."""
    with SessionLocal() as session:
        department = _get_or_create(session, Department, [Department.department_code == "CSE"], department_code="CSE", department_name="Computer Science and Engineering", short_name="CSE")
        department.is_active = True
        program = _get_or_create(session, Program, [Program.program_code == "CSE-UG"], department_id=department.id, program_code="CSE-UG", program_name="B.Tech Computer Science and Engineering", degree_type="UG", duration_years=4)
        program.department_id, program.is_active = department.id, True
        term = _get_or_create(session, AcademicTerm, [AcademicTerm.academic_year == "2026-27", AcademicTerm.term_name == "I-I"], academic_year="2026-27", term_name="I-I", year_number=1, semester_number=1, start_date=date(2026, 7, 1), end_date=date(2026, 11, 30), is_active=True, is_first_year_term=True)
        term.is_active = True
        section = _get_or_create(session, Section, [Section.program_id == program.id, Section.academic_term_id == term.id, Section.section_name == "A"], program_id=program.id, academic_term_id=term.id, section_name="A", section_code="CSE-A", student_strength=72)
        section.section_code, section.student_strength, section.is_active = "CSE-A", 72, True

        laboratory = session.scalar(select(Laboratory).where(Laboratory.laboratory_code == "CSE-PROG-01"))
        if laboratory is None:
            if session.scalar(select(Laboratory).where(Laboratory.room_number == "3102")):
                raise RuntimeError("Room 3102 is already used by a non-demo laboratory")
            laboratory = Laboratory(laboratory_code="CSE-PROG-01", laboratory_name="Programming Laboratory", room_number="3102", owning_department_id=department.id)
            session.add(laboratory); session.flush()
        laboratory.laboratory_name, laboratory.owning_department_id, laboratory.is_active = "Programming Laboratory", department.id, True

        theory = _get_or_create(session, Course, [Course.course_code == "DEMO-THEORY-01"], course_code="DEMO-THEORY-01", course_name="Demo Theory Course", offering_department_id=department.id, course_type="THEORY", weekly_periods=4, counts_toward_workload=True)
        theory.course_name, theory.offering_department_id, theory.course_type, theory.weekly_periods, theory.counts_toward_workload, theory.is_active = "Demo Theory Course", department.id, "THEORY", 4, True, True
        theory.lab_session_duration = theory.lab_sessions_per_week = theory.default_lab_group_count = theory.default_laboratory_id = None
        lab_course = _get_or_create(session, Course, [Course.course_code == "DEMO-LAB-01"], course_code="DEMO-LAB-01", course_name="Demo Programming Laboratory", offering_department_id=department.id, course_type="LABORATORY", weekly_periods=4, lab_session_duration=2, lab_sessions_per_week=2, default_lab_group_count=2, default_laboratory_id=laboratory.id, counts_toward_workload=True)
        lab_course.course_name, lab_course.offering_department_id, lab_course.course_type, lab_course.weekly_periods, lab_course.lab_session_duration, lab_course.lab_sessions_per_week, lab_course.default_lab_group_count, lab_course.default_laboratory_id, lab_course.counts_toward_workload, lab_course.is_active = "Demo Programming Laboratory", department.id, "LABORATORY", 4, 2, 2, 2, laboratory.id, True, True
        eligibility = session.get(CourseEligibleLaboratory, (lab_course.id, laboratory.id))
        if eligibility is None:
            session.add(CourseEligibleLaboratory(course_id=lab_course.id, laboratory_id=laboratory.id, preference_priority=1, is_active=True))
        else:
            eligibility.preference_priority, eligibility.is_active = 1, True

        theory_offering = _get_or_create(session, CourseOffering, [CourseOffering.course_id == theory.id, CourseOffering.section_id == section.id, CourseOffering.academic_term_id == term.id], course_id=theory.id, section_id=section.id, academic_term_id=term.id)
        lab_offering = _get_or_create(session, CourseOffering, [CourseOffering.course_id == lab_course.id, CourseOffering.section_id == section.id, CourseOffering.academic_term_id == term.id], course_id=lab_course.id, section_id=section.id, academic_term_id=term.id)
        theory_offering.is_active = lab_offering.is_active = True

        faculty_a = _get_or_create(session, Faculty, [Faculty.faculty_code == "VCE003"], faculty_code="VCE003", full_name="Demo Faculty A", department_id=department.id, designation="Assistant Professor", institutional_email="demo.faculty.a@vce.ac.in", maximum_weekly_workload=20)
        faculty_b = _get_or_create(session, Faculty, [Faculty.faculty_code == "VCE004"], faculty_code="VCE004", full_name="Demo Faculty B", department_id=department.id, designation="Assistant Professor", institutional_email="demo.faculty.b@vce.ac.in", maximum_weekly_workload=20)
        for faculty, name in ((faculty_a, "Demo Faculty A"), (faculty_b, "Demo Faculty B")):
            faculty.full_name, faculty.department_id, faculty.is_active = name, department.id, True

        theory_allocation = _get_or_create(session, TheoryFacultyAllocation, [TheoryFacultyAllocation.course_offering_id == theory_offering.id, TheoryFacultyAllocation.faculty_id == faculty_a.id], course_offering_id=theory_offering.id, faculty_id=faculty_a.id)
        theory_allocation.is_active = True
        main_allocation = _get_or_create(session, LaboratoryFacultyAllocation, [LaboratoryFacultyAllocation.course_offering_id == lab_offering.id, LaboratoryFacultyAllocation.faculty_id == faculty_a.id, LaboratoryFacultyAllocation.role_type == "MAIN"], course_offering_id=lab_offering.id, faculty_id=faculty_a.id, role_type="MAIN")
        support_allocation = _get_or_create(session, LaboratoryFacultyAllocation, [LaboratoryFacultyAllocation.course_offering_id == lab_offering.id, LaboratoryFacultyAllocation.faculty_id == faculty_b.id, LaboratoryFacultyAllocation.role_type == "SUPPORTING"], course_offering_id=lab_offering.id, faculty_id=faculty_b.id, role_type="SUPPORTING")
        main_allocation.is_active = support_allocation.is_active = True
        session.commit()
        return {"Department": department, "Program": program, "Academic term": term, "Section": section, "Laboratory": laboratory, "Theory course": theory, "Laboratory course": lab_course, "Theory offering": theory_offering, "Laboratory offering": lab_offering, "Faculty A": faculty_a, "Faculty B": faculty_b, "Theory allocation": theory_allocation, "Laboratory MAIN allocation": main_allocation, "Laboratory SUPPORTING allocation": support_allocation}


def main() -> None:
    records = seed_demo()
    print("Development demo data is ready:")
    for label, record in records.items():
        print(f"- {label}: {record.id}")


if __name__ == "__main__":
    main()
