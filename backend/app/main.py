"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.common.import_safety import import_baseline_middleware
from app.modules.authentication.router import router as authentication_router
from app.modules.academic_terms.router import router as academic_terms_router
from app.modules.departments.router import router as departments_router
from app.modules.health.router import router as health_router
from app.modules.programs.router import router as programs_router
from app.modules.sections.router import router as sections_router
from app.modules.faculty.router import router as faculty_router
from app.modules.faculty_scheduling.router import router as faculty_scheduling_router
from app.modules.schedule_configuration.router import router as schedule_configuration_router
from app.modules.facilities.router import router as facilities_router
from app.modules.courses.router import router as courses_router
from app.modules.course_offerings.router import router as course_offerings_router
from app.modules.combined_teaching.router import router as combined_teaching_router
from app.modules.faculty_allocations.router import router as faculty_allocations_router
from app.modules.laboratory_batches.router import router as laboratory_batches_router
from app.modules.facilities_constraints.router import router as facilities_constraints_router
from app.modules.resource_availability.router import router as resource_availability_router
from app.modules.timetable_validation.router import router as timetable_validation_router
from app.modules.timetables.router import router as timetables_router, version_router
from app.modules.timetables.entry_router import entry_router, version_entry_router
from app.modules.timetables.solver_router import solver_run_router, version_solver_router
from app.modules.timetables.review_router import review_entry_router,review_version_router,workflow_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Configure application resources at startup and release them at shutdown."""
    configure_logging()
    yield


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.middleware("http")(import_baseline_middleware)

    @application.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """Return basic service information."""
        return {
            "application": "AI Timetable Management System",
            "version": "0.1.0",
            "status": "running",
        }

    application.include_router(health_router, prefix=settings.api_v1_prefix)
    application.include_router(authentication_router, prefix=settings.api_v1_prefix)
    application.include_router(academic_terms_router, prefix=settings.api_v1_prefix)
    application.include_router(departments_router, prefix=settings.api_v1_prefix)
    application.include_router(programs_router, prefix=settings.api_v1_prefix)
    application.include_router(sections_router, prefix=settings.api_v1_prefix)
    application.include_router(faculty_router, prefix=settings.api_v1_prefix)
    application.include_router(faculty_scheduling_router, prefix=settings.api_v1_prefix)
    application.include_router(schedule_configuration_router, prefix=settings.api_v1_prefix)
    application.include_router(facilities_router, prefix=settings.api_v1_prefix)
    application.include_router(courses_router, prefix=settings.api_v1_prefix)
    application.include_router(course_offerings_router, prefix=settings.api_v1_prefix)
    application.include_router(combined_teaching_router, prefix=settings.api_v1_prefix)
    application.include_router(faculty_allocations_router, prefix=settings.api_v1_prefix)
    application.include_router(laboratory_batches_router, prefix=settings.api_v1_prefix)
    application.include_router(facilities_constraints_router, prefix=settings.api_v1_prefix)
    application.include_router(resource_availability_router, prefix=settings.api_v1_prefix)
    application.include_router(timetable_validation_router, prefix=settings.api_v1_prefix)
    application.include_router(timetables_router, prefix=settings.api_v1_prefix)
    application.include_router(version_router, prefix=settings.api_v1_prefix)
    application.include_router(version_entry_router, prefix=settings.api_v1_prefix)
    application.include_router(entry_router, prefix=settings.api_v1_prefix)
    application.include_router(version_solver_router, prefix=settings.api_v1_prefix)
    application.include_router(solver_run_router, prefix=settings.api_v1_prefix)
    application.include_router(review_version_router, prefix=settings.api_v1_prefix)
    application.include_router(review_entry_router, prefix=settings.api_v1_prefix)
    application.include_router(workflow_router, prefix=settings.api_v1_prefix)
    return application


app = create_application()
