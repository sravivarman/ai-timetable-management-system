"""Administrative report metadata, preview, and export API."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.reports.renderers import MIME_TYPES, render_report, report_filename
from app.modules.reports.schemas import ReportDefinitionResponse, ReportPreviewResponse, ReportRequest
from app.modules.reports.service import report_service


router = APIRouter(
    prefix="/reports",
    tags=["Administrative Reports"],
    dependencies=[Depends(require_permission("reports", "read"))],
)


@router.get("/definitions", response_model=list[ReportDefinitionResponse])
def list_report_definitions() -> list[ReportDefinitionResponse]:
    return report_service.definitions()


@router.post("/preview", response_model=ReportPreviewResponse)
def preview_report(payload: ReportRequest, db: Session = Depends(get_db)) -> ReportPreviewResponse:
    return report_service.preview(db, payload)


@router.post("/export")
def export_report(
    payload: ReportRequest,
    export_format: Literal["xlsx", "csv", "docx", "pdf"] = Query(alias="format"),
    db: Session = Depends(get_db),
) -> Response:
    result = report_service.canonical(db, payload)
    if export_format not in result.definition.supported_formats:
        raise HTTPException(422, "Export format is not supported for this report")
    try:
        content = render_report(result, export_format)
    except Exception as exc:
        raise HTTPException(500, "Export generation failed") from exc
    filename = report_filename(result, export_format)
    return Response(
        content=content,
        media_type=MIME_TYPES[export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
