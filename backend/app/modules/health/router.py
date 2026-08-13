"""Health-check API endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK, summary="Check service liveness")
@router.get("/health/live", status_code=status.HTTP_200_OK, summary="Check service liveness")
def liveness_check() -> dict[str, str]:
    """Confirm the application process is running without checking dependencies."""
    return {"status": "ok"}


@router.get("/health/ready", status_code=status.HTTP_200_OK, summary="Check service readiness")
def readiness_check() -> dict[str, str]:
    """Confirm the application can reach its required PostgreSQL database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error
    return {"status": "ok"}
