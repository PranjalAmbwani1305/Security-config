# Sentinel GRC — backend (FastAPI)

## Run locally

```bash
cp backend/.env.example backend/.env          # edit JWT_SECRET etc.
docker compose up --build                     # PostgreSQL+pgvector, migrations, API on :8000
# or without Docker, from backend/:
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed-library                # loads the 22-technology library (idempotent; safe to rerun)
uvicorn app.main:app --reload
python -m app.cli create-platform-admin --email ops@example.com --name "Ops"
pytest                                        # SQLite by default; TEST_DATABASE_URL=postgresql+psycopg://... for PostgreSQL
```

Frontend: `cp frontend/.env.example frontend/.env.development`, then `npm install && npm run dev`.

## Authentication

- One internal `users` table. `auth_identities` holds each way to sign in
  (`password`, `google`; Entra ID later) and resolves to the same user.
- Email/password: Argon2id hashes, 12+ character minimum.
- Google Sign-In: create an OAuth 2.0 **Web** client in Google Cloud Console, add your
  frontend origin(s) under *Authorized JavaScript origins*, then set the **same** client ID as
  `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend). The backend verifies the
  Google ID token (signature, audience, issuer, expiry) and requires `email_verified`.
- A Google sign-in links to an existing account only if Google verifies that email. A local account
  whose email was never verified loses its password on link (pre-hijack defence).
- Sessions: 15-min access JWT + rotating refresh token (stored hashed). Replaying a rotated token
  revokes all of that user's sessions. Role/membership are re-read from the database on every request.
- Adding a provider (e.g. Entra): implement `AuthProvider.authenticate()` in `app/auth/providers/`
  and register it in `registry.py`. Routes and account resolution need no changes.

## Roles

`org_admin`, `grc_manager`, `grc_auditor`, `reviewer`, `read_only` — matrix in `app/core/rbac.py`.
Platform administrator is a user flag (manages tenants via `/platform/*`); it grants no access to
any organization's data unless that user is also a member of it.

## Tenant isolation (three independent layers)

1. **Application:** every query filters by the caller's `organization_id`; foreign records are "not found".
2. **Schema:** child tables use composite foreign keys `(organization_id, parent_id)`, so a row cannot
   reference another tenant's parent even if application code has a bug.
3. **PostgreSQL row-level security:** the API sets `app.current_org` per transaction after authentication;
   policies on all tenant tables expose only matching rows (none if unset).

**The API must connect as a non-superuser role without `BYPASSRLS`** (superusers ignore RLS). Run
migrations as the owner role and the API as a separate role: see `db/init/01-app-role.sql`
(docker-compose does this). On AWS RDS, create the equivalent role and use it for the API's `DATABASE_URL`.

## Webhooks

Targets are validated against SSRF (public addresses only, https-only in production, no credentials in
URLs, redirects not followed, re-checked at delivery). Residual DNS-rebinding risk: also restrict egress
at the network layer (security group / egress proxy). `WEBHOOK_ALLOW_PRIVATE=true` is dev-only and refused
when `ENVIRONMENT=production`.

## Status

Done: auth (password + Google), RBAC, audit trail, tenant-scoped engagements / assessments / evidence
(text notes) / findings / risks / remediations / webhooks on PostgreSQL.

Still placeholders (next increments): the checklist library is the original in-code Linux/Windows lists and
`/checklists/{tech}/generate` + `/ai/ask` are the original mock/keyword implementations (not AI);
evidence is text-only until S3 storage; reports are still assembled client-side; no approval workflow yet.
