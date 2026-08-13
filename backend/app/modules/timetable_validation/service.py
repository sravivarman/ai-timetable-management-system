"""First prerequisite validation rule group."""
from sqlalchemy import select
from app.modules.academic_terms.models import AcademicTerm
from app.modules.departments.models import Department
from app.modules.programs.models import Program
from app.modules.sections.models import Section
from app.modules.course_offerings.models import CourseOffering
from app.modules.combined_teaching.models import CombinedTeachingGroup, CombinedTeachingGroupMember
from app.modules.courses.models import Course, CourseEligibleLaboratory
from app.modules.facilities_constraints.models import SectionClassroomAssignment
from app.modules.faculty.models import Faculty
from app.modules.faculty_allocations.models import TheoryFacultyAllocation, LaboratoryFacultyAllocation
from app.modules.faculty_allocations.workload import configured_faculty_workloads
from app.modules.faculty_scheduling.models import FacultyAvailability
from app.modules.schedule_configuration.models import WorkingDay
from app.modules.schedule_configuration.models import PeriodTiming
from app.modules.facilities.models import Classroom, Laboratory
from app.modules.resource_availability.models import ResourceAvailabilitySlot
from app.modules.resource_availability.service import availability_service
from app.modules.laboratory_batches.models import StudentBatch,LaboratoryBatchConfiguration,LaboratoryRotationGroup
from app.modules.laboratory_batches.services import service as rotation_service
from app.modules.facilities_constraints.models import LaboratoryAvailabilityBlock

