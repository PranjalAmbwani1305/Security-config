-- Runs once when the dev database is first created (as the POSTGRES_USER superuser).
-- The API must NOT connect as a superuser: superusers bypass row-level security.
-- Migrations run as the owner role (sentinel); the API runs as sentinel_app.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE ROLE sentinel_app LOGIN PASSWORD 'sentinel_app' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE sentinel TO sentinel_app;
GRANT USAGE ON SCHEMA public TO sentinel_app;

-- Tables later created by the migration role are usable by the app role.
ALTER DEFAULT PRIVILEGES FOR ROLE sentinel IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sentinel_app;
ALTER DEFAULT PRIVILEGES FOR ROLE sentinel IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sentinel_app;
