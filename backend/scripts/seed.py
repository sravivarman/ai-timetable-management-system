"""Idempotently seed required application reference data."""

from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import app.db.models  # noqa: F401  # register every FK target before seeding/tests

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.authentication.models import Permission, Role, User
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.academic_terms.models import AcademicTerm
from app.modules.schedule_configuration.models import PeriodTiming, WorkingDay
from app.modules.courses.models import Course
from app.modules.course_offerings.models import CourseOffering
from app.modules.faculty_allocations.models import TheoryFacultyAllocation

ROLE_DEFINITIONS = {
    "Administrator": "Full system administration",
    "Principal": "Institution principal",
    "Dean": "Academic dean",
    "HOD": "Head of department",
    "Timetable Coordinator": "Timetable operations coordinator",
    "Faculty": "Faculty member",
    "Student": "Student",
}

ADMIN_EMAIL = "admin@vce.ac.in"
ADMIN_PASSWORD = "Admin@123"
ADMIN_FULL_NAME = "System Administrator"

PERMISSION_DEFINITIONS = {
    ("departments", "view"): "View departments",
    ("departments", "manage"): "Create, update, delete, and restore departments",
    ("programs", "read"): "View programs",
    ("programs", "manage"): "Create, update, delete, and restore programs",
    ("academic_terms", "read"): "View academic terms",
    ("academic_terms", "manage"): "Create, update, delete, and restore academic terms",
    ("sections", "read"): "View sections",
    ("sections", "manage"): "Create, update, delete, and restore sections",
    ("faculty", "read"): "View faculty",
    ("faculty", "manage"): "Manage faculty",
    ("faculty_availability", "read"): "View faculty availability and policies",
    ("faculty_availability", "manage"): "Manage faculty availability and policies",
    ("working_days", "read"): "View working days",
    ("working_days", "manage"): "Manage working days",
    ("period_timings", "read"): "View period timings",
    ("period_timings", "manage"): "Manage period timings",
    ("classrooms", "read"): "View classrooms",
    ("classrooms", "manage"): "Manage classrooms",
    ("laboratories", "read"): "View laboratories",
    ("laboratories", "manage"): "Manage laboratories",
    ("courses", "read"): "View courses",
    ("courses", "manage"): "Manage courses",
    ("course_offerings", "read"): "View course offerings",
    ("course_offerings", "manage"): "Manage course offerings",
    ("faculty_allocations", "read"): "View faculty allocations",
    ("faculty_allocations", "manage"): "Manage faculty allocations",
    ("student_batches", "read"): "View student batches", ("student_batches", "manage"): "Manage student batches",
    ("laboratory_batch_configurations", "read"): "View laboratory batch configurations", ("laboratory_batch_configurations", "manage"): "Manage laboratory batch configurations",
    ("laboratory_rotations", "read"): "View laboratory rotations", ("laboratory_rotations", "manage"): "Manage laboratory rotations",
    ("section_classrooms", "read"): "View section classrooms", ("section_classrooms", "manage"): "Manage section classrooms",
    ("laboratory_blocks", "read"): "View laboratory blocks", ("laboratory_blocks", "manage"): "Manage laboratory blocks",
    ("timetable_validation", "read"): "View timetable validation runs", ("timetable_validation", "run"): "Run timetable validation",
    ("timetables", "read"): "View timetables", ("timetables", "manage"): "Manage timetables",
    ("solver_inputs", "read"): "View solver inputs", ("solver_inputs", "build"): "Build solver inputs",
    ("timetable_entries", "read"): "View timetable entries", ("timetable_entries", "manage"): "Manage timetable entries",
    ("timetable_solver", "read"): "View timetable solver runs", ("timetable_solver", "run"): "Run the timetable solver",
    ("timetable_views", "read"): "View rendered timetables and availability reports",
    ("timetable_entries", "move"): "Move timetable entries manually",
    ("timetable_entries", "lock"): "Lock and unlock timetable entries",
    ("timetable_versions", "copy"): "Copy timetable versions",
    ("timetable_workflow", "review"): "Submit and return timetables for review",
    ("timetable_workflow", "approve"): "Approve timetables",
    ("timetable_workflow", "publish"): "Publish timetables",
    ("timetable_workflow", "archive"): "Archive timetables",
    ("timetable_audit", "read"): "View timetable audit and workflow history",
    ("combined_teaching_groups", "read"): "View combined teaching groups",
    ("combined_teaching_groups", "manage"): "Manage combined teaching groups",
    ("reports", "read"): "Preview and export administrative reports",
}

