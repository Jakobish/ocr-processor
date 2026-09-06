"""Additive enterprise schema and short-lived transactions."""
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Integer, DateTime, Text, JSON, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator


def uid():
    return str(uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = 'ent_tenants'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    retention_days: Mapped[int] = mapped_column(default=30)
    max_concurrent_jobs: Mapped[int] = mapped_column(default=1)


class Upload(Base):
    __tablename__ = 'ent_uploads'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('ent_tenants.id'), index=True)
    owner_id: Mapped[str] = mapped_column(String(128))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Batch(Base):
    __tablename__ = 'ent_batches'
    __table_args__ = (UniqueConstraint('tenant_id', 'owner_id', 'idempotency_key'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('ent_tenants.id'), index=True)
    owner_id: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Job(Base):
    __tablename__ = 'ent_jobs'
    __table_args__ = (Index('ent_jobs_claim_idx', 'status', 'available_at', 'created_at'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('ent_tenants.id'), index=True)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey('ent_batches.id'), index=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey('ent_uploads.id'), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(12))
    language: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default='queued')
    stage: Mapped[str] = mapped_column(String(24), default='queued')
    attempt_count: Mapped[int] = mapped_column(default=0)
    cycle_attempts: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    artifacts: Mapped[dict] = mapped_column(JSON, default=dict)


class Attempt(Base):
    __tablename__ = 'ent_attempts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('ent_jobs.id'), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('ent_tenants.id'))
    lease_token: Mapped[str] = mapped_column(String(36), unique=True)
    worker_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default='running')
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Event(Base):
    __tablename__ = 'ent_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('ent_tenants.id'), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey('ent_jobs.id'), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class APIKey(Base):
    __tablename__ = 'ent_api_keys'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('ent_tenants.id'), index=True)
    owner_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Database:
    def __init__(self, url):
        options = {'pool_pre_ping': True}
        if url.startswith('sqlite:'):
            options['connect_args'] = {'check_same_thread': False}
        self.engine = create_engine(url, **options)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        with self.factory() as session:
            with session.begin():
                yield session

    def serialize(self, session):
        # Serializes only scheduling/submission transactions, never OCR execution.
        # This lock makes global/team concurrency limits atomic across API/workers.
        if self.engine.dialect.name == 'postgresql':
            session.execute(text('SELECT pg_advisory_xact_lock(172903811)'))
