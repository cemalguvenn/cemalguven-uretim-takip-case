"""Dashboard/report endpoints. All accept an optional date range (start/end)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import (
    LossAnalysisOut,
    QualityDistOut,
    ShiftStat,
    StationStat,
    SummaryOut,
    TrendPoint,
)
from services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/summary", response_model=SummaryOut)
async def summary(start: date | None = None, end: date | None = None,
                  session: AsyncSession = Depends(get_session)):
    return await report_service.summary(session, start, end)


@router.get("/oee-trend", response_model=list[TrendPoint])
async def oee_trend(start: date | None = None, end: date | None = None,
                    session: AsyncSession = Depends(get_session)):
    return await report_service.oee_trend(session, start, end)


@router.get("/shift-comparison", response_model=list[ShiftStat])
async def shift_comparison(start: date | None = None, end: date | None = None,
                           session: AsyncSession = Depends(get_session)):
    return await report_service.shift_comparison(session, start, end)


@router.get("/station-ranking", response_model=list[StationStat])
async def station_ranking(start: date | None = None, end: date | None = None,
                          session: AsyncSession = Depends(get_session)):
    return await report_service.station_ranking(session, start, end)


@router.get("/quality-distribution", response_model=QualityDistOut)
async def quality_distribution(start: date | None = None, end: date | None = None,
                               session: AsyncSession = Depends(get_session)):
    return await report_service.quality_distribution(session, start, end)


@router.get("/loss-analysis", response_model=LossAnalysisOut)
async def loss_analysis(start: date | None = None, end: date | None = None,
                        session: AsyncSession = Depends(get_session)):
    return await report_service.loss_analysis(session, start, end)
