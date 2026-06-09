"""Dashboard aggregations.

Only "countable" records feed the metrics: status in clean/warning/corrected/
submitted AND not hidden. Rejected, hidden, error and pending records are
excluded — this is what keeps bad data out of the reported numbers. OEE is a
duration-weighted average (by Çalışma Süresi), consistent with the API sync.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ProductionRecord
from schemas import QualityDistOut, ShiftStat, StationStat, SummaryOut, TrendPoint

COUNTABLE_STATUSES = ("clean", "warning", "corrected", "submitted")


def _weighted_oee(rows) -> float | None:
    num = sum(r.oee * r.calisma_suresi for r in rows
              if r.oee is not None and r.calisma_suresi)
    den = sum(r.calisma_suresi for r in rows
              if r.oee is not None and r.calisma_suresi)
    return round(num / den, 2) if den else None


async def _fetch_countable(session: AsyncSession, start: date | None, end: date | None):
    stmt = select(ProductionRecord).where(
        ProductionRecord.status.in_(COUNTABLE_STATUSES),
        ProductionRecord.is_hidden.is_(False),
    )
    if start is not None:
        stmt = stmt.where(ProductionRecord.tarih >= start)
    if end is not None:
        stmt = stmt.where(ProductionRecord.tarih <= end)
    return list((await session.scalars(stmt)).all())


async def summary(session: AsyncSession, start=None, end=None) -> SummaryOut:
    rows = await _fetch_countable(session, start, end)
    total_prod = sum(r.uretilen_miktar or 0 for r in rows)
    total_defect = sum(r.hatali_uretilen or 0 for r in rows)
    total_stop = sum(r.durus_suresi or 0 for r in rows)

    # Full status breakdown (across everything, for the UI).
    status_rows = (await session.scalars(select(ProductionRecord.status))).all()
    status_counts: dict[str, int] = defaultdict(int)
    for s in status_rows:
        status_counts[s] += 1
    status_counts["hidden"] = await session.scalar(
        select(func.count()).select_from(ProductionRecord)
        .where(ProductionRecord.is_hidden.is_(True))
    ) or 0

    return SummaryOut(
        avg_oee=_weighted_oee(rows),
        total_production=total_prod,
        total_defect=total_defect,
        total_stop_minutes=round(total_stop, 1),
        defect_rate=round(total_defect / total_prod * 100, 2) if total_prod else None,
        countable_records=len(rows),
        status_counts=dict(status_counts),
    )


async def oee_trend(session: AsyncSession, start=None, end=None) -> list[TrendPoint]:
    rows = await _fetch_countable(session, start, end)
    by_day: dict[date, list] = defaultdict(list)
    for r in rows:
        if r.tarih is not None:
            by_day[r.tarih].append(r)
    return [
        TrendPoint(tarih=d, avg_oee=_weighted_oee(grp),
                   production=sum(x.uretilen_miktar or 0 for x in grp))
        for d, grp in sorted(by_day.items())
    ]


async def shift_comparison(session: AsyncSession, start=None, end=None) -> list[ShiftStat]:
    rows = await _fetch_countable(session, start, end)
    by_shift: dict[int, list] = defaultdict(list)
    for r in rows:
        if r.vardiya in (1, 2, 3):
            by_shift[r.vardiya].append(r)
    return [
        ShiftStat(vardiya=s, avg_oee=_weighted_oee(grp),
                  production=sum(x.uretilen_miktar or 0 for x in grp), record_count=len(grp))
        for s, grp in sorted(by_shift.items())
    ]


async def station_ranking(session: AsyncSession, start=None, end=None) -> list[StationStat]:
    rows = await _fetch_countable(session, start, end)
    by_station: dict[str, list] = defaultdict(list)
    for r in rows:
        if r.is_istasyon_adi:
            by_station[r.is_istasyon_adi].append(r)
    stats = [
        StationStat(istasyon=st, avg_oee=_weighted_oee(grp),
                    production=sum(x.uretilen_miktar or 0 for x in grp), record_count=len(grp))
        for st, grp in by_station.items()
    ]
    return sorted(stats, key=lambda s: (s.avg_oee or -1), reverse=True)


async def quality_distribution(session: AsyncSession, start=None, end=None) -> QualityDistOut:
    rows = await _fetch_countable(session, start, end)
    total_prod = sum(r.uretilen_miktar or 0 for r in rows)
    total_defect = sum(r.hatali_uretilen or 0 for r in rows)
    good = max(total_prod - total_defect, 0)
    return QualityDistOut(
        total_good=good, total_defect=total_defect,
        defect_rate=round(total_defect / total_prod * 100, 2) if total_prod else None,
    )