def validate(db, request):
 issues=[]
 executed=2  # term activity and scope-shape checks always execute
 def add(code,message,entity_type=None,entity_id=None):issues.append({"severity":"ERROR","issue_code":code,"message":message,"entity_type":entity_type,"entity_id":entity_id,"details":None})
 def warn(code,message,entity_type=None,entity_id=None,details=None):issues.append({"severity":"WARNING","issue_code":code,"message":message,"entity_type":entity_type,"entity_id":entity_id,"details":details})
 term=db.scalar(select(AcademicTerm).where(AcademicTerm.id==request.academic_term_id))
 if not term or not term.is_active:add("TERM_INACTIVE","Academic term does not exist or is inactive","academic_term",request.academic_term_id)
 valid={"COLLEGE":not any((request.department_id,request.program_id,request.section_id)),"DEPARTMENT":request.department_id is not None and request.program_id is None and request.section_id is None,"PROGRAM":request.program_id is not None and request.department_id is None and request.section_id is None,"SECTION":request.section_id is not None and request.department_id is None and request.program_id is None}
 if not valid.get(request.scope_type):add("INVALID_SCOPE","Scope identifiers do not match scope type")
 if request.department_id:
  x=db.scalar(select(Department).where(Department.id==request.department_id));
  if not x or not x.is_active:add("INVALID_SCOPE","Scoped department is inactive","department",request.department_id)
 if request.program_id:
  x=db.scalar(select(Program).where(Program.id==request.program_id));
  if not x or not x.is_active:add("INVALID_SCOPE","Scoped program is inactive","program",request.program_id)
 if request.section_id:
  x=db.scalar(select(Section).where(Section.id==request.section_id));
  if not x or not x.is_active:add("INVALID_SCOPE","Scoped section is inactive","section",request.section_id)
 q=select(Section).where(Section.is_active.is_(True))
 if request.scope_type=="SECTION" and request.section_id:q=q.where(Section.id==request.section_id)
 elif request.scope_type=="PROGRAM" and request.program_id:q=q.where(Section.program_id==request.program_id)
 elif request.scope_type=="DEPARTMENT" and request.department_id:q=q.join(Program,Program.id==Section.program_id).where(Program.department_id==request.department_id)
 sections=list(db.scalars(q)) if term else []
 days=list(db.scalars(select(WorkingDay).where(WorkingDay.is_active.is_(True),WorkingDay.is_working_day.is_(True))))
 validated_labs=set()
 if not sections:add("NO_ACTIVE_SECTIONS","No active sections exist in the selected scope")
 for section in sections:
  executed+=4  # term, strength, primary-classroom, and offering presence
  if section.academic_term_id!=request.academic_term_id:add("SECTION_TERM_MISMATCH","Section does not belong to selected academic term","section",section.id)
  if section.student_strength<=0:add("SECTION_STRENGTH_INVALID","Section student strength must be greater than zero","section",section.id)
  primary=db.scalar(select(SectionClassroomAssignment).where(SectionClassroomAssignment.section_id==section.id,SectionClassroomAssignment.academic_term_id==request.academic_term_id,SectionClassroomAssignment.is_primary.is_(True),SectionClassroomAssignment.is_active.is_(True)))
  if not primary:add("SECTION_NO_PRIMARY_CLASSROOM","Section has no active primary classroom","section",section.id)
  offerings=list(db.scalars(select(CourseOffering).where(CourseOffering.section_id==section.id)))
  if not any(x.is_active for x in offerings):add("SECTION_NO_COURSE_OFFERINGS","Section has no active course offerings","section",section.id)
  for offering in offerings:
   executed+=4  # activity, term, override, and course activity
   if not offering.is_active:add("OFFERING_INACTIVE","Course offering is inactive","course_offering",offering.id)
   if offering.academic_term_id!=section.academic_term_id:add("OFFERING_TERM_MISMATCH","Offering term does not match section term","course_offering",offering.id)
   if offering.weekly_periods_override is not None and offering.weekly_periods_override<=0:add("WEEKLY_PERIODS_INVALID","Weekly periods override must be positive","course_offering",offering.id)
   course=db.scalar(select(Course).where(Course.id==offering.course_id))
   if not course or not course.is_active:add("COURSE_INACTIVE","Course is inactive","course",offering.course_id)
   cfg=None;eligible_ids=set();eligible_laboratories=[];usable_laboratories=[]
   if course and offering.is_active:
    executed+=3
    effective_periods=offering.weekly_periods_override or course.weekly_periods
    session_duration=course.lab_session_duration if course.course_type=="LABORATORY" and course.lab_session_duration else course.session_duration
    sessions_per_week=course.lab_sessions_per_week if course.course_type=="LABORATORY" and course.lab_sessions_per_week else course.sessions_per_week
    if session_duration<1 or sessions_per_week<1 or session_duration*sessions_per_week!=effective_periods:
     add("SESSION_PATTERN_INVALID","Weekly periods must equal session duration multiplied by sessions per week","course_offering",offering.id)
     if course.course_type=="LABORATORY":add("LAB_SESSION_CONFIGURATION_INVALID","Laboratory session pattern is invalid","course",course.id)
    cfg=db.scalar(select(LaboratoryBatchConfiguration).where(LaboratoryBatchConfiguration.course_offering_id==offering.id,LaboratoryBatchConfiguration.is_active.is_(True)))
    effective_group_count=cfg.number_of_groups if cfg else course.default_group_count
    if course.grouping_mode=="GROUPED":
     if not cfg:add("GROUP_CONFIGURATION_MISSING","Grouped offering has no active student-group configuration","course_offering",offering.id)
     batches=list(db.scalars(select(StudentBatch).where(StudentBatch.section_id==offering.section_id,StudentBatch.is_active.is_(True))))
     invalid_groups=any(batch.student_count<=0 or batch.roll_number_start>batch.roll_number_end or batch.student_count!=batch.roll_number_end-batch.roll_number_start+1 for batch in batches)
     if len(batches)!=effective_group_count or invalid_groups:add("STUDENT_BATCHES_INCOMPLETE","Active student groups do not match the effective group count","course_offering",offering.id)
    eligibility_links=list(db.scalars(select(CourseEligibleLaboratory).where(CourseEligibleLaboratory.course_id==course.id,CourseEligibleLaboratory.is_active.is_(True))))
    eligible_ids={link.laboratory_id for link in eligibility_links} or ({course.default_laboratory_id} if course.default_laboratory_id else set())
    eligible_laboratories=[db.get(Laboratory,laboratory_id) for laboratory_id in eligible_ids]
    usable_laboratories=[laboratory for laboratory in eligible_laboratories if laboratory and laboratory.is_active and (laboratory.owning_department_id==course.offering_department_id or laboratory.is_shareable_across_departments)]
    if course.venue_requirement=="LABORATORY_ONLY" and not usable_laboratories:
     add("VENUE_REQUIRED","LABORATORY_ONLY offering has no active eligible laboratory","course_offering",offering.id)
     add("LABORATORY_MISSING","Laboratory offering requires an active laboratory","course_offering",offering.id)
     add("LABORATORY_ELIGIBILITY_MISSING","Laboratory-only offering has no usable eligible laboratory","course_offering",offering.id)
    if course.venue_requirement=="CLASSROOM_ONLY" and not primary:add("VENUE_REQUIRED","CLASSROOM_ONLY offering has no active classroom","course_offering",offering.id)
    if course.venue_requirement=="CLASSROOM_OR_LABORATORY" and not primary and not usable_laboratories:add("NO_ELIGIBLE_VENUE","Offering has no active classroom or eligible laboratory","course_offering",offering.id)
    if course.default_laboratory_id and course.default_laboratory_id not in eligible_ids:add("PREFERRED_LABORATORY_NOT_ELIGIBLE","Course preferred laboratory is not eligible","course",course.id)
    for laboratory in eligible_laboratories:
     if not laboratory or not laboratory.is_active:add("LABORATORY_INACTIVE","Course eligibility references an inactive laboratory","course",course.id)
     elif laboratory.owning_department_id!=course.offering_department_id and not laboratory.is_shareable_across_departments:add("LABORATORY_NOT_SHAREABLE","Cross-department eligible laboratory is not shareable","course",course.id)
    mode=offering.laboratory_selection_mode;override=offering.laboratory_override_id
    if mode not in {"AUTO","PREFERRED","FIXED"} or mode=="AUTO" and override or mode in {"PREFERRED","FIXED"} and not override:add("INVALID_LABORATORY_OVERRIDE","Offering laboratory selection is invalid","course_offering",offering.id)
    if override and override not in eligible_ids:add("FIXED_LABORATORY_NOT_ELIGIBLE" if mode=="FIXED" else "PREFERRED_LABORATORY_NOT_ELIGIBLE","Offering laboratory is not eligible for the course","course_offering",offering.id)
    candidate_laboratories=[db.get(Laboratory,override)] if mode=="FIXED" and override else usable_laboratories
    if candidate_laboratories and all(any(code=="RESOURCE_NO_AVAILABLE_PERIODS" for code,_,_ in availability_service.validate(db,"LABORATORY",laboratory.id,request.academic_term_id)) for laboratory in candidate_laboratories if laboratory):add("NO_AVAILABLE_ELIGIBLE_LABORATORY","No eligible laboratory has any available instructional period","course_offering",offering.id)
   if course and course.course_type in {"THEORY","CDC","PRACTICAL"}:
    executed+=1
    allocations=list(db.scalars(select(TheoryFacultyAllocation).where(TheoryFacultyAllocation.course_offering_id==offering.id,TheoryFacultyAllocation.is_active.is_(True))))
    if not allocations:add("THEORY_FACULTY_MISSING" if course.course_type=="THEORY" else "FACULTY_ALLOCATION_MISSING","Offering has no active faculty allocation","course_offering",offering.id)
    elif len(allocations)>1:add("THEORY_MULTIPLE_FACULTY" if course.course_type=="THEORY" else "FACULTY_ALLOCATION_MULTIPLE","Offering has multiple active faculty allocations","course_offering",offering.id)
    for allocation in allocations:
     faculty=db.scalar(select(Faculty).where(Faculty.id==allocation.faculty_id))
     if not faculty or not faculty.is_active:add("FACULTY_INACTIVE","Allocated faculty is inactive","faculty",allocation.faculty_id)
   if course and course.course_type=="LABORATORY":
    executed+=4
    allocations=list(db.scalars(select(LaboratoryFacultyAllocation).where(LaboratoryFacultyAllocation.course_offering_id==offering.id,LaboratoryFacultyAllocation.role_type=="MAIN",LaboratoryFacultyAllocation.is_active.is_(True))))
    if not allocations:add("LAB_MAIN_FACULTY_MISSING","Laboratory offering has no active MAIN faculty allocation","course_offering",offering.id)
    for allocation in allocations:
     faculty=db.scalar(select(Faculty).where(Faculty.id==allocation.faculty_id))
     if not faculty or not faculty.is_active:add("FACULTY_INACTIVE","Allocated faculty is inactive","faculty",allocation.faculty_id)
    if course.grouping_mode=="GROUPED" and not cfg:add("BATCH_CONFIGURATION_MISSING","Laboratory offering has no active batch configuration","course_offering",offering.id)
    if cfg and course.default_lab_group_count is not None:
     executed+=1
     if cfg.number_of_groups!=course.default_lab_group_count:
      warn("LAB_BATCH_COUNT_OVERRIDE","Offering-specific laboratory group count overrides the course default","course_offering",offering.id,{"course_default_lab_group_count":course.default_lab_group_count,"effective_lab_group_count":cfg.number_of_groups})
    for laboratory in usable_laboratories:
     if days and laboratory.id not in validated_labs:
      validated_labs.add(laboratory.id);executed+=4
      aliases={"RESOURCE_INVALID_MODE":"LAB_INVALID_AVAILABILITY_MODE","RESOURCE_AVAILABILITY_CONFLICT":"LAB_AVAILABILITY_CONFLICT","RESOURCE_SELECTED_PERIODS_EMPTY":"LAB_SELECTED_PERIODS_EMPTY","RESOURCE_NO_AVAILABLE_PERIODS":"LAB_NO_AVAILABLE_PERIODS"}
      for code,severity,message in availability_service.validate(db,"LABORATORY",laboratory.id,request.academic_term_id):
       add(code,message,"laboratory",laboratory.id);add(aliases[code],message,"laboratory",laboratory.id)
       if code=="RESOURCE_NO_AVAILABLE_PERIODS":add("LABORATORY_FULLY_BLOCKED","Laboratory is unavailable for every working period","laboratory",laboratory.id)
 scoped_section_ids={section.id for section in sections}
 # Combined teaching is a shared event across complete section offerings, not
 # student-group rotation. Validate its independent compatibility contract.
 combined_groups=list(db.scalars(select(CombinedTeachingGroup).where(CombinedTeachingGroup.academic_term_id==request.academic_term_id,CombinedTeachingGroup.is_active.is_(True))))
 for group in combined_groups:
  members=list(db.scalars(select(CombinedTeachingGroupMember).where(CombinedTeachingGroupMember.combined_teaching_group_id==group.id,CombinedTeachingGroupMember.is_active.is_(True))))
  member_offerings=[db.get(CourseOffering,member.course_offering_id) for member in members];member_sections=[db.get(Section,offering.section_id) for offering in member_offerings if offering]
  if not any(section and section.id in scoped_section_ids for section in member_sections):continue
  executed+=10
  if len(members)<2:add("COMBINED_TEACHING_MINIMUM_SECTIONS","Combined teaching requires at least two sections","combined_teaching_group",group.id)
  if any(section and section.id not in scoped_section_ids for section in member_sections):add("COMBINED_TEACHING_INCOMPLETE","The selected timetable scope does not contain every section in the combined class","combined_teaching_group",group.id)
  if len(member_offerings)!=len(members) or any(not offering or not offering.is_active for offering in member_offerings):add("COMBINED_TEACHING_INCOMPLETE","Combined teaching membership is incomplete or inactive","combined_teaching_group",group.id)
  if any(offering and offering.academic_term_id!=group.academic_term_id for offering in member_offerings):add("COMBINED_TEACHING_TERM_MISMATCH","Combined offerings must share the academic term","combined_teaching_group",group.id)
  if any(offering and offering.course_id!=group.course_id for offering in member_offerings):add("COMBINED_TEACHING_COURSE_MISMATCH","Combined offerings must share the configured course","combined_teaching_group",group.id)
  if len({section.id for section in member_sections if section})!=len(member_sections):add("COMBINED_TEACHING_DUPLICATE_SECTION","A section occurs more than once in the combined group","combined_teaching_group",group.id)
  if any(not section or not section.student_strength or section.student_strength<=0 for section in member_sections):add("COMBINED_TEACHING_SECTION_STRENGTH_MISSING","Every participating section requires positive strength","combined_teaching_group",group.id)
  course=db.get(Course,group.course_id);effective={offering.weekly_periods_override or course.weekly_periods for offering in member_offerings if offering and course}
  if not course or len(effective)!=1 or next(iter(effective),0)!=course.session_duration*course.sessions_per_week:add("COMBINED_TEACHING_SESSION_MISMATCH","Combined offerings require one compatible complete session pattern","combined_teaching_group",group.id)
  allocation_model=LaboratoryFacultyAllocation if course and course.course_type=="LABORATORY" else TheoryFacultyAllocation
  allocated={offering.id for offering in member_offerings if offering and db.scalar(select(allocation_model.id).where(allocation_model.course_offering_id==offering.id,allocation_model.faculty_id==group.faculty_id,allocation_model.is_active.is_(True),*((allocation_model.role_type=="MAIN",) if allocation_model is LaboratoryFacultyAllocation else ())))}
  if not group.faculty_id:add("COMBINED_TEACHING_FACULTY_MISSING","Combined teaching requires faculty","combined_teaching_group",group.id)
  elif allocated!={offering.id for offering in member_offerings if offering}:add("COMBINED_TEACHING_FACULTY_MISMATCH","Combined faculty must be allocated to every offering","combined_teaching_group",group.id)
  classroom=db.get(Classroom,group.preferred_classroom_id) if group.preferred_classroom_id else None;laboratory=db.get(Laboratory,group.preferred_laboratory_id) if group.preferred_laboratory_id else None
  if course and course.venue_requirement=="CLASSROOM_ONLY" and (not classroom or not classroom.is_active):add("COMBINED_TEACHING_ROOM_MISSING","Combined classroom is missing or inactive","combined_teaching_group",group.id)
  if course and course.venue_requirement=="LABORATORY_ONLY" and (not laboratory or not laboratory.is_active):add("COMBINED_TEACHING_NO_ELIGIBLE_VENUE","Combined laboratory is missing or inactive","combined_teaching_group",group.id)
  strength=sum(section.student_strength for section in member_sections if section and section.student_strength)
  if classroom and classroom.capacity is not None and classroom.capacity<strength:add("COMBINED_TEACHING_CAPACITY_EXCEEDED","Combined section strength exceeds classroom capacity","combined_teaching_group",group.id)
 # Synchronized rotations are checked as complete matrices. Independent
 # one-group laboratories intentionally remain outside these groups.
 rotation_groups=list(db.scalars(select(LaboratoryRotationGroup).where(LaboratoryRotationGroup.section_id.in_(scoped_section_ids),LaboratoryRotationGroup.academic_term_id==request.academic_term_id,LaboratoryRotationGroup.is_active.is_(True)))) if scoped_section_ids else []
 for rotation_group in rotation_groups:
  rotation_issues=rotation_service.rotation_issues(db,rotation_group);executed+=max(1,8)
  for issue in rotation_issues:add(issue["issue_code"],issue["message"],"laboratory_rotation_group",rotation_group.id)
 for section in sections:
  rotating_configs=list(db.scalars(select(LaboratoryBatchConfiguration).join(CourseOffering,CourseOffering.id==LaboratoryBatchConfiguration.course_offering_id).where(LaboratoryBatchConfiguration.section_id==section.id,LaboratoryBatchConfiguration.is_active.is_(True),LaboratoryBatchConfiguration.is_rotation_enabled.is_(True),CourseOffering.academic_term_id==request.academic_term_id)))
  multi=[configuration for configuration in rotating_configs if configuration.number_of_groups>1]
  if rotating_configs:
   executed+=2
   if any(configuration.number_of_groups==1 for configuration in rotating_configs):add("ROTATION_SINGLE_GROUP_NOT_ALLOWED","Single-group laboratories must remain outside rotations","section",section.id)
   if len(multi)==1:add("ROTATION_REQUIRES_MULTIPLE_LABS","At least two multi-group laboratory offerings are required for rotation","section",section.id)
   if len({configuration.number_of_groups for configuration in multi})>1:add("ROTATION_GROUP_CONFIGURATION_MISMATCH","Rotating laboratory offerings use different student-group counts","section",section.id)
   assigned_config_ids={group.laboratory_batch_configuration_id for group in rotation_groups if group.section_id==section.id and group.laboratory_batch_configuration_id}
   if multi and not any(configuration.id in assigned_config_ids for configuration in multi) and not any(group.section_id==section.id for group in rotation_groups):add("ROTATION_INCOMPLETE","Rotation-enabled offerings have no synchronized rotation matrix","section",section.id)
 # Configured workload is physical faculty occupancy, not per-group academic
 # contact periods. The shared calculator expands ordinary grouped offerings
 # and counts explicit synchronized-rotation assignments without double-counting.
 scoped_offering_ids={offering.id for section in sections for offering in db.scalars(select(CourseOffering).where(CourseOffering.section_id==section.id,CourseOffering.is_active.is_(True)))}
 workloads=configured_faculty_workloads(db,offering_ids=scoped_offering_ids,academic_term_id=request.academic_term_id);allocated=set(workloads)
 for faculty_id,hours in workloads.items():
  executed+=3
  faculty=db.scalar(select(Faculty).where(Faculty.id==faculty_id))
  if faculty and hours>faculty.maximum_weekly_workload:add("FACULTY_OVER_MAX_WORKLOAD","Configured workload exceeds faculty maximum","faculty",faculty_id)
  if faculty and hours<faculty.minimum_weekly_workload:issues.append({"severity":"WARNING","issue_code":"FACULTY_UNDER_MIN_WORKLOAD","message":"Configured workload is below faculty minimum","entity_type":"faculty","entity_id":faculty_id,"details":None})
  unavailable={(x.day_of_week,x.period_number) for x in db.scalars(select(FacultyAvailability).where(FacultyAvailability.faculty_id==faculty_id,FacultyAvailability.academic_term_id==request.academic_term_id,FacultyAvailability.availability_type=="unavailable",FacultyAvailability.is_active.is_(True)))}
  if days and len(unavailable)>=len(days)*7:add("FACULTY_FULLY_UNAVAILABLE","Allocated faculty is unavailable for every working period","faculty",faculty_id)
 # global schedule and facility-reference readiness
 executed+=3
 if {d.day_name for d in days}!={"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"}:add("WORKING_DAYS_INCOMPLETE","Monday through Saturday active working days are required")
 for schedule_type in ("FIRST_YEAR","HIGHER_YEAR"):
  executed+=3
  timings=list(db.scalars(select(PeriodTiming).where(PeriodTiming.schedule_type==schedule_type,PeriodTiming.is_active.is_(True))))
  instructional=[x for x in timings if x.is_instructional]
  if len(instructional)!=7 or len({x.period_number for x in instructional})!=7 or any(x.period_number not in range(1,8) for x in instructional):add("PERIOD_TIMINGS_INVALID",f"{schedule_type} must contain seven unique instructional periods")
  breaks=[x.break_type for x in timings if not x.is_instructional]
  expected={"FIRST_YEAR":("LUNCH",4,"SHORT_BREAK",7),"HIGHER_YEAR":("SHORT_BREAK",3,"LUNCH",6)}[schedule_type]
  by_sequence={x.sequence_number:x.break_type for x in timings if not x.is_instructional}
  if "LUNCH" not in breaks or "SHORT_BREAK" not in breaks or by_sequence.get(expected[1])!=expected[0] or by_sequence.get(expected[3])!=expected[2]:add("PERIOD_TIMINGS_INVALID",f"{schedule_type} lunch/short-break sequence is invalid")
 for availability in db.scalars(select(FacultyAvailability).where(FacultyAvailability.is_active.is_(True),FacultyAvailability.academic_term_id==request.academic_term_id)):
  executed+=1
  if availability.day_of_week not in {d.day_name for d in days} or availability.period_number not in range(1,8):add("FACULTY_AVAILABILITY_INVALID","Faculty availability references invalid day or period","faculty_availability",availability.id)
 for assignment in db.scalars(select(SectionClassroomAssignment).where(SectionClassroomAssignment.is_active.is_(True),SectionClassroomAssignment.academic_term_id==request.academic_term_id)):
  executed+=1
  classroom=db.scalar(select(__import__("app.modules.facilities.models",fromlist=["Classroom"]).Classroom).where(__import__("app.modules.facilities.models",fromlist=["Classroom"]).Classroom.id==assignment.classroom_id))
  if not classroom or not classroom.is_active:add("FACILITY_REFERENCE_INACTIVE","Classroom assignment references inactive classroom","section_classroom_assignment",assignment.id)
 for block in db.scalars(select(LaboratoryAvailabilityBlock).where(LaboratoryAvailabilityBlock.resource_type=="LABORATORY",LaboratoryAvailabilityBlock.is_active.is_(True),LaboratoryAvailabilityBlock.academic_term_id==request.academic_term_id)):
  executed+=1
  lab=db.scalar(select(Laboratory).where(Laboratory.id==block.laboratory_id));day=db.scalar(select(WorkingDay).where(WorkingDay.id==block.working_day_id))
  if not lab or not lab.is_active or not day or not day.is_active:add("FACILITY_REFERENCE_INACTIVE","Laboratory block references inactive facility","laboratory_availability_block",block.id)
 # Defensive duplicate detection supports legacy/imported data despite normal constraints.
 for model,columns in ((SectionClassroomAssignment,("section_id","classroom_id","academic_term_id")),(LaboratoryAvailabilityBlock,("resource_type","resource_id","academic_term_id","working_day_id","period_number"))):
  query=select(model).where(model.is_active.is_(True))
  rows=list(db.scalars(query))
  seen=set()
  for row in rows:
   key=tuple(getattr(row,column) for column in columns)
   if key in seen:add("DUPLICATE_FACILITY_CONSTRAINT","Duplicate active facility constraint detected",model.__tablename__,row.id)
   seen.add(key)
 # All hard availability resources share the same generic validation rules.
 generic_pairs={(slot.resource_type,slot.resource_id) for slot in db.scalars(select(ResourceAvailabilitySlot).where(ResourceAvailabilitySlot.academic_term_id==request.academic_term_id,ResourceAvailabilitySlot.is_active.is_(True)))}
 for assignment in db.scalars(select(SectionClassroomAssignment).where(SectionClassroomAssignment.academic_term_id==request.academic_term_id,SectionClassroomAssignment.is_active.is_(True))):generic_pairs.add(("CLASSROOM",assignment.classroom_id))
 generic_pairs|={("FACULTY",faculty_id) for faculty_id in allocated}
 for resource_type,resource_id in sorted(generic_pairs,key=lambda value:(value[0],str(value[1]))):
  if resource_type=="LABORATORY":continue
  executed+=1
  for code,severity,message in availability_service.validate(db,resource_type,resource_id,request.academic_term_id):add(code,message,resource_type.lower(),resource_id)
 return issues, executed
