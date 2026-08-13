from uuid import UUID
from fastapi import APIRouter,Depends,Query,Response,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.faculty.schemas import FacultyCreate,FacultyPage,FacultyRead,FacultyUpdate
from app.modules.faculty.services import faculty_service
router=APIRouter(prefix="/faculty",tags=["faculty"]); read=Depends(require_permission("faculty","read")); manage=Depends(require_permission("faculty","manage"))
@router.get("",response_model=FacultyPage,dependencies=[read])
def list_faculty(db:Session=Depends(get_db),search:str|None=Query(default=None,min_length=1),department_id:UUID|None=None,designation:str|None=None,is_active:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)): return faculty_service.list_faculty(db,search=search,department_id=department_id,designation=designation,is_active=is_active,page=page,page_size=page_size)
@router.get("/{faculty_id}",response_model=FacultyRead,dependencies=[read])
def get_faculty(faculty_id:UUID,db:Session=Depends(get_db)): return faculty_service.get(db,faculty_id)
@router.post("",response_model=FacultyRead,status_code=status.HTTP_201_CREATED,dependencies=[manage])
def create_faculty(payload:FacultyCreate,db:Session=Depends(get_db)): return faculty_service.create(db,payload)
@router.put("/{faculty_id}",response_model=FacultyRead,dependencies=[manage])
def update_faculty(faculty_id:UUID,payload:FacultyUpdate,db:Session=Depends(get_db)): return faculty_service.update(db,faculty_id,payload)
@router.delete("/{faculty_id}",status_code=204,dependencies=[manage])
def delete_faculty(faculty_id:UUID,db:Session=Depends(get_db)): faculty_service.delete(db,faculty_id); return Response(status_code=204)
@router.post("/{faculty_id}/restore",response_model=FacultyRead,dependencies=[manage])
def restore_faculty(faculty_id:UUID,db:Session=Depends(get_db)): return faculty_service.restore(db,faculty_id)
