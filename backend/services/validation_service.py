"""Validation reporting queries and bulk re-validation."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ImportBatch, ValidationError, ValidationRule
from schemas import KeyCount, ValidationSummaryOut
from seed import reset_rules
from validation.engine import validate_batch


async def _grouped(session: AsyncSession, column) -> list[KeyCount]:
    rows = await session.execute(
        select(column, func.count()).group_by(column).order_by(func.count().desc())
    )
    return [KeyCount(key=str(k), count=c) for k, c in rows]


async def summary(session: AsyncSession) -> ValidationSummaryOut:
    total = await session.scalar(select(func.count()).select_from(ValidationError)) or 0
    return ValidationSummaryOut(
        total=int(total),
        by_severity=await _grouped(session, ValidationError.severity),
        by_category=await _grouped(session, ValidationError.category),
        by_rule=await _grouped(session, ValidationError.rule_code),
    )


async def list_errors(session: AsyncSession, *, page=1, page_size=50, severity=None,
                      category=None, rule_code=None, field_name=None, record_id=None,
                      is_resolved=None) -> tuple[list[ValidationError], int]:
    conds = []
    if severity:
        conds.append(ValidationError.severity == severity)
    if category:
        conds.append(ValidationError.category == category)
    if rule_code:
        conds.append(ValidationError.rule_code == rule_code)
    if field_name:
        conds.append(ValidationError.field_name == field_name)
    if record_id is not None:
        conds.append(ValidationError.record_id == record_id)
    if is_resolved is not None:
        conds.append(ValidationError.is_resolved.is_(is_resolved))

    total = await session.scalar(
        select(func.count()).select_from(ValidationError).where(*conds)
    )
    stmt = (
        select(ValidationError).where(*conds)
        .order_by(ValidationError.severity.desc(), ValidationError.id)
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = list((await session.scalars(stmt)).all())
    return items, int(total or 0)


async def list_rules(session: AsyncSession) -> list[ValidationRule]:
    return list((await session.scalars(
        select(ValidationRule).order_by(ValidationRule.category, ValidationRule.rule_code)
    )).all())


async def update_rule(session: AsyncSession, rule_id: int, patch: dict) -> ValidationRule | None:
    rule = await session.get(ValidationRule, rule_id)
    if rule is None:
        return None
    for field in ("is_active", "default_severity", "warning_threshold", "error_threshold"):
        if field in patch:
            setattr(rule, field, patch[field])
    await session.commit()
    return rule


async def reset_all_rules(session: AsyncSession) -> list[ValidationRule]:
    await reset_rules(session)
    return await list_rules(session)


async def revalidate_all(session: AsyncSession) -> dict[str, int]:
    """Re-run validation across every imported batch with current rules."""
    batch_ids = (await session.scalars(select(ImportBatch.id))).all()
    totals = {"clean": 0, "warning": 0, "error": 0}
    for bid in batch_ids:
        counts = await validate_batch(session, bid)
        for k in totals:
            totals[k] += counts.get(k, 0)
    return totals
