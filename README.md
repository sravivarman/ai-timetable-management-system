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

The protected frontend Reports workspace includes six configurable administrative reports with shared filters, selectable/reorderable columns, independent multi-field sorting, preview, and Excel/CSV/Word/PDF downloads. See [docs/reports.md](docs/reports.md) for the report registry, API, export behavior, and the distinction from Master Data CSV files.

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

The script creates `admin@vce.ac.in` with the initial password `Admin@123` only when that account does not already exist. Change this password immediately after first use.

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

All API paths use the `/api/v1` prefix. After creating the initial user, use `POST /api/v1/auth/login` to receive an access and refresh token. This endpoint uses the OAuth2 Password flow: submit the email in the `username` form field and the password in `password`. Send the access token as `Authorization: Bearer <token>` for protected endpoints; Swagger's **Authorize** dialog supports this flow directly.

- `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`
- `POST|GET|PUT|DELETE /roles`
- `POST|GET|PUT|DELETE /users`

Passwords are hashed with Argon2. Logout increments the user's token version, invalidating both the access and refresh tokens issued before logout.

## Unified resource availability

Faculty, classrooms, laboratories, and registered room/faculty aliases use one term-specific availability engine. Each profile is `ALL_PERIODS`, `EXCEPT_BLOCKED`, or `ONLY_SELECTED`; slot rows are `BLOCKED` or `ALLOWED`. The frontend master-data and report views provide the same weekly editor and a business-key CSV template (`resource_type`, `resource_code`, `academic_term_code`) without UUID columns.

The generic API is under `/api/v1/resource-availability`. Existing `/api/v1/laboratory-availability-blocks` requests remain supported and use the same persisted slot rows. Existing faculty `preferred` and `avoid` records remain soft scheduling preferences; hard `unavailable` records are mirrored into the unified engine.

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
