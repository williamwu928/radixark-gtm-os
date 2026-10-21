"""Database layer: SQLAlchemy models and session factory.

DATABASE_URL selects the backend: sqlite:///data/gtm.db locally (default),
postgresql+psycopg://... on Railway. Research tables are rebuildable from
sources; CRM tables are human-maintained and never overwritten by imports.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, create_engine, event, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        (ROOT / "data").mkdir(exist_ok=True)
        return f"sqlite:///{ROOT / 'data' / 'gtm.db'}"
    # Railway hands out postgres://; SQLAlchemy 2 wants a driver-qualified scheme.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Base(DeclarativeBase):
    pass


# ---------- Reference ----------
class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    fit_hypothesis: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # sglang, miles, sglang-omni
    name: Mapped[str] = mapped_column(String(80))


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(600))
    type: Mapped[str | None] = mapped_column(String(80))
    published: Mapped[str | None] = mapped_column(String(20))


# ---------- Research (rebuildable) ----------
class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # ACC-001 or LF-xxxx
    name: Mapped[str] = mapped_column(String(200), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    business_unit: Mapped[str | None] = mapped_column(String(120))
    segment_id: Mapped[str | None] = mapped_column(ForeignKey("segments.id"))
    segment_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    vertical: Mapped[str | None] = mapped_column(String(120))
    origin: Mapped[str] = mapped_column(String(20), default="researched")  # researched | lfai | mad | manual
    source_category: Mapped[str | None] = mapped_column(String(200))  # category path as the source gives it
    homepage: Mapped[str | None] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(80))
    domain: Mapped[str | None] = mapped_column(String(200), index=True)
    github_org: Mapped[str | None] = mapped_column(String(120), index=True)
    hf_org: Mapped[str | None] = mapped_column(String(120), index=True)
    crunchbase_slug: Mapped[str | None] = mapped_column(String(160), index=True)
    landscape_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    # ---- CRM fields (human-maintained; imports never touch these) ----
    relationship_status: Mapped[str] = mapped_column(String(40), default="Unset")
    status_date: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[str | None] = mapped_column(String(10))
    next_action: Mapped[str | None] = mapped_column(Text)
    next_action_due: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    segment: Mapped[Segment | None] = relationship()
    aliases: Mapped[list["Alias"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    products: Mapped[list["AccountProduct"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    notes: Mapped[list["Note"]] = relationship(back_populates="account", cascade="all, delete-orphan", order_by="Note.date.desc()")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(back_populates="account", cascade="all, delete-orphan", order_by="Activity.date.desc()")
    projects: Mapped[list["Project"]] = relationship(back_populates="org")
    ranks: Mapped[list["Rank"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class Alias(Base):
    __tablename__ = "aliases"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    alias_type: Mapped[str] = mapped_column(String(30))  # display_name|domain|github_org|hf_org|crunchbase|lf_name
    value: Mapped[str] = mapped_column(String(300), index=True)
    account: Mapped[Account] = relationship(back_populates="aliases")


class AccountProduct(Base):
    __tablename__ = "account_products"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    relevance: Mapped[str] = mapped_column(String(30), default="Suggested fit")  # Confirmed use | Suggested fit
    account: Mapped[Account] = relationship(back_populates="products")
    product: Mapped[Product] = relationship()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    repo_url: Mapped[str | None] = mapped_column(String(300))
    homepage: Mapped[str | None] = mapped_column(String(300))
    org_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(80))  # RadixArk product | LF project | OSS project
    hosting_status: Mapped[str | None] = mapped_column(String(40))  # graduated|incubating|sandbox
    source_category: Mapped[str | None] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(20), default="manual")
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    org: Mapped[Account | None] = relationship(back_populates="projects")


class ModelRecord(Base):
    __tablename__ = "models"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)  # HF model id
    publisher_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    family: Mapped[str | None] = mapped_column(String(120))
    modality: Mapped[str | None] = mapped_column(String(60))
    downloads_30d: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str | None] = mapped_column(String(30))
    sglang_supported: Mapped[bool | None] = mapped_column(Boolean)
    providers: Mapped[list | None] = mapped_column(JSON)  # serving providers from HF mapping
    snapshot_date: Mapped[str | None] = mapped_column(String(20))
    publisher: Mapped[Account | None] = relationship()


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40))  # seed | lfai | mad | huggingface | github
    snapshot_ref: Mapped[str | None] = mapped_column(String(300))
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    added: Mapped[int] = mapped_column(Integer, default=0)
    changed: Mapped[int] = mapped_column(Integer, default=0)
    removed: Mapped[int] = mapped_column(Integer, default=0)
    needs_review: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="ok")
    log: Mapped[list | None] = mapped_column(JSON)


class ImportChange(Base):
    __tablename__ = "import_changes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # added | changed | removed | review
    entity: Mapped[str] = mapped_column(String(20))  # account | project
    entity_id: Mapped[str | None] = mapped_column(String(80))
    detail: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class Rank(Base):
    __tablename__ = "ranks"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # scale | proximity
    rank: Mapped[int | None] = mapped_column(Integer)
    of: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column()
    inputs: Mapped[dict | None] = mapped_column(JSON)
    missing: Mapped[list | None] = mapped_column(JSON)
    rubric: Mapped[str] = mapped_column(String(10), default="v1")
    snapshot_date: Mapped[str] = mapped_column(String(20))
    account: Mapped[Account] = relationship(back_populates="ranks")


# ---------- CRM (human-maintained) ----------
class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    source_url: Mapped[str | None] = mapped_column(String(600))
    date: Mapped[date] = mapped_column(Date, default=date.today)
    author: Mapped[str | None] = mapped_column(String(120))
    account: Mapped[Account] = relationship(back_populates="notes")
    source: Mapped[Source | None] = relationship()


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str | None] = mapped_column(String(160))
    buying_role: Mapped[str | None] = mapped_column(String(60))  # Technical champion | Budget owner | Procurement | Intro route
    email: Mapped[str | None] = mapped_column(String(200))
    relationship_owner: Mapped[str | None] = mapped_column(String(120))
    last_verified: Mapped[date | None] = mapped_column(Date)
    account: Mapped[Account] = relationship(back_populates="contacts")


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))  # Call | Meeting | Email | Task | Note
    date: Mapped[date] = mapped_column(Date, default=date.today)
    owner: Mapped[str | None] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    due: Mapped[date | None] = mapped_column(Date)
    account: Mapped[Account] = relationship(back_populates="activities")


class Opportunity(Base):
    """One current opportunity per existing account, independent of source research."""
    __tablename__ = "account_opportunities"
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), primary_key=True)
    icp_segment: Mapped[str] = mapped_column(String(80), default="Unclassified")
    workload: Mapped[str] = mapped_column(Text, default="")
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    opportunity_type: Mapped[str] = mapped_column(String(20), default="")
    stage: Mapped[str] = mapped_column(String(20), default="Research")
    basis: Mapped[str] = mapped_column(String(30), default="Hypothesis")
    evidence: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


# ---------- Engine ----------
_engine = None
_Session: sessionmaker | None = None


def engine():
    global _engine, _Session
    if _engine is None:
        url = database_url()
        kw = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kw)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(dbapi_conn, _):
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
        _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def session() -> Session:
    engine()
    return _Session()


# Columns added after schema v1 shipped: (table, column, DDL type). Applied once, idempotently.
_ADDED_COLUMNS = [("accounts", "country", "VARCHAR(80)")]


def _migrate(eng) -> None:
    from sqlalchemy import inspect, text
    insp = inspect(eng)
    with eng.begin() as conn:
        for table, col, ddl in _ADDED_COLUMNS:
            if table in insp.get_table_names() and col not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def init_db() -> None:
    _backup_before_crm_upgrade(engine())
    Base.metadata.create_all(engine())
    _migrate(engine())
    with session() as s:
        if not s.get(Meta, "schema_version"):
            s.add(Meta(key="schema_version", value=str(SCHEMA_VERSION)))
            s.commit()


def is_empty() -> bool:
    with session() as s:
        return s.execute(select(Account.id).limit(1)).first() is None


def _backup_before_crm_upgrade(eng) -> None:
    """Back up an existing register before the additive opportunity-table upgrade."""
    from sqlalchemy import inspect, MetaData
    import gzip
    import json
    import sqlite3
    tables = inspect(eng).get_table_names()
    if "accounts" not in tables or "account_opportunities" in tables:
        return
    folder = Path(os.environ.get("GTM_BACKUP_DIR", ROOT / "data" / "backups"))
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    if eng.dialect.name == "sqlite" and eng.url.database not in (None, "", ":memory:"):
        with sqlite3.connect(eng.url.database) as source, sqlite3.connect(folder / f"before-crm-{stamp}.db") as target:
            source.backup(target)
    else:
        metadata = MetaData()
        with eng.connect() as conn:
            if eng.dialect.name == "postgresql":
                conn = conn.execution_options(isolation_level="REPEATABLE READ")
            with conn.begin():
                metadata.reflect(conn)
                snapshot = {table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
                            for table in metadata.sorted_tables}
                with gzip.open(folder / f"before-crm-{stamp}.json.gz", "wt", encoding="utf-8") as out:
                    json.dump(snapshot, out, default=str)
