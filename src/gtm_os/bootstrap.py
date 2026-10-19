"""Idempotent first-run setup: schema, seed register, frozen LF AI & Data snapshot if present.
Safe to run on every start; it only imports when the corresponding run has never happened."""
from __future__ import annotations
from sqlalchemy import select
from . import config
from .db import init_db, session
from .models import ImportRun
from .adapters import seed, landscape


def ensure_seeded():
    init_db()
    with session() as s:
        if s.scalar(select(ImportRun).where(ImportRun.source == "seed").limit(1)) is None:
            seed.run(s)
        if s.scalar(select(ImportRun).where(ImportRun.source == "lfai").limit(1)) is None:
            d = config.SOURCES_DIR / "lfai"
            files = sorted(d.glob("*.yml")) if d.exists() else []
            if files:
                landscape.run(s, "lfai", files[-1])


if __name__ == "__main__":
    ensure_seeded()
    print("bootstrap ok")