DEPARTMENT_DEFINITIONS = {
    "CIV": ("Civil Engineering", "CIV"),
    "EEE": ("Electrical and Electronics Engineering", "EEE"),
    "MEC": ("Mechanical Engineering", "MEC"),
    "ECE": ("Electronics and Communication Engineering", "ECE"),
    "CSE": ("Computer Science and Engineering", "CSE"),
    "INF": ("Information Technology", "INF"),
    "CSM": ("Computer Science and Engineering (AI and ML)", "CSM"),
    "CSD": ("Computer Science and Engineering (Data Science)", "CSD"),
}

PROGRAM_DEFINITIONS = {
    "CIV": ("BTECH-CIV", "Bachelor of Technology in Civil Engineering"),
    "EEE": ("BTECH-EEE", "Bachelor of Technology in Electrical and Electronics Engineering"),
    "MEC": ("BTECH-MEC", "Bachelor of Technology in Mechanical Engineering"),
    "ECE": ("BTECH-ECE", "Bachelor of Technology in Electronics and Communication Engineering"),
    "CSE": ("BTECH-CSE", "Bachelor of Technology in Computer Science and Engineering"),
    "INF": ("BTECH-INF", "Bachelor of Technology in Information Technology"),
    "CSM": ("BTECH-CSM", "Bachelor of Technology in Computer Science and Engineering (AI and ML)"),
    "CSD": ("BTECH-CSD", "Bachelor of Technology in Computer Science and Engineering (Data Science)"),
}

ACADEMIC_TERM_DEFINITIONS = (
    {"academic_year": "2026-27", "term_name": "I-I", "year_number": 1, "semester_number": 1, "start_date": date(2026, 7, 1), "end_date": date(2026, 11, 30), "is_active": True, "is_current": False, "is_first_year_term": True},
    {"academic_year": "2026-27", "term_name": "II-I", "year_number": 2, "semester_number": 1, "start_date": date(2026, 6, 15), "end_date": date(2026, 11, 30), "is_active": True, "is_current": False, "is_first_year_term": False},
    {"academic_year": "2026-27", "term_name": "III-I", "year_number": 3, "semester_number": 1, "start_date": date(2026, 6, 15), "end_date": date(2026, 11, 30), "is_active": True, "is_current": False, "is_first_year_term": False},
    {"academic_year": "2026-27", "term_name": "IV-I", "year_number": 4, "semester_number": 1, "start_date": date(2026, 6, 15), "end_date": date(2026, 11, 15), "is_active": True, "is_current": False, "is_first_year_term": False},
)


