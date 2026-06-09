"""In-app alert center — operational signals aggregated live (no extra table)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import ImportBatch, SyncLog, ValidationError
from schemas import AlertOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

HIGH_ERROR_RATE = 0.30  # batches over this error fraction raise a warning


@router.get("", response_model=list[AlertOut])
async def list_alerts(session: AsyncSession = Depends(get_session)):
    alerts: list[AlertOut] = []

    # 1) Failed submissions
    for log in (await session.scalars(
        select(SyncLog).where(SyncLog.status == "failed")
        .order_by(SyncLog.last_attempt_at.desc())
    )).all():
        alerts.append(AlertOut(
            key=f"sync-{log.id}", severity="error",
            title=f"Gönderim başarısız: {log.production_date} V{log.shift}",
            detail=log.error_message or f"HTTP {log.response_status}", link="/sync",
        ))

    # 2) High-error-rate import batches
    for b in (await session.scalars(select(ImportBatch))).all():
        if b.total_rows and b.error_rows and b.error_rows / b.total_rows > HIGH_ERROR_RATE:
            rate = round(b.error_rows / b.total_rows * 100)
            alerts.append(AlertOut(
                key=f"batch-{b.id}", severity="warning",
                title=f"Yüksek hata oranı: {b.filename}",
                detail=f"%{rate} kayıt hatalı ({b.error_rows}/{b.total_rows})", link="/validation",
            ))

    # 3) Systematic anomaly present
    sys_count = await session.scalar(
        select(func.count(func.distinct(ValidationError.record_id)))
        .where(ValidationError.rule_code == "SYSTEMATIC_HIGH_P")
    )
    if sys_count:
        alerts.append(AlertOut(
            key="systematic", severity="warning",
            title="Sistemik anomali tespit edildi",
            detail=f"{sys_count} kayıt: ürün/istasyon bazlı sistemik yüksek P", link="/validation",
        ))

    return alerts
