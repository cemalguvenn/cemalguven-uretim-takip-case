"""Day×shift aggregation and submission of validated data to the target API.

Only countable records (clean/warning/corrected, not hidden) are aggregated, so
rejected/hidden/error data never reaches the target system. Idempotency is
enforced via sync_logs UNIQUE(production_date, shift): a successfully submitted
day/shift is not re-sent unless the caller passes force=True.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import ProductionRecord, SyncLog
from services.report_service import COUNTABLE_STATUSES, _weighted_oee

settings = get_settings()


@dataclass
class Aggregation:
    payload: dict
    record_ids: list[int]
    record_count: int


# --------------------------------------------------------------------------- #
# HTTP client (retry + backoff) — mock vs real is pure .env config
# --------------------------------------------------------------------------- #
class ProductionApiClient:
    def __init__(self) -> None:
        self.base_url = settings.api_base_url.rstrip("/")
        self.key = settings.api_key

    async def submit(self, payload: dict) -> tuple[int | None, dict | str | None, str | None]:
        """POST one day/shift. Returns (status_code, body, error_message).

        Retries: 429 → wait Retry-After (capped); 5xx/network → exponential
        backoff 2/4/8s, max 3 attempts. 401/422/413 are not retried.
        """
        url = f"{self.base_url}/api/v1/submit"
        headers = {"X-Production-Key": self.key, "Content-Type": "application/json"}
        max_attempts = 3
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt == max_attempts:
                        return None, None, f"Bağlantı hatası: {exc}"
                    await asyncio.sleep(2 ** attempt)
                    continue

                if resp.status_code == 429 and attempt < max_attempts:
                    wait = int(resp.headers.get("Retry-After", 5))
                    await asyncio.sleep(min(wait, 60))
                    continue
                if resp.status_code >= 500 and attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)
                    continue

                try:
                    body = resp.json()
                except ValueError:
                    body = resp.text
                return resp.status_code, body, None
        return None, None, "Gönderim başarısız."


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
async def _countable_for(session: AsyncSession, day: date, shift: int) -> list[ProductionRecord]:
    return list((await session.scalars(
        select(ProductionRecord).where(
            ProductionRecord.status.in_(COUNTABLE_STATUSES),
            ProductionRecord.is_hidden.is_(False),
            ProductionRecord.tarih == day,
            ProductionRecord.vardiya == shift,
        )
    )).all())


def aggregate_records(records: list[ProductionRecord], day: date, shift: int) -> Aggregation | None:
    """Build the API payload for one day/shift, or None if nothing to send."""
    if not records:
        return None
    total_units = sum(r.uretilen_miktar or 0 for r in records)
    if total_units <= 0:
        return None  # API requires total_production_units >= 1
    stations = {r.is_istasyon_adi for r in records if r.is_istasyon_adi}
    machine_count = min(max(len(stations), 1), 1000)
    oee = _weighted_oee(records)
    oe_value = round(min(max(oee or 0.0, 0.0), 100.0), 2)
    payload = {
        "oe_value": oe_value,
        "machine_count": machine_count,
        "shift": shift,
        "total_production_units": int(total_units),
        "production_date": day.isoformat(),
    }
    return Aggregation(payload=payload, record_ids=[r.id for r in records], record_count=len(records))


async def preview(session: AsyncSession, day: date, shift: int) -> dict:
    records = await _countable_for(session, day, shift)
    agg = aggregate_records(records, day, shift)
    if agg is None:
        reason = "Gönderilebilir temiz üretim verisi yok." if not records \
            else "Toplam üretim 0 — gönderim atlanır."
        return {"payload": None, "record_count": len(records), "skip_reason": reason}
    return {"payload": agg.payload, "record_count": agg.record_count, "skip_reason": None}


# --------------------------------------------------------------------------- #
# Matrix / history
# --------------------------------------------------------------------------- #
async def pending_matrix(session: AsyncSession) -> list[dict]:
    """One cell per (date, shift) that has countable records, plus sync status."""
    records = list((await session.scalars(
        select(ProductionRecord).where(
            ProductionRecord.status.in_(COUNTABLE_STATUSES),
            ProductionRecord.is_hidden.is_(False),
        )
    )).all())
    groups: dict[tuple[date, int], list[ProductionRecord]] = {}
    for r in records:
        if r.tarih is not None and r.vardiya in (1, 2, 3):
            groups.setdefault((r.tarih, r.vardiya), []).append(r)

    logs = {(l.production_date, l.shift): l for l in (await session.scalars(select(SyncLog))).all()}

    cells = []
    for (day, shift), recs in sorted(groups.items()):
        agg = aggregate_records(recs, day, shift)
        log = logs.get((day, shift))
        sync_status = "none"
        if log:
            sync_status = "success" if log.status == "success" else log.status
        cells.append({
            "production_date": day,
            "shift": shift,
            "clean_count": len(recs),
            "oe_value": agg.payload["oe_value"] if agg else None,
            "machine_count": agg.payload["machine_count"] if agg else 0,
            "total_production_units": agg.payload["total_production_units"] if agg else 0,
            "sync_status": "skipped" if agg is None and sync_status == "none" else sync_status,
            "submission_id": log.submission_id if log else None,
            "skip_reason": None if agg else "Üretim 0",
        })
    return cells


async def history(session: AsyncSession) -> list[SyncLog]:
    return list((await session.scalars(
        select(SyncLog).order_by(SyncLog.last_attempt_at.desc().nullslast(), SyncLog.id.desc())
    )).all())


# --------------------------------------------------------------------------- #
# Submit
# --------------------------------------------------------------------------- #
async def submit(session: AsyncSession, day: date, shift: int, force: bool = False) -> dict:
    existing = await session.scalar(
        select(SyncLog).where(SyncLog.production_date == day, SyncLog.shift == shift)
    )
    if existing and existing.status == "success" and not force:
        return {
            "status": "duplicate",
            "message": f"Bu gün/vardiya zaten gönderildi (submission #{existing.submission_id}). "
                       f"Yeniden göndermek için 'force' kullanın.",
            "submission_id": existing.submission_id,
            "response_status": existing.response_status,
        }

    records = await _countable_for(session, day, shift)
    agg = aggregate_records(records, day, shift)
    if agg is None:
        return {"status": "skipped",
                "message": "Gönderilecek geçerli üretim verisi yok (kayıt yok veya toplam üretim 0).",
                "submission_id": None, "response_status": None}

    status_code, body, err = await ProductionApiClient().submit(agg.payload)

    log = existing or SyncLog(production_date=day, shift=shift)
    log.oe_value = agg.payload["oe_value"]
    log.machine_count = agg.payload["machine_count"]
    log.total_production = agg.payload["total_production_units"]
    log.request_body = json.dumps(agg.payload, ensure_ascii=False)
    log.response_status = status_code
    log.response_body = json.dumps(body, ensure_ascii=False) if body is not None else None
    log.attempt_count = (log.attempt_count or 0) + 1
    log.last_attempt_at = datetime.now()
    log.error_message = err

    if status_code == 200 and isinstance(body, dict) and body.get("success"):
        log.status = "success"
        log.submission_id = body.get("submission_id")
        # mark the contributing records as submitted
        for rec in records:
            if rec.status != "rejected":
                rec.status = "submitted"
        result = {"status": "success", "message": body.get("message", "Gönderildi."),
                  "submission_id": log.submission_id, "response_status": 200}
    else:
        log.status = "failed"
        detail = err or (body.get("detail") if isinstance(body, dict) else body)
        result = {"status": "failed", "message": f"Gönderim başarısız: {detail}",
                  "submission_id": None, "response_status": status_code}

    if existing is None:
        session.add(log)
    await session.commit()
    return result
