"""SQLAlchemy 2.0 ORM models — 6 tables.

Design notes:
- `production_records.original_data` stores the untouched CSV row as JSON (data
  lineage), so corrections never destroy the source of truth.
- `validation_rules` holds thresholds/severity/active flags so the validation
  engine reads configuration at runtime (no hardcoded thresholds) and the
  Settings UI is just CRUD over this table.
- `sync_logs` has UNIQUE(production_date, shift) to enforce idempotency: a given
  day/shift is submitted once unless the user explicitly re-sends.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductionRecord(Base):
    __tablename__ = "production_records"
    __table_args__ = (UniqueConstraint("record_id", "import_batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    csv_row_number: Mapped[int | None] = mapped_column(Integer)
    import_batch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Immutable original CSV row (JSON string) — data lineage
    original_data: Mapped[str] = mapped_column(Text, nullable=False)

    # Workable fields
    tarih: Mapped[date | None] = mapped_column(Date, index=True)
    is_emri_no: Mapped[str | None] = mapped_column(String)
    is_merkezi_no: Mapped[str | None] = mapped_column(String)
    is_merkezi_adi: Mapped[str | None] = mapped_column(String)
    is_istasyon_adi: Mapped[str | None] = mapped_column(String, index=True)
    stok_adi: Mapped[str | None] = mapped_column(String)
    vardiya: Mapped[int | None] = mapped_column(Integer, index=True)

    availability: Mapped[float | None] = mapped_column(Float)
    performance: Mapped[float | None] = mapped_column(Float)
    quality: Mapped[float | None] = mapped_column(Float)
    oee: Mapped[float | None] = mapped_column(Float)

    calisma_suresi: Mapped[float | None] = mapped_column(Float)
    durus_suresi: Mapped[float | None] = mapped_column(Float)
    planli_durus: Mapped[float | None] = mapped_column(Float)
    plansiz_durus: Mapped[float | None] = mapped_column(Float)

    uretilen_miktar: Mapped[int | None] = mapped_column(Integer)
    hatali_uretilen: Mapped[int | None] = mapped_column(Integer)

    # State management
    # pending | clean | warning | error | corrected | rejected | submitted
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ValidationError(Base):
    __tablename__ = "validation_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("production_records.id"), nullable=False, index=True
    )
    import_batch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    rule_code: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)  # error | warning | info
    category: Mapped[str] = mapped_column(String, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str | None] = mapped_column(String)
    actual_value: Mapped[str | None] = mapped_column(String)
    suggested_action: Mapped[str | None] = mapped_column(String)  # reject | warn | fix

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ValidationRule(Base):
    __tablename__ = "validation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String, nullable=False)
    default_severity: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    warning_threshold: Mapped[float | None] = mapped_column(Float)
    error_threshold: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(
        ForeignKey("production_records.id"), nullable=False, index=True
    )
    field_name: Mapped[str | None] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String, nullable=False)  # edit|reject|restore|hide|unhide
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)  # SHA-256 dedupe
    total_rows: Mapped[int | None] = mapped_column(Integer)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    clean_rows: Mapped[int | None] = mapped_column(Integer)
    warning_rows: Mapped[int | None] = mapped_column(Integer)
    error_rows: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="processing")
    phase: Mapped[str | None] = mapped_column(String)  # importing | validating | done | failed
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AppSetting(Base):
    """Tiny key/value store for runtime config (e.g. auto-sync schedule)."""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)


class SyncLog(Base):
    __tablename__ = "sync_logs"
    __table_args__ = (UniqueConstraint("production_date", "shift"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    production_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift: Mapped[int] = mapped_column(Integer, nullable=False)

    oe_value: Mapped[float | None] = mapped_column(Float)
    machine_count: Mapped[int | None] = mapped_column(Integer)
    total_production: Mapped[int | None] = mapped_column(Integer)

    request_body: Mapped[str | None] = mapped_column(Text)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    submission_id: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
