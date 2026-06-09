"""Settings endpoints: dynamic validation-rule management.

Rules' thresholds/severity/active flags live in the DB and are read by the
engine at runtime, so editing them here changes validation behaviour without
code changes. Re-running validation is an explicit action (see /api/validation/
re-validate-all) so the user can tune several rules before re-processing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from schemas import ValidationRuleOut, ValidationRuleUpdate
from services import validation_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/validation-rules", response_model=list[ValidationRuleOut])
async def list_rules(session: AsyncSession = Depends(get_session)):
    return await validation_service.list_rules(session)


@router.put("/validation-rules/{rule_id}", response_model=ValidationRuleOut)
async def update_rule(rule_id: int, payload: ValidationRuleUpdate,
                      session: AsyncSession = Depends(get_session)):
    rule = await validation_service.update_rule(
        session, rule_id, payload.model_dump(exclude_unset=True)
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Kural bulunamadı.")
    return rule


@router.post("/validation-rules/reset", response_model=list[ValidationRuleOut])
async def reset_rules(session: AsyncSession = Depends(get_session)):
    return await validation_service.reset_all_rules(session)
