"""Technology library: loading the shipped seed and resolving technology names."""
import json
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LibraryControl, LibraryTechnology

SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "library.json"


@lru_cache
def _seed() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120]


def seed_library(db: Session) -> dict:
    """Idempotent upsert of the shipped technologies/controls. Never touches
    organization data. Existing rows are updated in place so reruns are safe."""
    created_t = created_c = 0
    for t in _seed()["technologies"]:
        tech = db.scalar(select(LibraryTechnology).where(LibraryTechnology.slug == t["slug"]))
        if tech is None:
            tech = LibraryTechnology(slug=t["slug"], name=t["name"], category=t["category"], basis=t["basis"])
            db.add(tech)
            db.flush()
            created_t += 1
        else:
            tech.name, tech.category, tech.basis = t["name"], t["category"], t["basis"]
        existing = {c.control_id: c for c in db.scalars(
            select(LibraryControl).where(LibraryControl.technology_id == tech.id))}
        for pos, c in enumerate(t["controls"]):
            row = existing.get(c["control_id"])
            if row is None:
                db.add(LibraryControl(technology_id=tech.id, position=pos, reference_verified=False, **c))
                created_c += 1
            else:
                row.category, row.control, row.audit_step = c["category"], c["control"], c["audit_step"]
                row.reference, row.position = c["reference"], pos
    db.commit()
    return {"technologies_created": created_t, "controls_created": created_c}


def find_library_technology(db: Session, name: str) -> LibraryTechnology | None:
    """Match a user-supplied technology string to a library technology by alias,
    slug or (case-insensitive) name. Returns None for technologies not in the library."""
    key = slugify(name)
    key = _seed()["aliases"].get(key, key)
    tech = db.scalar(select(LibraryTechnology).where(LibraryTechnology.slug == key))
    if tech:
        return tech
    lowered = name.strip().lower()
    for t in db.scalars(select(LibraryTechnology)):
        if lowered in (t.name.lower(), f"{t.name} ({t.basis})".lower()):
            return t
    return None
