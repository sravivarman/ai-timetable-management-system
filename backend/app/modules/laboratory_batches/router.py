from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.authentication.dependencies import require_permission
from app.modules.laboratory_batches.models import (
    LaboratoryBatchConfiguration,
    LaboratoryRotationAssignment,
    LaboratoryRotationBlock,
    LaboratoryRotationGroup,
    StudentBatch,
)
from app.modules.laboratory_batches.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    BatchCreate,
    BatchGenerate,
    BatchRead,
    BatchUpdate,
    ConfigCreate,
    ConfigRead,
    ConfigUpdate,
    RotationBlockCreate,
    RotationBlockRead,
    RotationBlockUpdate,
    RotationCreate,
    RotationGenerateRequest,
    RotationMatrixResponse,
    RotationRead,
    RotationUpdate,
)
from app.modules.laboratory_batches.services import service


router = APIRouter(tags=["laboratory-batches"])
batch_read = Depends(require_permission("student_batches", "read"))
batch_manage = Depends(require_permission("student_batches", "manage"))
config_read = Depends(require_permission("laboratory_batch_configurations", "read"))
config_manage = Depends(require_permission("laboratory_batch_configurations", "manage"))
rotation_read = Depends(require_permission("laboratory_rotations", "read"))
rotation_manage = Depends(require_permission("laboratory_rotations", "manage"))


@router.post("/student-batches/generate", response_model=list[BatchRead], dependencies=[batch_manage])
def generate_batches(payload: BatchGenerate, db: Session = Depends(get_db)):
    return service.batches(db, payload.section_id, payload.number_of_groups, payload.overwrite, payload.naming_pattern)


@router.get("/student-batches", dependencies=[batch_read])
def list_batches(db: Session = Depends(get_db), section_id: UUID | None = None, is_active: bool | None = True, page: int = 1, page_size: int = 20):
    return service.list(db, StudentBatch, page, page_size, section_id=section_id, is_active=is_active)


@router.post("/student-batches", response_model=BatchRead, status_code=status.HTTP_201_CREATED, dependencies=[batch_manage])
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    return service.save(db, StudentBatch(**payload.model_dump()))


@router.get("/student-batches/{batch_id}", response_model=BatchRead, dependencies=[batch_read])
def get_batch(batch_id: UUID, db: Session = Depends(get_db)):
    return service.get(db, StudentBatch, batch_id)


@router.put("/student-batches/{batch_id}", response_model=BatchRead, dependencies=[batch_manage])
def update_batch(batch_id: UUID, payload: BatchUpdate, db: Session = Depends(get_db)):
    record = service.get(db, StudentBatch, batch_id)
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    return service.save(db, record)


