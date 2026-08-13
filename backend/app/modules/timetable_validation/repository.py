from math import ceil
from datetime import datetime, timezone
from sqlalchemy import func,select
from app.modules.timetable_validation.models import ValidationRun,ValidationIssue
class Repository:
 def create_run(self,db,**data):
  now=datetime.now(timezone.utc);x=ValidationRun(**data,started_at=now,created_at=now,completed_at=now);db.add(x);db.flush();return x
 def create_issues(self,db,run_id,issues):
  now=datetime.now(timezone.utc);rows=[ValidationIssue(validation_run_id=run_id,created_at=now,**x)for x in issues];db.add_all(rows);db.flush();return rows
 def finalize(self,db,run,issues,total_checks=None):
  errors=sum(x["severity"]=="ERROR"for x in issues);warnings=sum(x["severity"]=="WARNING"for x in issues);run.failed_checks=errors;run.warning_checks=warnings;run.total_checks=max(total_checks or len(issues),errors+warnings);run.passed_checks=run.total_checks-errors-warnings;run.status="FAILED"if errors else "WARNING"if warnings else "PASSED";run.completed_at=datetime.now(timezone.utc);db.commit();db.refresh(run);return run
 def page(self,db,m,page,ps,**f):
  q=select(m).where(*[getattr(m,k)==v for k,v in f.items() if v is not None]);total=int(db.scalar(select(func.count()).select_from(q.subquery()))or 0)
  if m is ValidationRun:q=q.order_by(ValidationRun.created_at.desc(),ValidationRun.id.desc())
  return list(db.scalars(q.offset((page-1)*ps).limit(ps))),total,ceil(total/ps)if total else 0
repo=Repository()
