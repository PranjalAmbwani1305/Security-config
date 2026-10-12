# Deploying Sentinel GRC on Vercel

Two Vercel projects from the same repo, plus a hosted Postgres.

## 1. Database (Neon / Supabase / Vercel Postgres)
1. Create a Postgres database and copy the **pooled** connection string.
2. Create the restricted API role (RLS is NOT enforced for superusers / table owners).
   Adapt `db/init/01-app-role.sql`, run it as the owner, and use the restricted
   role's credentials as the API's `DATABASE_URL`.
3. Run migrations + seed from your machine, using the **owner** URL:
   ```bash
   cd backend
   pip install -r requirements.txt
   export DATABASE_URL="postgresql://owner:...@host/db?sslmode=require"
   export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   alembic upgrade head
   python -m app.cli seed-library
   python -m app.cli create-platform-admin --email you@example.com --name "You"
   ```

## 2. Backend project
Vercel > Add New Project > import repo > **Root Directory: `backend`** (Framework: FastAPI/Other).
Environment variables:

| Name | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | restricted-role URL (`postgres://` is auto-converted) |
| `JWT_SECRET` | 32+ random chars, must not start with `dev-` |
| `CORS_ORIGINS` | your frontend URL, e.g. `https://sentinel-web.vercel.app` (https, no `*`, no trailing slash) |
| `GOOGLE_CLIENT_ID` | optional |

Check `https://<api>.vercel.app/health` and `/ready`.

## 3. Frontend project
Add New Project > same repo > **Root Directory: `frontend`** (Vite is auto-detected).
Environment variables (build-time, redeploy after changing):

| Name | Value |
|---|---|
| `VITE_API_URL` | the backend URL, e.g. `https://sentinel-api.vercel.app` |
| `VITE_GOOGLE_CLIENT_ID` | optional, same as backend |

## Notes
- Preview deployments get new URLs; add them to `CORS_ORIGINS` (comma-separated) if you need them.
- The old Streamlit prototype now lives in `legacy/`
  is not deployed; set the Root Directory as above.
- Webhooks run inside request time on serverless; long deliveries may hit the 30s limit.
