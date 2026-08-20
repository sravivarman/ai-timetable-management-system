"""Central ORM model registry used by operational commands and Alembic."""

# Import every declarative model module so all ForeignKey targets are present in
# Base.metadata before a session performs mapper configuration or a flush.
import app.modules.authentication.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.programs.models  # noqa: F401
import app.modules.academic_terms.models  # noqa: F401
import app.modules.sections.models  # noqa: F401
import app.modules.faculty.models  # noqa: F401
import app.modules.faculty_scheduling.models  # noqa: F401
import app.modules.schedule_configuration.models  # noqa: F401
import app.modules.facilities.models  # noqa: F401
import app.modules.resource_availability.models  # noqa: F401
import app.modules.courses.models  # noqa: F401
import app.modules.course_offerings.models  # noqa: F401
import app.modules.combined_teaching.models  # noqa: F401
import app.modules.faculty_allocations.models  # noqa: F401
import app.modules.laboratory_batches.models  # noqa: F401
import app.modules.facilities_constraints.models  # noqa: F401
import app.modules.timetable_validation.models  # noqa: F401
import app.modules.scheduling_slots.models  # noqa: F401
import app.modules.timetables.models  # noqa: F401
