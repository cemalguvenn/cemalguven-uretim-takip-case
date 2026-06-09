"""API sync endpoints: day×shift matrix, preview, submit, history."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import (
    AutoSyncConfig,
    SyncCell,
    SyncLogOut,
    SyncPreview,
    SyncResultOut,
    SyncSubmitRequest,
)
from services import scheduler, sync_service

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/pending", response_model=list[SyncCell])
async def pending(session: AsyncSession = Depends(get_session)):
    return await sync_service.pending_matrix(session)


@router.get("/preview", response_model=SyncPreview)
async def preview(production_date: date, shift: int = Query(ge=1, le=3),
                  session: AsyncSession = Depends(get_session)):
    return await sync_service.preview(session, production_date, shift)


@router.post("/submit", response_model=SyncResultOut)
async def submit(payload: SyncSubmitRequest, session: AsyncSession = Depends(get_session)):
    return await sync_service.submit(session, payload.production_date, payload.shift, payload.force)


@router.get("/history", response_model=list[SyncLogOut])
async def history(session: AsyncSession = Depends(get_session)):
    return await sync_service.history(session)


@router.get("/auto-sync", response_model=AutoSyncConfig)
async def get_auto_sync(session: AsyncSession = Depends(get_session)):
    return await scheduler.get_config(session)


@router.put("/auto-sync", response_model=AutoSyncConfig)
async def set_auto_sync(cfg: AutoSyncConfig, session: AsyncSession = Depends(get_session)):
    return await scheduler.set_config(session, cfg.enabled, cfg.interval_minutes)


@router.post("/run-now", response_model=SyncResultOut)
async def run_now(session: AsyncSession = Depends(get_session)):
    r = await sync_service.submit_all_ready(session)
    return SyncResultOut(
        status="success",
        message=f"{r['submitted']} gönderildi · {r['failed']} hata · {r['skipped']} atlandı",
    )
