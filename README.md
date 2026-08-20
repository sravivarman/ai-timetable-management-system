# AI-Based Engineering College Timetable Management System

Initial backend foundation for a production-oriented timetable management system.

## Stack

- FastAPI
- SQLAlchemy 2.x
- PostgreSQL
- Alembic
- JWT-ready security utilities

The frontend and future scheduling engine (Google OR-Tools) are intentionally not implemented in this setup.

## Backend setup

Prerequisites: Python 3.11+ and PostgreSQL 15+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `backend/.env` with a secure `SECRET_KEY` and your PostgreSQL connection string.

## Run locally

```powershell
cd backend
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` for service information or `http://127.0.0.1:8000/docs` for the API documentation.

## Administrative reports

The protected frontend Reports workspace includes eleven configurable administrative and scheduling reports with shared filters, selectable/reorderable columns, independent multi-field sorting, preview, and Excel/CSV/Word/PDF downloads. See [docs/reports.md](docs/reports.md) for the report registry, API, export behavior, and the distinction from Master Data CSV files.

Health endpoints are available at:

- `/api/v1/health` and `/api/v1/health/live`: process liveness; safe for container liveness probes.
- `/api/v1/health/ready`: checks PostgreSQL connectivity; suitable for readiness probes and returns `503` while the database is unavailable.

## Database migrations

Create the database configured in `DATABASE_URL`, then run:

```powershell
cd backend
alembic upgrade head
```

The migration creates the authentication and authorization schema, seeds the seven requested roles, and grants the `Administrator` role permission to manage users and roles. The first `POST /api/v1/users` request is a protected bootstrap exception: it creates the initial administrator (and assigns `Administrator` automatically when no role is supplied). All later user and role administration calls require an Administrator access token.

## Seed data

After applying migrations, run the idempotent seed script to ensure all required roles and the default administrator exist:

```powershell
cd backend
python -m scripts.seed
```

The script preserves the existing Administrator account and password hash while ensuring its login username is `administrator`. For a new development database it creates the Administrator with the existing development bootstrap password.

To establish the initial read-only Report Viewer credential, set `REPORT_VIEWER_INITIAL_PASSWORD` before the first seed run:

```powershell
cd backend
$env:REPORT_VIEWER_INITIAL_PASSWORD = "use-a-secure-deployment-secret"
python -m scripts.seed
```

The idempotent seed creates the `REPORT_VIEWER` role, grants only `reports.read`, and creates the active `reportviewer` account without resetting an existing password. If the variable is omitted, the account receives an unavailable random credential; an Administrator must reset it through User Management. Plaintext credentials are never logged.

It also creates the eight VCE departments if missing: CIV, EEE, MEC, ECE, CSE, INF, CSM, and CSD.

For each active seeded department, it also creates one four-year UG B.Tech program if missing.

### Development demo scenario

For a self-contained CSE section, theory/laboratory offerings, two faculty members, and their allocations, run the separate development-only command:

```powershell
cd backend
python -m scripts.seed_demo
```

It is idempotent and prints all created or reused UUIDs. It does not invoke or alter the mandatory system seed. To remove only this demo graph later (while retaining the shared CSE department and academic term), run:

```powershell
cd backend
python -m scripts.cleanup_demo
```

## Departments API

Department endpoints use the `/api/v1/departments` prefix and require an authenticated user. Administrators and Timetable Coordinators can list and view departments; only Administrators can create, update, soft-delete, or restore them.

- `GET /departments?search=&page=1&page_size=20&include_inactive=false`
- `GET /departments/{department_id}`
- `POST /departments`, `PUT /departments/{department_id}`
- `DELETE /departments/{department_id}` (soft delete)
- `POST /departments/{department_id}/restore`

## Programs API

Program endpoints use the `/api/v1/programs` prefix. Administrators and Timetable Coordinators can view programs; only Administrators can create, update, soft-delete, or restore them. Version 1 accepts only four-year UG programs and requires an active Department.

- `GET /programs?search=&department_id=&page=1&page_size=20&include_inactive=false`
- `GET /programs/{program_id}`
- `POST /programs`, `PUT /programs/{program_id}`
- `DELETE /programs/{program_id}` (soft delete)
- `POST /programs/{program_id}/restore`

## Academic Terms API

Academic Term endpoints use the `/api/v1/academic-terms` prefix. Administrators and Timetable Coordinators can view terms; only Administrators can manage them. Terms are constrained to the eight VCE year/semester names and retain historical data through soft deletion.

