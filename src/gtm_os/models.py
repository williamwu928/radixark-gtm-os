"""ORM schema. Research tables are rebuilt by imports; CRM fields on Account, plus Note, Contact,
Activity, are human-maintained and never overwritten by an import."""
from __future__ import annotations
from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Float, Date, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    fit_hypothesis: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)   # ACC-001, LF-0001, MAD-0001
    name: Mapped[str] = mapped_column(String(200), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))
    business_unit: Mapped[str | None] = mapped_column(String(120))
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.id"), index=True)
    vertical: Mapped[str | None] = mapped_column(String(120))
    origin: Mapped[str] = mapped_column(String(32), default="Researched")  # Researched | LF AI & Data | MAD
    homepage: Mapped[str | None] = mapped_column(String(300))
    domain: Mapped[str | None] = mapped_column(String(200), index=True)
    github_org: Mapped[str | None] = mapped_column(String(120), index=True)
    hf_org: Mapped[str | None] = mapped_column(String(120), index=True)
    source_category: Mapped[str | None] = mapped_column(String(200))  # category path as the source gives it
    # --- CRM fields: never touched by imports ---
    relationship_status: Mapped[str] = mapped_column(String(32), default="Unset")
    status_date: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(8), default="Unset")
    next_action: Mapped[str | None] = mapped_column(Text)
    next_action_due: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    segment: Mapped[Segment] = relationship()
    aliases: Mapped[list[AccountAlias]] = relationship(back_populates="account", cascade="all, delete-orphan")
    products: Mapped[list[AccountProduct]] = relationship(back_populates="account", cascade="all, delete-orphan")
    notes: Mapped[list[Note]] = relationship(back_populates="account", cascade="all, delete-orphan", order_by="Note.date.desc()")
    contacts: Mapped[list[Contact]] = relationship(back_populates="account", cascade="all, delete-orphan")
    activities: Mapped[list[Activity]] = relationship(back_populates="account", cascade="all, delete-orphan", order_by="Activity.date.desc()")


class AccountAlias(Base):
    __tablename__ = "account_aliases"
    __table_args__ = (UniqueConstraint("alias_type", "value"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    alias_type: Mapped[str] = mapped_column(String(32))  # display_name | domain | github_login | hf_org | lf_name | mad_name | crunchbase
    value: Mapped[str] = mapped_column(String(300), index=True)
    account: Mapped[Account] = relationship(back_populates="aliases")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class AccountProduct(Base):
    __tablename__ = "account_products"
    __table_args__ = (UniqueConstraint("account_id", "product_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    account: Mapped[Account] = relationship(back_populates="products")
    product: Mapped[Product] = relationship()


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[str | None] = mapped_column(String(80))
    published: Mapped[str | None] = mapped_column(String(20))


class Note(Base):
    """A research note: a sentence about the account, a source and a date."""
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    source_url: Mapped[str | None] = mapped_column(String(500))
    date: Mapped[date] = mapped_column(Date, default=date.today)
    author: Mapped[str | None] = mapped_column(String(120))
    seed_ref: Mapped[str | None] = mapped_column(String(32), unique=True)  # EV-001 … so re-imports do not duplicate
    account: Mapped[Account] = relationship(back_populates="notes")
    source: Mapped[Source | None] = relationship()


class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[str | None] = mapped_column(String(60))  # Technical champion | Budget owner | Procurement | Introduction
    email: Mapped[str | None] = mapped_column(String(200))
    owner: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    account: Mapped[Account] = relationship(back_populates="contacts")


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))  # Call | Meeting | Email | Task | Note
    date: Mapped[date] = mapped_column(Date, default=date.today)
    owner: Mapped[str | None] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    due: Mapped[date | None] = mapped_column(Date)
    account: Mapped[Account] = relationship(back_populates="activities")


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    role: Mapped[str | None] = mapped_column(String(80))  # RadixArk product | LF project | Ecosystem project
    origin: Mapped[str] = mapped_column(String(32), default="Researched")
    category: Mapped[str | None] = mapped_column(String(200))
    homepage: Mapped[str | None] = mapped_column(String(300))
    repo_url: Mapped[str | None] = mapped_column(String(300))
    github_org: Mapped[str | None] = mapped_column(String(120))
    hosting: Mapped[str | None] = mapped_column(String(40))  # graduated | incubating | sandbox
    account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"))  # backing organization when known
    stars: Mapped[int | None] = mapped_column(Integer)
    last_release: Mapped[date | None] = mapped_column(Date)


class ModelRecord(Base):
    __tablename__ = "models"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)  # HF model id, e.g. deepseek-ai/DeepSeek-V3
    publisher_account_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), index=True)
    hf_org: Mapped[str] = mapped_column(String(120), index=True)
    family: Mapped[str | None] = mapped_column(String(120))
    modality: Mapped[str | None] = mapped_column(String(60))
    downloads_30d: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    created: Mapped[date | None] = mapped_column(Date)
    providers: Mapped[str | None] = mapped_column(Text)  # comma-separated HF inference providers
    sglang_supported: Mapped[bool | None] = mapped_column(Boolean)
    snapshot_date: Mapped[date | None] = mapped_column(Date)


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))   # seed | lfai | mad | huggingface | github
    snapshot_file: Mapped[str | None] = mapped_column(String(300))
    snapshot_date: Mapped[date] = mapped_column(Date)
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    added: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    needs_review: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    log: Mapped[str | None] = mapped_column(Text)


class ImportChange(Base):
    __tablename__ = "import_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # added | matched | review | removed
    entity: Mapped[str] = mapped_column(String(20))  # account | project
    entity_id: Mapped[str | None] = mapped_column(String(40))
    source_name: Mapped[str] = mapped_column(String(200))
    candidate_id: Mapped[str | None] = mapped_column(String(40))  # for review: the account it may match
    detail: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class Metric(Base):
    """One measured signal for an account from one snapshot. Ranks are computed from these."""
    __tablename__ = "metrics"
    __table_args__ = (UniqueConstraint("account_id", "metric", "snapshot_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    metric: Mapped[str] = mapped_column(String(60), index=True)  # scale.hf_downloads_30d, prox.contributors, …
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)


class Rank(Base):
    __tablename__ = "ranks"
    __table_args__ = (UniqueConstraint("account_id", "kind", "rubric_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # scale | proximity
    rubric_version: Mapped[str] = mapped_column(String(8))
    rank: Mapped[int] = mapped_column(Integer)
    of: Mapped[int] = mapped_column(Integer)      # accounts ranked in the segment
    score: Mapped[float] = mapped_column(Float)   # 0..1 percentile mean (scale) or 0..4 families (proximity)
    inputs: Mapped[str | None] = mapped_column(Text)  # JSON of metric -> value used
    missing: Mapped[str | None] = mapped_column(Text)
    snapshot_date: Mapped[date] = mapped_column(Date)
