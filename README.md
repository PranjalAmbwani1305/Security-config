# Sentinel GRC

AI-assisted GRC checklist, assessment and audit management.

- `backend/`  FastAPI + PostgreSQL (row-level-security multi-tenancy). See `backend/README.md`.
- `frontend/` React + Vite + Tailwind single-page app.
- `legacy/`   The original Streamlit prototype (not part of the deployment).
- `DEPLOY_VERCEL.md` Deployment guide (two Vercel projects + hosted Postgres).

Local dev: `docker compose up --build`, then `cd frontend && cp .env.example .env.development && npm install && npm run dev`.