- `GET /academic-terms?search=&academic_year=&year_number=&semester_number=&is_active=&is_current=`
- `GET /academic-terms/{academic_term_id}`
- `POST /academic-terms`, `PUT /academic-terms/{academic_term_id}`
- `DELETE /academic-terms/{academic_term_id}` (soft delete)
- `POST /academic-terms/{academic_term_id}/restore`

## Authentication API

All API paths use the `/api/v1` prefix. After creating the initial user, use `POST /api/v1/auth/login` to receive an access and refresh token. This endpoint uses the OAuth2 Password flow: submit the account username in the `username` form field and the password in `password`. Email remains contact information and is not accepted as a login identifier. Send the access token as `Authorization: Bearer <token>` for protected endpoints; Swagger's **Authorize** dialog supports this flow directly.

- `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password`
- `POST|GET|PUT|DELETE /roles`
- `POST|GET|PUT|DELETE /users`

Passwords are hashed with Argon2. Logout increments the user's token version, invalidating both the access and refresh tokens issued before logout.

Newly created, changed, reset, or seeded passwords must contain at least 8 characters. This policy does not invalidate existing password hashes or impose a minimum during login.

Usernames are trimmed, stored in lowercase, and unique case-insensitively. They accept letters, digits, `.`, `_`, and `-`. Report Viewer intentionally lacks `account_password.change_self`; its password can only be reset by an Administrator.

## Unified resource availability

Faculty, classrooms, laboratories, and registered room/faculty aliases use one term-specific availability engine. Each profile is `ALL_PERIODS`, `EXCEPT_BLOCKED`, or `ONLY_SELECTED`; slot rows are `BLOCKED` or `ALLOWED`. The frontend master-data and report views provide the same weekly editor and a business-key CSV template (`resource_type`, `resource_code`, `academic_term_code`) without UUID columns.

The generic API is under `/api/v1/resource-availability`. Existing `/api/v1/laboratory-availability-blocks` requests remain supported and use the same persisted slot rows. Existing faculty `preferred` and `avoid` records remain soft scheduling preferences; hard `unavailable` records are mirrored into the unified engine.

## Weekly and Slot-Based scheduling

Timetable plans support two independent demand modes without duplicating the constraint engine:

- `WEEKLY` preserves the recurring Monday–Saturday timetable and existing `sessions_per_week` semantics.
- `SLOT_BASED` schedules against explicitly saved local calendar dates and explicit `sessions_required` values for each Scheduling Slot and Course Offering.

Manage arbitrary Slot definitions, their actual working dates, requirement completeness, and the business-key CSV workflow from **Scheduling Slots** in the frontend. A blank requirement is missing configuration; an explicit `0` means intentionally no session in that Slot. Slot CSV templates use `academic_term`, `slot_code`, `course_code`, and `section_code`; UUIDs are resolved internally.

The API groups include `/api/v1/scheduling-slots`, `/api/v1/slot-course-requirements`, and `/api/v1/semester-session-requirements`. Existing timetable and validation requests remain backward compatible and default to `WEEKLY`. A Semester Requirement is optional: blank means not configured, while zero is an intentional zero-session requirement. Slot totals are reconciled as not configured, under-, fully-, or over-allocated.

Progress and reports use one session-counting service. Multi-period entries count as one session, grouped activities count only after complete group coverage, and current progress selects one authoritative active version per Slot. Approval and publication transitions capture immutable progress snapshots. Date-specific resource exceptions override recurring weekday availability and may cover one period range or the whole date.

Apply migrations `0035` and `0036` before using these features:

```powershell
cd backend
alembic upgrade head
python -m scripts.seed
```

The seed grants Slot, Slot-requirement, and Semester-requirement management to Administrator, Timetable Coordinator, and Dean; HOD and Principal receive read-only access. Report Viewer retains only `reports.read` and receives no planning or exception write permission.

When models are introduced later, generate a migration with:

```powershell
alembic revision --autogenerate -m "describe change"
```

## Layout

```text
backend/
  alembic/       # migration environment and version history
  app/
    core/        # settings, logging, security
    db/          # SQLAlchemy engine, session, metadata
    common/      # shared cross-feature code
    modules/     # feature-based API and application code
  scripts/       # operational commands, including seeds
    main.py      # FastAPI application factory
```
