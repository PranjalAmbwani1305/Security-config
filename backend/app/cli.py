"""Operator commands.  Usage (from backend/):

    python -m app.cli create-platform-admin --email ops@example.com --name "Ops"

The password is read from the SENTINEL_ADMIN_PASSWORD env var or prompted.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_db
from app.models import AuthIdentity, User
from app.services.audit import record_audit
from app.services.auth_service import check_password_policy, normalize_email


def create_platform_admin(email: str, name: str) -> None:
    password = os.getenv("SENTINEL_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    check_password_policy(password)
    db = next(get_db())
    email = normalize_email(email)
    if db.scalar(select(User.id).where(User.email == email)):
        sys.exit(f"User {email} already exists")
    user = User(email=email, full_name=name, email_verified=True, is_platform_admin=True)
    db.add(user)
    db.flush()
    db.add(AuthIdentity(user_id=user.id, provider="password", subject=str(user.id),
                        secret_hash=hash_password(password)))
    record_audit(db, action="platform_admin.created", object_type="user", object_id=user.id,
                 organization_id=None, actor_user_id=None, changes={"via": "cli"})
    db.commit()
    print(f"Platform administrator created: {email}")


def seed_library_cmd() -> None:
    from app.services.library import seed_library
    print(seed_library(next(get_db())))


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-platform-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    sub.add_parser("seed-library", help="load/refresh the shipped technology library")
    args = parser.parse_args()
    if args.cmd == "create-platform-admin":
        create_platform_admin(args.email, args.name)
    elif args.cmd == "seed-library":
        seed_library_cmd()


if __name__ == "__main__":
    main()
