"""Record endpoints: filtered listing, detail, correction, status workflow."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import (
    AuditLogOut,
    BatchAction,
    PaginatedRecords,
    RecordOut,
    RecordUpdate,
    StatusAction,
    ValidationErrorOut,
)
from services import record_service

router = APIRouter(prefix="/api/records", tags=["records"])

_ALLOWED_ACTIONS = {"reject", "hide", "unhide", "restore"}


@router.get("", response_model=PaginatedRecords)
async def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    tarih_start: date | None = None,
    tarih_end: date | None = None,
    vardiya: list[int] | None = Query(None),
    istasyon: list[str] | None = Query(None),
    stok: str | None = None,
    oee_min: float | None = None,
    oee_max: float | None = None,
    status: list[str] | None = Query(None),
    only_problematic: bool = False,
    hide_errors: bool = False,
    include_hidden: bool = False,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    items, total = await record_service.list_records(
        session, page=page, page_size=page_size, tarih_start=tarih_start,
        tarih_end=tarih_end, vardiya=vardiya, istasyon=istasyon, stok=stok,
        oee_min=oee_min, oee_max=oee_max, statuses=status,
        only_problematic=only_problematic, hide_errors=hide_errors,
        include_hidden=include_hidden, search=search,
    )
    return PaginatedRecords(items=items, total=total, page=page, page_size=page_size)


@router.post("/batch-action")
async def batch_action(payload: BatchAction, session: AsyncSession = Depends(get_session)):
    if payload.action not in _ALLOWED_ACTIONS:
        raise HTTPException(status_code=422, detail=f"Geçersiz aksiyon: {payload.action}")
    affected = await record_service.batch_action(
        session, payload.ids, payload.action, payload.reason
    )
    return {"affected": affected, "action": payload.action}


@router.get("/{record_pk}", response_model=RecordOut)
async def get_record(record_pk: int, session: AsyncSession = Depends(get_session)):
    rec = await record_service.get_record(session, record_pk)
    if rec is None:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    out = RecordOut.model_validate(rec)
    await record_service._attach_error_counts(session, [rec], [out])
    return out


@router.get("/{record_pk}/errors", response_model=list[ValidationErrorOut])
async def record_errors(record_pk: int, session: AsyncSession = Depends(get_session)):
    return await record_service.get_record_errors(session, record_pk)


@router.get("/{record_pk}/audit-log", response_model=list[AuditLogOut])
async def record_audit(record_pk: int, session: AsyncSession = Depends(get_session)):
    return await record_service.get_audit_log(session, record_pk)


@router.put("/{record_pk}", response_model=RecordOut)
async def update_record(record_pk: int, payload: RecordUpdate,
                        session: AsyncSession = Depends(get_session)):
    changes = payload.model_dump(exclude_unset=True, exclude={"reason"})
    rec = await record_service.update_record(session, record_pk, changes, payload.reason)
    if rec is None:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    out = RecordOut.model_validate(rec)
    await record_service._attach_error_counts(session, [rec], [out])
    return out


@router.patch("/{record_pk}/status", response_model=RecordOut)
async def change_status(record_pk: int, payload: StatusAction,
                        session: AsyncSession = Depends(get_session)):
    if payload.action not in _ALLOWED_ACTIONS:
        raise HTTPException(status_code=422, detail=f"Geçersiz aksiyon: {payload.action}")
    rec = await record_service.set_status(session, record_pk, payload.action, payload.reason)
    if rec is None:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")
    return RecordOut.model_validate(rec)
