"""Optimistic stale-preview protection for CSV-approved mutations.

Normal CRUD requests remain unchanged. CSV review requests attach the record ID
and the ``updated_at`` value observed during preview. The final write is rejected
when the database row no longer has that timestamp, while the existing route and
domain service still perform authorization and validation.
"""

from contextvars import ContextVar
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import event, select
from sqlalchemy.orm import Session


_target_id: ContextVar[str | None] = ContextVar("csv_import_target_id", default=None)
_expected_updated_at: ContextVar[str | None] = ContextVar("csv_import_expected_updated_at", default=None)


async def import_baseline_middleware(request: Request, call_next):
    """Make optional import baseline headers available to the flush guard."""

    target_token = _target_id.set(request.headers.get("x-import-target-id"))
    timestamp_token = _expected_updated_at.set(request.headers.get("x-import-expected-updated-at"))
    try:
        return await call_next(request)
    finally:
        _target_id.reset(target_token)
        _expected_updated_at.reset(timestamp_token)


@event.listens_for(Session, "before_flush")
def reject_stale_csv_import_update(session: Session, _flush_context, _instances) -> None:
    """Compare the preview baseline with the current row in the write transaction."""

    target_id = _target_id.get()
    expected_raw = _expected_updated_at.get()
    if not target_id or not expected_raw:
        return
    try:
        expected = _as_utc(datetime.fromisoformat(expected_raw.replace("Z", "+00:00")))
        target_uuid = UUID(target_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Invalid CSV import baseline headers")

    target = next((item for item in session.dirty if getattr(item, "id", None) == target_uuid and hasattr(type(item), "updated_at")), None)
    if target is None:
        return
    table = type(target).__table__
    current = session.connection().execute(select(table.c.updated_at).where(table.c.id == target_uuid)).scalar_one_or_none()
    if current is None or _as_utc(current) != expected:
        raise HTTPException(status_code=409, detail="Record changed since import preview; reload and review current database values")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

