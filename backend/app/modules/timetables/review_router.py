from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import get_current_user,require_permission
from app.modules.authentication.models import User
from app.modules.timetables.entry_repository import entry_repository
from app.modules.timetables.entry_schemas import TimetableEntryResponse
from app.modules.timetables.models import TimetableEntry
from app.modules.timetables.review_schemas import ConflictReportResponse,FreeResourceResponse,LockRequest,RequiredReasonRequest,TimetableEntryAuditResponse,TimetableEntryMove,TimetableGridResponse,TimetableStatusHistoryResponse,TransitionRequest,UnlockRequest,VersionComparisonResponse,VersionCopyRequest
from app.modules.timetables.review_service import review_service
from app.modules.timetables.schemas import TimetableResponse,TimetableVersionResponse

review_version_router=APIRouter(prefix="/timetable-versions",tags=["timetable-review"]);review_entry_router=APIRouter(prefix="/timetable-entries",tags=["timetable-review"]);workflow_router=APIRouter(prefix="/timetables",tags=["timetable-workflow"])
view_permission=Depends(require_permission("timetable_views","read"));move_permission=Depends(require_permission("timetable_entries","move"));lock_permission=Depends(require_permission("timetable_entries","lock"));copy_permission=Depends(require_permission("timetable_versions","copy"));audit_permission=Depends(require_permission("timetable_audit","read"))

def grid(view_type):
 def endpoint(version_id:UUID,resource_id:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.grid(db,version_id,view_type,resource_id,user)
 return endpoint
for path,kind in (("section","section"),("faculty","faculty"),("classroom","classroom"),("laboratory","laboratory"),("batch","batch")):
 review_version_router.add_api_route(f"/{{version_id}}/views/{path}/{{resource_id}}",grid(kind),methods=["GET"],response_model=TimetableGridResponse,dependencies=[view_permission],name=f"{kind}_timetable_view")

@review_entry_router.post("/{entry_id}/move",response_model=TimetableEntryResponse,dependencies=[move_permission])
def move(entry_id:UUID,payload:TimetableEntryMove,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 entry=entry_repository.get(db,entry_id)
 if not entry:raise HTTPException(404,"Timetable entry not found")
 return review_service.move(db,entry,payload,user)
@review_entry_router.post("/{entry_id}/lock",response_model=TimetableEntryResponse,dependencies=[lock_permission])
def lock(entry_id:UUID,payload:LockRequest=LockRequest(),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 entry=entry_repository.get(db,entry_id)
 if not entry:raise HTTPException(404,"Timetable entry not found")
 return review_service.lock(db,entry,user,payload.reason)
@review_entry_router.post("/{entry_id}/unlock",response_model=TimetableEntryResponse,dependencies=[lock_permission])
def unlock(entry_id:UUID,payload:UnlockRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
 entry=entry_repository.get(db,entry_id)
 if not entry:raise HTTPException(404,"Timetable entry not found")
 return review_service.unlock(db,entry,user,payload.reason)
@review_entry_router.get("/{entry_id}/audit",response_model=list[TimetableEntryAuditResponse],dependencies=[audit_permission])
def audit(entry_id:UUID,db:Session=Depends(get_db)):
 records=review_service.audits(db,entry_id)
 if not entry_repository.get(db,entry_id) and not records:raise HTTPException(404,"Timetable entry not found")
 return records

@review_version_router.post("/{version_id}/copy",response_model=TimetableVersionResponse,status_code=201,dependencies=[copy_permission])
def copy_version(version_id:UUID,payload:VersionCopyRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.copy_version(db,version_id,payload,user)
@review_version_router.get("/{version_id}/compare/{other_version_id}",response_model=VersionComparisonResponse,dependencies=[view_permission])
def compare(version_id:UUID,other_version_id:UUID,db:Session=Depends(get_db)):return review_service.compare(db,version_id,other_version_id)
@review_version_router.get("/{version_id}/free-faculty",response_model=FreeResourceResponse,dependencies=[view_permission])
def free_faculty(version_id:UUID,working_day_id:UUID,period_number:int=Query(ge=1,le=7),db:Session=Depends(get_db)):return review_service.free_resources(db,version_id,"faculty",working_day_id,period_number)
@review_version_router.get("/{version_id}/free-classrooms",response_model=FreeResourceResponse,dependencies=[view_permission])
def free_classrooms(version_id:UUID,working_day_id:UUID,period_number:int=Query(ge=1,le=7),db:Session=Depends(get_db)):return review_service.free_resources(db,version_id,"classroom",working_day_id,period_number)
@review_version_router.get("/{version_id}/free-laboratories",response_model=FreeResourceResponse,dependencies=[view_permission])
def free_laboratories(version_id:UUID,working_day_id:UUID,period_number:int=Query(ge=1,le=7),section_id:UUID|None=None,student_batch_id:UUID|None=None,db:Session=Depends(get_db)):return review_service.free_resources(db,version_id,"laboratory",working_day_id,period_number,section_id,student_batch_id)
@review_version_router.get("/{version_id}/conflicts",response_model=ConflictReportResponse,dependencies=[view_permission])
def conflicts(version_id:UUID,db:Session=Depends(get_db)):return review_service.conflicts(db,version_id)

@workflow_router.post("/{timetable_id}/submit-review",response_model=TimetableResponse,dependencies=[Depends(require_permission("timetable_workflow","review"))])
def submit_review(timetable_id:UUID,payload:TransitionRequest=TransitionRequest(),db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.transition(db,timetable_id,"UNDER_REVIEW",user,payload.reason)
@workflow_router.post("/{timetable_id}/approve",response_model=TimetableResponse,dependencies=[Depends(require_permission("timetable_workflow","approve"))])
def approve(timetable_id:UUID,payload:TransitionRequest=TransitionRequest(),db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.transition(db,timetable_id,"APPROVED",user,payload.reason)
@workflow_router.post("/{timetable_id}/publish",response_model=TimetableResponse,dependencies=[Depends(require_permission("timetable_workflow","publish"))])
def publish(timetable_id:UUID,payload:TransitionRequest=TransitionRequest(),db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.transition(db,timetable_id,"PUBLISHED",user,payload.reason)
@workflow_router.post("/{timetable_id}/archive",response_model=TimetableResponse,dependencies=[Depends(require_permission("timetable_workflow","archive"))])
def archive(timetable_id:UUID,payload:TransitionRequest=TransitionRequest(),db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.transition(db,timetable_id,"ARCHIVED",user,payload.reason)
@workflow_router.post("/{timetable_id}/return-to-draft",response_model=TimetableResponse,dependencies=[Depends(require_permission("timetable_workflow","review"))])
def return_to_draft(timetable_id:UUID,payload:RequiredReasonRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):return review_service.transition(db,timetable_id,"DRAFT",user,payload.reason)
@workflow_router.get("/{timetable_id}/status-history",response_model=list[TimetableStatusHistoryResponse],dependencies=[audit_permission])
def status_history(timetable_id:UUID,db:Session=Depends(get_db)):return review_service.status_history(db,timetable_id)
