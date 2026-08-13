# AI Timetable frontend

Phase 1 provides authentication, the authenticated application shell, dashboard summaries, timetable browsing, timetable workflow controls, and read-only timetable-version views.

## Run locally

1. Copy `.env.example` to `.env.local` and confirm the FastAPI URL.
2. Start the backend at `http://127.0.0.1:8000`.
3. Install and start the frontend:

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`.

## Verification

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

JWTs are kept out of application logs and UI. The current backend returns tokens in response bodies, so this phase stores them in browser storage and rotates them through the refresh endpoint. A future cookie-based backend contract should use secure, HTTP-only cookies.
