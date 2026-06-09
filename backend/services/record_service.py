"""Record CRUD, filtering, correction, and status workflow.

Status transitions (see PLAN state machine):
    pending → clean|warning|error            (validation)
    error   → corrected                       (user edits + re-validate)
    *       → rejected                         (user rejects; excluded everywhere)
    rejected→ pending → clean|warning|error    (user restores + re-validate)
`is_hidden` is independent of status. Every mutation is recorded in audit_logs.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, ProductionRecord, ValidationError
from schemas import RecordOut
from validation.engine import revalidate_record

_EDITABLE_FIELDS = {
    "tarih", "is_emri_no", "is_merkezi_no", "is_merkezi_adi", "is_istasyon_adi",
    "stok_adi", "vardiya", "availability", "performance", "quality", "oee",
    "calisma_suresi", "durus_suresi", "planli_durus", "plansiz_durus",
    "uretilen_miktar", "hatali_uretilen",
}


def _apply_filters(stmt, *, tarih_start, tarih_end, vardiya, istasyon, stok,
                   oee_min, oee_max, statuses, only_problematic, hide_errors,
                   include_hidden, search):
    R = ProductionRecord
    if tarih_start is not None:
        stmt = stmt.where(R.tarih >= tarih_start)
    if tarih_end is not None:
        stmt = stmt.where(R.tarih <= tarih_end)
    if vardiya:
        stmt = stmt.where(R.vardiya.in_(vardiya))
    if istasyon:
        stmt = stmt.where(R.is_istasyon_adi.in_(istasyon))
    if stok:
        stmt = stmt.where(R.stok_adi.ilike(f"%{stok}%"))
    if oee_min is not None:
        stmt = stmt.where(R.oee >= oee_min)
    if oee_max is not None:
        stmt = stmt.where(R.oee <= oee_max)
    if statuses:
        stmt = stmt.where(R.status.in_(statuses))
    if only_problematic:
        stmt = stmt.where(R.status.in_(("warning", "error")))
    if hide_errors:
        stmt = stmt.where(R.status != "error")
    if not include_hidden:
        stmt = stmt.where(R.is_hidden.is_(False))
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            R.stok_adi.ilike(like) | R.is_emri_no.ilike(like) | R.is_istasyon_adi.ilike(like)
        )
    return stmt


async def list_records(session: AsyncSession, *, page=1, page_size=50, tarih_start=None,
                       tarih_end=None, vardiya=None, istasyon=None, stok=None,
                       oee_min=None, oee_max=None, statuses=None, only_problematic=False,
                       hide_errors=False, include_hidden=False, search=None) -> tuple[list[RecordOut], int]:
    flt = dict(tarih_start=tarih_start, tarih_end=tarih_end, vardiya=vardiya,
               istasyon=istasyon, stok=stok, oee_min=oee_min, oee_max=oee_max,
               statuses=statuses, only_problematic=only_problematic,
               hide_errors=hide_errors, include_hidden=include_hidden, search=search)

    total = await session.scalar(
        _apply_filters(select(func.count()).select_from(ProductionRecord), **flt)
    )
    stmt = _apply_filters(select(ProductionRecord), **flt)
    stmt = stmt.order_by(ProductionRecord.record_id).offset((page - 1) * page_size).limit(page_size)
    records = (await session.scalars(stmt)).all()

    out = [RecordOut.model_validate(r) for r in records]
    await _attach_error_counts(session, records, out)
    return out, int(total or 0)


async def _attach_error_counts(session, records, out):
    ids = [r.id for r in records]
    if not ids:
        return
    rows = await session.execute(
        select(ValidationError.record_id, ValidationError.severity)
        .where(ValidationError.record_id.in_(ids))
    )
    counts: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # [error, warning]
    for rid, severity in rows:
        if severity == "error":
            counts[rid][0] += 1
        elif severity == "warning":
            counts[rid][1] += 1
    by_id = {o.id: o for o in out}
    for rid, (errs, warns) in counts.items():
        if rid in by_id:
            by_id[rid].error_count = errs
            by_id[rid].warning_count = warns


async def get_record(session: AsyncSession, record_pk: int) -> ProductionRecord | None:
    return await session.get(ProductionRecord, record_pk)


async def get_record_errors(session: AsyncSession, record_pk: int) -> list[ValidationError]:
    return list((await session.scalars(
        select(ValidationError).where(ValidationError.record_id == record_pk)
        .order_by(ValidationError.severity.desc())
    )).all())


async def get_audit_log(session: AsyncSession, record_pk: int) -> list[AuditLog]:
    return list((await session.scalars(
        select(AuditLog).where(AuditLog.record_id == record_pk)
        .order_by(AuditLog.created_at.desc())
    )).all())


async def update_record(session: AsyncSession, record_pk: int, changes: dict,
                        reason: str | None = None) -> ProductionRecord | None:
    rec = await session.get(ProductionRecord, record_pk)
    if rec is None:
        return None
    for field, new_val in changes.items():
        if field not in _EDITABLE_FIELDS:
            continue
        old_val = getattr(rec, field)
        if old_val == new_val:
            continue
        setattr(rec, field, new_val)
        session.add(AuditLog(
            record_id=rec.id, field_name=field,
            old_value=None if old_val is None else str(old_val),
            new_value=None if new_val is None else str(new_val),
            action="edit", reason=reason,
        ))
    await session.flush()
    await revalidate_record(session, rec, mark_corrected=True)
    return rec


def _apply_status_action(rec: ProductionRecord, action: str) -> None:
    if action == "reject":
        rec.status = "rejected"
    elif action == "restore":
        rec.status = "pending"
    elif action == "hide":
        rec.is_hidden = True
    elif action == "unhide":
        rec.is_hidden = False
    else:
        raise ValueError(f"Unknown action: {action}")
    # updated_at is refreshed automatically by the column's onupdate=func.now()


async def set_status(session: AsyncSession, record_pk: int, action: str,
                     reason: str | None = None) -> ProductionRecord | None:
    rec = await session.get(ProductionRecord, record_pk)
    if rec is None:
        return None
    _apply_status_action(rec, action)
    session.add(AuditLog(record_id=rec.id, field_name="status", action=action, reason=reason))
    await session.flush()
    if action == "restore":
        await revalidate_record(session, rec)  # recompute clean/warning/error
    else:
        await session.commit()
    return rec


async def batch_action(session: AsyncSession, ids: list[int], action: str,
                       reason: str | None = None) -> int:
    records = (await session.scalars(
        select(ProductionRecord).where(ProductionRecord.id.in_(ids))
    )).all()
    for rec in records:
        _apply_status_action(rec, action)
        session.add(AuditLog(record_id=rec.id, field_name="status", action=action, reason=reason))
    await session.flush()
    if action == "restore":
        for rec in records:
            await revalidate_record(session, rec)
    else:
        await session.commit()
    return len(records)