@router.delete("/student-batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[batch_manage])
def delete_batch(batch_id: UUID, db: Session = Depends(get_db)):
    service.delete(db, StudentBatch, batch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/student-batches/{batch_id}/restore", response_model=BatchRead, dependencies=[batch_manage])
def restore_batch(batch_id: UUID, db: Session = Depends(get_db)):
    return service.restore(db, StudentBatch, batch_id)


@router.get("/laboratory-batch-configurations", dependencies=[config_read])
def list_configurations(db: Session = Depends(get_db), section_id: UUID | None = None, course_offering_id: UUID | None = None, is_active: bool | None = True, page: int = 1, page_size: int = 20):
    return service.list(db, LaboratoryBatchConfiguration, page, page_size, section_id=section_id, course_offering_id=course_offering_id, is_active=is_active)


@router.post("/laboratory-batch-configurations", response_model=ConfigRead, status_code=status.HTTP_201_CREATED, dependencies=[config_manage])
def create_configuration(payload: ConfigCreate, db: Session = Depends(get_db)):
    return service.config(db, payload.model_dump())


@router.get("/laboratory-batch-configurations/{configuration_id}", response_model=ConfigRead, dependencies=[config_read])
def get_configuration(configuration_id: UUID, db: Session = Depends(get_db)):
    return service.get(db, LaboratoryBatchConfiguration, configuration_id)


@router.put("/laboratory-batch-configurations/{configuration_id}", response_model=ConfigRead, dependencies=[config_manage])
def update_configuration(configuration_id: UUID, payload: ConfigUpdate, db: Session = Depends(get_db)):
    return service.config(db, payload.model_dump(exclude_unset=True), configuration_id)


@router.delete("/laboratory-batch-configurations/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[config_manage])
def delete_configuration(configuration_id: UUID, db: Session = Depends(get_db)):
    service.delete(db, LaboratoryBatchConfiguration, configuration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/laboratory-batch-configurations/{configuration_id}/restore", response_model=ConfigRead, dependencies=[config_manage])
def restore_configuration(configuration_id: UUID, db: Session = Depends(get_db)):
    return service.restore(db, LaboratoryBatchConfiguration, configuration_id)


# Static routes must precede the UUID route so legacy clients keep working.
@router.post("/laboratory-rotations/generate", response_model=RotationMatrixResponse, status_code=status.HTTP_201_CREATED, dependencies=[rotation_manage])
def generate_rotation(payload: RotationGenerateRequest, db: Session = Depends(get_db)):
    return service.generate_rotation(db, payload)


@router.get("/laboratory-rotations", dependencies=[rotation_read])
def list_rotations(db: Session = Depends(get_db), section_id: UUID | None = None, academic_term_id: UUID | None = None, is_active: bool | None = True, page: int = 1, page_size: int = 20):
    return service.list(db, LaboratoryRotationGroup, page, page_size, section_id=section_id, academic_term_id=academic_term_id, is_active=is_active)


@router.post("/laboratory-rotations", response_model=RotationRead, status_code=status.HTTP_201_CREATED, dependencies=[rotation_manage])
def create_rotation(payload: RotationCreate, db: Session = Depends(get_db)):
    return service.create_rotation(db, payload.model_dump())


@router.get("/laboratory-rotations/{group_id}/matrix", response_model=RotationMatrixResponse, dependencies=[rotation_read])
def get_rotation_matrix(group_id: UUID, db: Session = Depends(get_db)):
    return service.matrix(db, group_id)


@router.post("/laboratory-rotations/{group_id}/blocks", response_model=RotationBlockRead, status_code=status.HTTP_201_CREATED, dependencies=[rotation_manage])
def create_rotation_block(group_id: UUID, payload: RotationBlockCreate, db: Session = Depends(get_db)):
    return service.block(db, group_id, payload.model_dump())


@router.put("/laboratory-rotations/blocks/{block_id}", response_model=RotationBlockRead, dependencies=[rotation_manage])
def update_rotation_block(block_id: UUID, payload: RotationBlockUpdate, db: Session = Depends(get_db)):
    record = service.get(db, LaboratoryRotationBlock, block_id)
    return service.block(db, record.rotation_group_id, payload.model_dump(exclude_unset=True), block_id)


@router.delete("/laboratory-rotations/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[rotation_manage])
def delete_rotation_block(block_id: UUID, db: Session = Depends(get_db)):
    service.delete(db, LaboratoryRotationBlock, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/laboratory-rotations/{group_id}/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED, dependencies=[rotation_manage])
def create_assignment(group_id: UUID, payload: AssignmentCreate, db: Session = Depends(get_db)):
    return service.assignment(db, group_id, payload.model_dump())


@router.put("/laboratory-rotations/assignments/{assignment_id}", response_model=AssignmentRead, dependencies=[rotation_manage])
def update_assignment(assignment_id: UUID, payload: AssignmentUpdate, db: Session = Depends(get_db)):
    record = service.get(db, LaboratoryRotationAssignment, assignment_id)
    return service.assignment(db, record.rotation_group_id, payload.model_dump(exclude_unset=True), assignment_id)


@router.delete("/laboratory-rotations/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[rotation_manage])
def delete_assignment(assignment_id: UUID, db: Session = Depends(get_db)):
    service.delete(db, LaboratoryRotationAssignment, assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/laboratory-rotations/{group_id}", response_model=RotationRead, dependencies=[rotation_read])
def get_rotation(group_id: UUID, db: Session = Depends(get_db)):
    return service.get(db, LaboratoryRotationGroup, group_id)


@router.put("/laboratory-rotations/{group_id}", response_model=RotationRead, dependencies=[rotation_manage])
def update_rotation(group_id: UUID, payload: RotationUpdate, db: Session = Depends(get_db)):
    record = service.get(db, LaboratoryRotationGroup, group_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    return service.save(db, record)


@router.delete("/laboratory-rotations/{group_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[rotation_manage])
def delete_rotation(group_id: UUID, db: Session = Depends(get_db)):
    record = service.get(db, LaboratoryRotationGroup, group_id)
    service._deactivate_rotation(db, record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/laboratory-rotations/{group_id}/restore", response_model=RotationRead, dependencies=[rotation_manage])
def restore_rotation(group_id: UUID, db: Session = Depends(get_db)):
    return service.restore(db, LaboratoryRotationGroup, group_id)