def seed() -> None:
    """Create missing roles, permissions, administrator, and departments."""
    with SessionLocal() as session:
        existing_roles = {
            role.name: role
            for role in session.scalars(select(Role).where(Role.name.in_(ROLE_DEFINITIONS)))
        }
        for name, description in ROLE_DEFINITIONS.items():
            if name not in existing_roles:
                role = Role(name=name, description=description)
                session.add(role)
                existing_roles[name] = role

        session.flush()

        existing_permissions = {
            (permission.resource, permission.action): permission
            for permission in session.scalars(
                    select(Permission).where(Permission.resource.in_(tuple({resource for resource,_ in PERMISSION_DEFINITIONS})))
            )
        }
        for (resource, action), description in PERMISSION_DEFINITIONS.items():
            if (resource, action) not in existing_permissions:
                permission = Permission(resource=resource, action=action, description=description)
                session.add(permission)
                existing_permissions[(resource, action)] = permission

        session.flush()

        administrator_role = existing_roles["Administrator"]
        timetable_coordinator_role = existing_roles["Timetable Coordinator"]
        departments_view = existing_permissions[("departments", "view")]
        departments_manage = existing_permissions[("departments", "manage")]
        programs_read = existing_permissions[("programs", "read")]
        programs_manage = existing_permissions[("programs", "manage")]
        terms_read = existing_permissions[("academic_terms", "read")]
        terms_manage = existing_permissions[("academic_terms", "manage")]
        sections_read = existing_permissions[("sections", "read")]
        sections_manage = existing_permissions[("sections", "manage")]
        faculty_read = existing_permissions[("faculty", "read")]
        faculty_manage = existing_permissions[("faculty", "manage")]
        availability_read = existing_permissions[("faculty_availability", "read")]
        availability_manage = existing_permissions[("faculty_availability", "manage")]
        wd_read, wd_manage = existing_permissions[("working_days", "read")], existing_permissions[("working_days", "manage")]
        pt_read, pt_manage = existing_permissions[("period_timings", "read")], existing_permissions[("period_timings", "manage")]
        classroom_read, classroom_manage = existing_permissions[("classrooms", "read")], existing_permissions[("classrooms", "manage")]
        laboratory_read, laboratory_manage = existing_permissions[("laboratories", "read")], existing_permissions[("laboratories", "manage")]
        courses_read, courses_manage = existing_permissions[("courses", "read")], existing_permissions[("courses", "manage")]
        offerings_read, offerings_manage = existing_permissions[("course_offerings", "read")], existing_permissions[("course_offerings", "manage")]
        allocations_read, allocations_manage = existing_permissions[("faculty_allocations", "read")], existing_permissions[("faculty_allocations", "manage")]
        batch_permissions = [existing_permissions[key] for key in (("student_batches","read"),("student_batches","manage"),("laboratory_batch_configurations","read"),("laboratory_batch_configurations","manage"),("laboratory_rotations","read"),("laboratory_rotations","manage"))]
        section_classroom_read, section_classroom_manage = existing_permissions[("section_classrooms","read")], existing_permissions[("section_classrooms","manage")]
        laboratory_blocks_read, laboratory_blocks_manage = existing_permissions[("laboratory_blocks","read")], existing_permissions[("laboratory_blocks","manage")]
        validation_read, validation_run = existing_permissions[("timetable_validation","read")], existing_permissions[("timetable_validation","run")]
        timetable_read,timetable_manage=existing_permissions[("timetables","read")],existing_permissions[("timetables","manage")]
        solver_read,solver_build=existing_permissions[("solver_inputs","read")],existing_permissions[("solver_inputs","build")]
        entry_read,entry_manage=existing_permissions[("timetable_entries","read")],existing_permissions[("timetable_entries","manage")]
        timetable_solver_read,timetable_solver_run=existing_permissions[("timetable_solver","read")],existing_permissions[("timetable_solver","run")]
        phase3={key:existing_permissions[key] for key in (("timetable_views","read"),("timetable_entries","move"),("timetable_entries","lock"),("timetable_versions","copy"),("timetable_workflow","review"),("timetable_workflow","approve"),("timetable_workflow","publish"),("timetable_workflow","archive"),("timetable_audit","read"))}
        combined_permissions = [existing_permissions[("combined_teaching_groups", action)] for action in ("read", "manage")]
        reports_read = existing_permissions[("reports", "read")]
        hod_role = existing_roles["HOD"]
        if departments_view not in administrator_role.permissions:
            administrator_role.permissions.append(departments_view)
        if departments_manage not in administrator_role.permissions:
            administrator_role.permissions.append(departments_manage)
        if departments_view not in timetable_coordinator_role.permissions:
            timetable_coordinator_role.permissions.append(departments_view)
        if programs_read not in administrator_role.permissions:
            administrator_role.permissions.append(programs_read)
        if programs_manage not in administrator_role.permissions:
            administrator_role.permissions.append(programs_manage)
        if programs_read not in timetable_coordinator_role.permissions:
            timetable_coordinator_role.permissions.append(programs_read)
        if terms_read not in administrator_role.permissions:
            administrator_role.permissions.append(terms_read)
        if terms_manage not in administrator_role.permissions:
            administrator_role.permissions.append(terms_manage)
        if terms_read not in timetable_coordinator_role.permissions:
            timetable_coordinator_role.permissions.append(terms_read)
        if sections_read not in administrator_role.permissions:
            administrator_role.permissions.append(sections_read)
        if sections_manage not in administrator_role.permissions:
            administrator_role.permissions.append(sections_manage)
        if sections_read not in timetable_coordinator_role.permissions:
            timetable_coordinator_role.permissions.append(sections_read)
        if faculty_read not in administrator_role.permissions: administrator_role.permissions.append(faculty_read)
        if faculty_manage not in administrator_role.permissions: administrator_role.permissions.append(faculty_manage)
        if faculty_read not in timetable_coordinator_role.permissions: timetable_coordinator_role.permissions.append(faculty_read)
        if faculty_read not in hod_role.permissions: hod_role.permissions.append(faculty_read)
        if availability_read not in administrator_role.permissions: administrator_role.permissions.append(availability_read)
        if availability_manage not in administrator_role.permissions: administrator_role.permissions.append(availability_manage)
        if availability_read not in timetable_coordinator_role.permissions: timetable_coordinator_role.permissions.append(availability_read)
        if availability_manage not in timetable_coordinator_role.permissions: timetable_coordinator_role.permissions.append(availability_manage)
        if availability_read not in hod_role.permissions: hod_role.permissions.append(availability_read)
        for permission in (wd_read, wd_manage, pt_read, pt_manage):
            if permission not in administrator_role.permissions: administrator_role.permissions.append(permission)
        for role in (timetable_coordinator_role, hod_role):
            for permission in (wd_read, pt_read):
                if permission not in role.permissions: role.permissions.append(permission)
        for permission in (classroom_read, classroom_manage, laboratory_read, laboratory_manage):
            if permission not in administrator_role.permissions: administrator_role.permissions.append(permission)
            if permission not in timetable_coordinator_role.permissions: timetable_coordinator_role.permissions.append(permission)
        for permission in (classroom_read, laboratory_read):
            if permission not in hod_role.permissions: hod_role.permissions.append(permission)
        for role in (administrator_role, timetable_coordinator_role, hod_role):
            for permission in (courses_read, courses_manage):
                if permission not in role.permissions:
                    role.permissions.append(permission)
            for permission in (offerings_read, offerings_manage):
                if permission not in role.permissions:
                    role.permissions.append(permission)
        for role in (administrator_role, hod_role):
            for permission in (allocations_read, allocations_manage):
                if permission not in role.permissions:
                    role.permissions.append(permission)
        if allocations_read not in timetable_coordinator_role.permissions:
            timetable_coordinator_role.permissions.append(allocations_read)
        for role in (administrator_role, hod_role, timetable_coordinator_role):
            for permission in batch_permissions:
                if permission not in role.permissions: role.permissions.append(permission)
        for role in (administrator_role, timetable_coordinator_role):
            for permission in (section_classroom_read, section_classroom_manage, laboratory_blocks_read, laboratory_blocks_manage):
                if permission not in role.permissions: role.permissions.append(permission)
        for permission in (section_classroom_read, laboratory_blocks_read, laboratory_blocks_manage):
            if permission not in hod_role.permissions: hod_role.permissions.append(permission)
        for role in (administrator_role, timetable_coordinator_role, hod_role):
            for permission in (validation_read, validation_run):
                if permission not in role.permissions: role.permissions.append(permission)
        for role in (existing_roles["Dean"], existing_roles["Principal"]):
            if validation_read not in role.permissions: role.permissions.append(validation_read)
        for role in (administrator_role,timetable_coordinator_role):
            for permission in (timetable_read,timetable_manage,solver_read,solver_build):
                if permission not in role.permissions: role.permissions.append(permission)
        for role in (hod_role,existing_roles["Dean"],existing_roles["Principal"]):
            if timetable_read not in role.permissions: role.permissions.append(timetable_read)
        if solver_read not in hod_role.permissions: hod_role.permissions.append(solver_read)
        for role in (administrator_role,timetable_coordinator_role):
            for permission in (entry_read,entry_manage):
                if permission not in role.permissions: role.permissions.append(permission)
        for role in (hod_role,existing_roles["Dean"],existing_roles["Principal"]):
            if entry_read not in role.permissions: role.permissions.append(entry_read)
        for role in (administrator_role,timetable_coordinator_role):
            for permission in (timetable_solver_read,timetable_solver_run):
                if permission not in role.permissions: role.permissions.append(permission)
        for role in (hod_role,existing_roles["Dean"],existing_roles["Principal"]):
            if timetable_solver_read not in role.permissions: role.permissions.append(timetable_solver_read)
        for permission in phase3.values():
            if permission not in administrator_role.permissions: administrator_role.permissions.append(permission)
        for key in (("timetable_views","read"),("timetable_entries","move"),("timetable_entries","lock"),("timetable_versions","copy"),("timetable_workflow","review"),("timetable_audit","read")):
            if phase3[key] not in timetable_coordinator_role.permissions: timetable_coordinator_role.permissions.append(phase3[key])
        for key in (("timetable_views","read"),("timetable_entries","move"),("timetable_entries","lock"),("timetable_audit","read")):
            if phase3[key] not in hod_role.permissions: hod_role.permissions.append(phase3[key])
        for role in (existing_roles["Dean"],existing_roles["Principal"]):
            for key in (("timetable_views","read"),("timetable_workflow","approve"),("timetable_audit","read")):
                if phase3[key] not in role.permissions: role.permissions.append(phase3[key])
        for key in (("timetable_workflow","publish"),("timetable_views","read"),("timetable_audit","read")):
            if phase3[key] not in existing_roles["Principal"].permissions: existing_roles["Principal"].permissions.append(phase3[key])
        for role in (existing_roles["Faculty"],existing_roles["Student"]):
            if phase3[("timetable_views","read")] not in role.permissions: role.permissions.append(phase3[("timetable_views","read")])
        for role in (administrator_role, timetable_coordinator_role, hod_role):
            for permission in combined_permissions:
                if permission not in role.permissions: role.permissions.append(permission)
        for role in (administrator_role, timetable_coordinator_role, hod_role, existing_roles["Dean"], existing_roles["Principal"]):
            if reports_read not in role.permissions:
                role.permissions.append(reports_read)

        administrator = session.scalar(
            select(User)
            .where(User.email == ADMIN_EMAIL)
            .options(selectinload(User.roles))
        )
        if administrator is None:
            administrator = User(
                email=ADMIN_EMAIL,
                full_name=ADMIN_FULL_NAME,
                password_hash=hash_password(ADMIN_PASSWORD),
            )
            session.add(administrator)

        if administrator_role not in administrator.roles:
            administrator.roles.append(administrator_role)

        existing_departments = {
            department.department_code: department
            for department in session.scalars(
                select(Department).where(Department.department_code.in_(DEPARTMENT_DEFINITIONS))
            )
        }
        for department_code, (department_name, short_name) in DEPARTMENT_DEFINITIONS.items():
            if department_code not in existing_departments:
                session.add(
                    Department(
                        department_code=department_code,
                        department_name=department_name,
                        short_name=short_name,
                    )
                )

        session.flush()

        active_departments = {
            department.department_code: department
            for department in session.scalars(
                select(Department).where(
                    Department.department_code.in_(PROGRAM_DEFINITIONS),
                    Department.is_active.is_(True),
                )
            )
        }
        existing_program_codes = set(
            session.scalars(
                select(Program.program_code).where(
                    Program.program_code.in_([definition[0] for definition in PROGRAM_DEFINITIONS.values()])
                )
            )
        )
        for department_code, (program_code, program_name) in PROGRAM_DEFINITIONS.items():
            department = active_departments.get(department_code)
            if department is not None and program_code not in existing_program_codes:
                session.add(
                    Program(
                        department_id=department.id,
                        program_code=program_code,
                        program_name=program_name,
                        degree_type="UG",
                        duration_years=4,
                    )
                )

        existing_terms = {
            (term.academic_year, term.term_name)
            for term in session.scalars(
                select(AcademicTerm).where(AcademicTerm.academic_year == "2026-27")
            )
        }
        for definition in ACADEMIC_TERM_DEFINITIONS:
            if (definition["academic_year"], definition["term_name"]) not in existing_terms:
                session.add(AcademicTerm(**definition))

        for sequence, name in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"), 1):
            if session.scalar(select(WorkingDay).where(WorkingDay.day_name == name)) is None:
                session.add(WorkingDay(day_name=name, sequence_number=sequence))

        patterns = {
            "FIRST_YEAR": [(1,"09:10","10:10",True,None),(2,"10:10","11:00",True,None),(3,"11:00","11:50",True,None),(None,"11:50","12:40",False,"LUNCH"),(4,"12:40","13:30",True,None),(5,"13:30","14:20",True,None),(None,"14:20","14:30",False,"SHORT_BREAK"),(6,"14:30","15:20",True,None),(7,"15:20","16:10",True,None)],
            "HIGHER_YEAR": [(1,"09:10","10:10",True,None),(2,"10:10","11:00",True,None),(None,"11:00","11:10",False,"SHORT_BREAK"),(3,"11:10","12:00",True,None),(4,"12:00","12:50",True,None),(None,"12:50","13:40",False,"LUNCH"),(5,"13:40","14:30",True,None),(6,"14:30","15:20",True,None),(7,"15:20","16:10",True,None)],
        }
        from datetime import time
        for schedule_type, entries in patterns.items():
            for sequence, (period, start, end, instructional, break_type) in enumerate(entries, 1):
                existing = session.scalar(select(PeriodTiming).where(PeriodTiming.schedule_type == schedule_type, PeriodTiming.sequence_number == sequence))
                if existing is None:
                    sh, sm = map(int, start.split(":")); eh, em = map(int, end.split(":"))
                    session.add(PeriodTiming(schedule_type=schedule_type, period_number=period, start_time=time(sh, sm), end_time=time(eh, em), duration_minutes=(eh*60+em)-(sh*60+sm), is_instructional=instructional, break_type=break_type, sequence_number=sequence))

        session.commit()


def main() -> None:
    """Run the seed operation from the command line."""
    seed()
    print("Seed completed successfully.")


if __name__ == "__main__":
    main()
