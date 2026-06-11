"""Validation reporting queries and bulk re-validation."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ImportBatch, ValidationError, ValidationRule
from schemas import KeyCount, ValidationSummaryOut
from seed import reset_rules
from validation.engine import validate_batch
from validation.metadata import CUSTOM_RULE_COMPARISONS, CUSTOM_RULE_FIELD_SET


async def _grouped(session: AsyncSession, column, conds=()) -> list[KeyCount]:
    rows = await session.execute(
        select(column, func.count()).where(*conds)
        .group_by(column).order_by(func.count().desc())
    )
    return [KeyCount(key=str(k), count=c) for k, c in rows]


async def summary(session: AsyncSession, *, batch_id: int | None = None) -> ValidationSummaryOut:
    conds = [ValidationError.import_batch_id == batch_id] if batch_id is not None else []
    total = await session.scalar(
        select(func.count()).select_from(ValidationError).where(*conds)
    ) or 0
    return ValidationSummaryOut(
        total=int(total),
        by_severity=await _grouped(session, ValidationError.severity, conds),
        by_category=await _grouped(session, ValidationError.category, conds),
        by_rule=await _grouped(session, ValidationError.rule_code, conds),
    )


async def list_errors(session: AsyncSession, *, page=1, page_size=50, severity=None,
                      category=None, rule_code=None, field_name=None, record_id=None,
                      is_resolved=None, batch_id=None) -> tuple[list[ValidationError], int]:
    conds = []
    if batch_id is not None:
        conds.append(ValidationError.import_batch_id == batch_id)
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


class RuleValidationError(ValueError):
    """Bad custom-rule payload (unknown field/comparison, no threshold)."""


def _validate_custom_fields(target_field: str | None, comparison: str | None) -> None:
    if target_field is not None and target_field not in CUSTOM_RULE_FIELD_SET:
        raise RuleValidationError(f"Geçersiz alan: {target_field}")
    if comparison is not None and comparison not in CUSTOM_RULE_COMPARISONS:
        raise RuleValidationError("Karşılaştırma 'max' veya 'min' olmalı.")


async def _unique_rule_code(session: AsyncSession, base: str) -> str:
    existing = set((await session.scalars(select(ValidationRule.rule_code))).all())
    code, i = base, 1
    while code in existing:
        i += 1
        code = f"{base}_{i}"
    return code


async def create_rule(session: AsyncSession, payload: dict) -> ValidationRule:
    """Create a user-defined custom_range rule. Raises RuleValidationError on bad input."""
    target_field = payload.get("target_field")
    comparison = payload.get("comparison")
    _validate_custom_fields(target_field, comparison)
    if payload.get("warning_threshold") is None and payload.get("error_threshold") is None:
        raise RuleValidationError("En az bir eşik (uyarı veya hata) belirtilmeli.")

    code = await _unique_rule_code(
        session, f"CUSTOM_{target_field.upper()}_{comparison.upper()}"
    )
    rule = ValidationRule(
        rule_code=code,
        display_name=payload["display_name"],
        description=payload.get("description"),
        category="custom",
        default_severity=payload.get("default_severity", "warning"),
        is_active=payload.get("is_active", True),
        warning_threshold=payload.get("warning_threshold"),
        error_threshold=payload.get("error_threshold"),
        rule_type="custom_range",
        target_field=target_field,
        comparison=comparison,
    )
    session.add(rule)
    await session.commit()
    return rule


async def update_rule(session: AsyncSession, rule_id: int, patch: dict) -> ValidationRule | None:
    rule = await session.get(ValidationRule, rule_id)
    if rule is None:
        return None
    editable = ["is_active", "default_severity", "warning_threshold", "error_threshold"]
    if rule.rule_type == "custom_range":
        editable += ["display_name", "description", "target_field", "comparison"]
        _validate_custom_fields(patch.get("target_field"), patch.get("comparison"))
    for field in editable:
        if field in patch:
            setattr(rule, field, patch[field])
    await session.commit()
    return rule


async def delete_rule(session: AsyncSession, rule_id: int) -> str:
    """Delete a custom rule. Returns 'deleted' | 'not_found' | 'builtin'.

    Built-in rules are code-backed and re-seeded on startup, so they can't be
    deleted (only deactivated). Removes the rule's findings for cleanliness.
    """
    rule = await session.get(ValidationRule, rule_id)
    if rule is None:
        return "not_found"
    if rule.rule_type != "custom_range":
        return "builtin"
    from sqlalchemy import delete

    await session.execute(
        delete(ValidationError).where(ValidationError.rule_code == rule.rule_code)
    )
    await session.delete(rule)
    await session.commit()
    return "deleted"


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
