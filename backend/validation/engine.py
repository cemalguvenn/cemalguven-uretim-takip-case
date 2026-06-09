"""Validation engine — orchestrates rules over records and assigns status.

Reads active rules (and their thresholds) from the DB at runtime, runs each
registered per-record rule, then a batch-level systematic-anomaly pass. Writes
`validation_errors` rows and sets each record's status to the highest severity
found (error > warning > clean). Used both for full-batch validation and for
single-record re-validation after a correction.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ProductionRecord, ValidationError, ValidationRule
from validation.rules import BATCH_RULES, RULE_REGISTRY, Finding, _present

# Statuses that user actions own — full-batch validation must not clobber them.
_PROTECTED = {"rejected", "submitted"}
_SEVERITY_RANK = {"clean": 0, "info": 0, "warning": 1, "error": 2}


async def _load_active_rules(session: AsyncSession) -> dict[str, ValidationRule]:
    rows = (await session.scalars(
        select(ValidationRule).where(ValidationRule.is_active.is_(True))
    )).all()
    return {r.rule_code: r for r in rows}


def _status_from_findings(findings: list[Finding]) -> str:
    rank = 0
    for f in findings:
        rank = max(rank, _SEVERITY_RANK.get(f.severity, 0))
    return {0: "clean", 1: "warning", 2: "error"}[rank]


def _run_record_rules(
    rec: ProductionRecord, rules: dict[str, ValidationRule]
) -> list[tuple[str, ValidationRule, Finding]]:
    """Run every active per-record rule; return (rule_code, cfg, finding) tuples."""
    results: list[tuple[str, ValidationRule, Finding]] = []
    for code, cfg in rules.items():
        if code in BATCH_RULES:
            continue
        fn = RULE_REGISTRY.get(code)
        if fn is None:
            continue
        for finding in fn(rec, cfg):
            results.append((code, cfg, finding))
    return results


def _make_error(
    rec: ProductionRecord, batch_id: int, code: str, cfg: ValidationRule, f: Finding
) -> ValidationError:
    return ValidationError(
        record_id=rec.id,
        import_batch_id=batch_id,
        rule_code=code,
        severity=f.severity,
        category=cfg.category,
        field_name=f.field_name,
        message=f.message,
        expected_value=f.expected_value,
        actual_value=f.actual_value,
        suggested_action=f.action(),
    )


def _systematic_findings(
    records: list[ProductionRecord], rules: dict[str, ValidationRule]
) -> dict[int, list[tuple[str, ValidationRule, Finding]]]:
    """SYSTEMATIC_HIGH_P: product+station groups where EVERY record has P above
    the threshold are flagged as a systemic issue (not isolated bad rows)."""
    out: dict[int, list[tuple[str, ValidationRule, Finding]]] = defaultdict(list)
    cfg = rules.get("SYSTEMATIC_HIGH_P")
    if cfg is None:
        return out
    threshold = cfg.error_threshold if cfg.error_threshold is not None else 1000

    groups: dict[tuple, list[ProductionRecord]] = defaultdict(list)
    for rec in records:
        if rec.stok_adi and rec.is_istasyon_adi:
            groups[(rec.stok_adi, rec.is_istasyon_adi)].append(rec)

    # A combo is "systemic" when it has enough records and the vast majority
    # carry extreme P — robust to a few zero/None outliers within the group.
    MIN_GROUP = 3
    MIN_FRACTION = 0.8
    for (stok, station), members in groups.items():
        if len(members) < MIN_GROUP:
            continue
        high = sum(1 for m in members if _present(m.performance) and m.performance > threshold)
        if high / len(members) >= MIN_FRACTION:
            for m in members:
                out[m.id].append((
                    "SYSTEMATIC_HIGH_P", cfg,
                    Finding("info",
                            f"Sistemik yüksek P: '{stok}' + {station} grubundaki tüm "
                            f"kayıtlarda P > {threshold:g} (ideal çevrim süresi hatalı).",
                            field_name="P (Performans)",
                            actual_value=str(m.performance)),
                ))
    return out


async def validate_batch(session: AsyncSession, batch_id: int) -> dict[str, int]:
    """Validate every record of a batch. Returns {clean, warning, error} counts."""
    rules = await _load_active_rules(session)
    records = (await session.scalars(
        select(ProductionRecord).where(ProductionRecord.import_batch_id == batch_id)
    )).all()

    # Clear prior findings for this batch (idempotent re-runs).
    await session.execute(
        delete(ValidationError).where(ValidationError.import_batch_id == batch_id)
    )

    systematic = _systematic_findings(list(records), rules)
    counts = {"clean": 0, "warning": 0, "error": 0}

    for rec in records:
        triples = _run_record_rules(rec, rules) + systematic.get(rec.id, [])
        for code, cfg, f in triples:
            session.add(_make_error(rec, batch_id, code, cfg, f))
        if rec.status not in _PROTECTED:
            rec.status = _status_from_findings([t[2] for t in triples])
        counts[rec.status if rec.status in counts else "clean"] += 1

    await session.commit()
    return counts


async def revalidate_record(
    session: AsyncSession, record: ProductionRecord, *, mark_corrected: bool = False
) -> str:
    """Re-run per-record rules for one record after a correction.

    Returns the new status. If `mark_corrected` and the record is no longer in
    error, the status becomes 'corrected' (human-fixed, still counts toward
    metrics/sync); otherwise it is clean/warning/error from the findings.
    """
    rules = await _load_active_rules(session)
    await session.execute(
        delete(ValidationError).where(ValidationError.record_id == record.id)
    )
    triples = _run_record_rules(record, rules)
    for code, cfg, f in triples:
        session.add(_make_error(record, record.import_batch_id, code, cfg, f))

    base = _status_from_findings([t[2] for t in triples])
    if record.status not in _PROTECTED:
        if mark_corrected and base in ("clean", "warning"):
            record.status = "corrected"
        else:
            record.status = base
    await session.commit()  # updated_at refreshed by the column's onupdate
    return record.status
