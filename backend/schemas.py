"""Pydantic request/response schemas for the API layer."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_id: int
    csv_row_number: int | None
    import_batch_id: int
    tarih: date | None
    is_emri_no: str | None
    is_merkezi_no: str | None
    is_merkezi_adi: str | None
    is_istasyon_adi: str | None
    stok_adi: str | None
    vardiya: int | None
    availability: float | None
    performance: float | None
    quality: float | None
    oee: float | None
    calisma_suresi: float | None
    durus_suresi: float | None
    planli_durus: float | None
    plansiz_durus: float | None
    uretilen_miktar: int | None
    hatali_uretilen: int | None
    status: str
    is_hidden: bool
    error_count: int = 0
    warning_count: int = 0


class PaginatedRecords(BaseModel):
    items: list[RecordOut]
    total: int
    page: int
    page_size: int


class RecordUpdate(BaseModel):
    """Correction payload — only provided fields are changed (exclude_unset)."""
    tarih: date | None = None
    is_emri_no: str | None = None
    is_merkezi_no: str | None = None
    is_merkezi_adi: str | None = None
    is_istasyon_adi: str | None = None
    stok_adi: str | None = None
    vardiya: int | None = None
    availability: float | None = None
    performance: float | None = None
    quality: float | None = None
    oee: float | None = None
    calisma_suresi: float | None = None
    durus_suresi: float | None = None
    planli_durus: float | None = None
    plansiz_durus: float | None = None
    uretilen_miktar: int | None = None
    hatali_uretilen: int | None = None
    reason: str | None = None


class StatusAction(BaseModel):
    action: str = Field(description="reject | hide | unhide | restore")
    reason: str | None = None


class BatchAction(BaseModel):
    ids: list[int]
    action: str = Field(description="reject | hide | unhide | restore")
    reason: str | None = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_name: str | None
    old_value: str | None
    new_value: str | None
    action: str
    reason: str | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    total_rows: int | None
    processed_rows: int
    clean_rows: int | None
    warning_rows: int | None
    error_rows: int | None
    status: str
    phase: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
class ValidationErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    record_id: int
    rule_code: str
    severity: str
    category: str
    field_name: str | None
    message: str
    expected_value: str | None
    actual_value: str | None
    suggested_action: str | None
    is_resolved: bool


class PaginatedErrors(BaseModel):
    items: list[ValidationErrorOut]
    total: int
    page: int
    page_size: int


class KeyCount(BaseModel):
    key: str
    count: int


class ValidationSummaryOut(BaseModel):
    total: int
    by_severity: list[KeyCount]
    by_category: list[KeyCount]
    by_rule: list[KeyCount]


# --------------------------------------------------------------------------- #
# Reports / dashboard
# --------------------------------------------------------------------------- #
class SummaryOut(BaseModel):
    avg_oee: float | None
    total_production: int
    total_defect: int
    total_stop_minutes: float
    defect_rate: float | None
    countable_records: int
    status_counts: dict[str, int]


class TrendPoint(BaseModel):
    tarih: date
    avg_oee: float | None
    production: int


class ShiftStat(BaseModel):
    vardiya: int
    avg_oee: float | None
    production: int
    record_count: int


class StationStat(BaseModel):
    istasyon: str
    avg_oee: float | None
    production: int
    record_count: int


class QualityDistOut(BaseModel):
    total_good: int
    total_defect: int
    defect_rate: float | None


class StationLoss(BaseModel):
    istasyon: str
    availability: float
    performance: float
    quality: float
    oee: float
    availability_loss: float
    performance_loss: float
    quality_loss: float


class LossAnalysisOut(BaseModel):
    availability: float
    performance: float
    quality: float
    oee: float
    availability_loss: float
    performance_loss: float
    quality_loss: float
    planned_stop_min: float
    unplanned_stop_min: float
    run_min: float
    stations: list[StationLoss]


# --------------------------------------------------------------------------- #
# Validation rules (settings)
# --------------------------------------------------------------------------- #
class ValidationRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule_code: str
    display_name: str
    description: str | None
    category: str
    default_severity: str
    is_active: bool
    warning_threshold: float | None
    error_threshold: float | None


class ValidationRuleUpdate(BaseModel):
    is_active: bool | None = None
    default_severity: str | None = None
    warning_threshold: float | None = None
    error_threshold: float | None = None


# --------------------------------------------------------------------------- #
# API sync
# --------------------------------------------------------------------------- #
class SubmitPayload(BaseModel):
    """Exact body sent to the target API (per the case-study contract)."""
    oe_value: float
    machine_count: int
    shift: int
    total_production_units: int
    production_date: str


class SyncCell(BaseModel):
    production_date: date
    shift: int
    clean_count: int
    oe_value: float | None
    machine_count: int
    total_production_units: int
    sync_status: str  # none | success | failed | skipped
    submission_id: int | None = None
    skip_reason: str | None = None


class SyncPreview(BaseModel):
    payload: SubmitPayload | None
    record_count: int
    skip_reason: str | None = None


class SyncSubmitRequest(BaseModel):
    production_date: date
    shift: int
    force: bool = False


class AutoSyncConfig(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=60, ge=1, le=1440)


class SyncResultOut(BaseModel):
    status: str  # success | failed | skipped | duplicate
    message: str
    submission_id: int | None = None
    response_status: int | None = None


class AlertOut(BaseModel):
    key: str
    severity: str  # error | warning | info
    title: str
    detail: str | None = None
    link: str | None = None


class SyncLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    production_date: date
    shift: int
    oe_value: float | None
    machine_count: int | None
    total_production: int | None
    response_status: int | None
    submission_id: int | None
    status: str
    attempt_count: int
    last_attempt_at: datetime | None
    error_message: str | None
    created_at: datetime
