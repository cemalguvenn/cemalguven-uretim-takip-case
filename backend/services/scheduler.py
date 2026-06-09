"""Opt-in scheduled auto-submission of validated data ("after each shift").

A single APScheduler interval job calls sync_service.submit_all_ready, which is
idempotent (sync_logs UNIQUE(date,shift)), so repeated runs never duplicate.
Config (enabled + interval) is persisted in the app_settings table and editable
from the Sync page; default is OFF so nothing is submitted without consent.
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AppSetting

_scheduler = AsyncIOScheduler()
_JOB_ID = "auto_sync"
_DEFAULTS = {"auto_sync_enabled": "false", "auto_sync_interval_minutes": "60"}


async def _run_job() -> None:
    from database import SessionLocal
    from services import sync_service

    async with SessionLocal() as session:
        await sync_service.submit_all_ready(session)


async def get_config(session: AsyncSession) -> dict:
    rows = {s.key: s.value for s in (await session.scalars(select(AppSetting))).all()}
    return {
        "enabled": rows.get("auto_sync_enabled", _DEFAULTS["auto_sync_enabled"]) == "true",
        "interval_minutes": int(rows.get("auto_sync_interval_minutes",
                                         _DEFAULTS["auto_sync_interval_minutes"])),
    }


async def _set(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value


async def set_config(session: AsyncSession, enabled: bool, interval_minutes: int) -> dict:
    interval_minutes = max(1, int(interval_minutes))
    await _set(session, "auto_sync_enabled", "true" if enabled else "false")
    await _set(session, "auto_sync_interval_minutes", str(interval_minutes))
    await session.commit()
    _apply(enabled, interval_minutes)
    return {"enabled": enabled, "interval_minutes": interval_minutes}


def _apply(enabled: bool, interval_minutes: int) -> None:
    """(Re)install or remove the interval job to match the config."""
    if _scheduler.get_job(_JOB_ID):
        _scheduler.remove_job(_JOB_ID)
    if enabled:
        _scheduler.add_job(_run_job, "interval", minutes=interval_minutes,
                           id=_JOB_ID, replace_existing=True)


async def start(session: AsyncSession) -> None:
    if not _scheduler.running:
        _scheduler.start()
    cfg = await get_config(session)
    _apply(cfg["enabled"], cfg["interval_minutes"])


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
