"""Validation reporting endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import PaginatedErrors, ValidationSummaryOut
from services import validation_service

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("/summary", response_model=ValidationSummaryOut)
async def validation_summary(
    batch_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    return await validation_service.summary(session, batch_id=batch_id)


@router.get("/errors", response_model=PaginatedErrors)
async def list_errors(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    severity: str | None = None,
    category: str | None = None,
    rule_code: str | None = None,
    field_name: str | None = None,
    record_id: int | None = None,
    is_resolved: bool | None = None,
    batch_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    items, total = await validation_service.list_errors(
        session, page=page, page_size=page_size, severity=severity, category=category,
        rule_code=rule_code, field_name=field_name, record_id=record_id,
        is_resolved=is_resolved, batch_id=batch_id,
    )
    return PaginatedErrors(items=items, total=total, page=page, page_size=page_size)


@router.post("/re-validate-all")
async def revalidate_all(session: AsyncSession = Depends(get_session)):
    return await validation_service.revalidate_all(session)
