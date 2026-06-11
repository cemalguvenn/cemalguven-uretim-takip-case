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
from schemas import ValidationRuleCreate, ValidationRuleOut, ValidationRuleUpdate
from services import validation_service
from services.validation_service import RuleValidationError

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/validation-rules", response_model=list[ValidationRuleOut])
async def list_rules(session: AsyncSession = Depends(get_session)):
    return await validation_service.list_rules(session)


@router.post("/validation-rules", response_model=ValidationRuleOut, status_code=201)
async def create_rule(payload: ValidationRuleCreate,
                      session: AsyncSession = Depends(get_session)):
    try:
        return await validation_service.create_rule(session, payload.model_dump())
    except RuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/validation-rules/{rule_id}", response_model=ValidationRuleOut)
async def update_rule(rule_id: int, payload: ValidationRuleUpdate,
                      session: AsyncSession = Depends(get_session)):
    try:
        rule = await validation_service.update_rule(
            session, rule_id, payload.model_dump(exclude_unset=True)
        )
    except RuleValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if rule is None:
        raise HTTPException(status_code=404, detail="Kural bulunamadı.")
    return rule


@router.delete("/validation-rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, session: AsyncSession = Depends(get_session)):
    result = await validation_service.delete_rule(session, rule_id)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Kural bulunamadı.")
    if result == "builtin":
        raise HTTPException(
            status_code=400,
            detail="Yerleşik kurallar silinemez; devre dışı bırakabilirsiniz.",
        )


@router.post("/validation-rules/reset", response_model=list[ValidationRuleOut])
async def reset_rules(session: AsyncSession = Depends(get_session)):
    return await validation_service.reset_all_rules(session)
