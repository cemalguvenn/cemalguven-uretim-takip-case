"""Validation engine — orchestrates rules over records and assigns status.

Reads active rules (and their thresholds) from the DB at runtime, runs each
registered per-record rule, then a batch-level systematic-anomaly pass. Writes
`validation_errors` rows and sets each record's status to the highest severity
found (error > warning > clean). Used both for full-batch validation and for
single-record re-validation after a correction.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import ProductionRecord, ValidationError, ValidationRule
from validation.rules import (
    BATCH_RULES,
    RULE_REGISTRY,
    Finding,
    _present,
    custom_range_check,
)

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
            # User-defined rules aren't in the registry — run the generic checker.
            if cfg.rule_type == "custom_range":
                fn = custom_range_check
            else:
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


def _finding_dict(record_id: int, batch_id: int, code: str, cfg: ValidationRule, f: Finding) -> dict:
    """Same as _make_error but a plain dict for bulk `insert()` (executemany)."""
    return dict(
        record_id=record_id, import_batch_id=batch_id, rule_code=code,
        severity=f.severity, category=cfg.category, field_name=f.field_name,
        message=f.message, expected_value=f.expected_value, actual_value=f.actual_value,
        suggested_action=f.action(), is_resolved=False,
    )


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


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


def _percentile(sorted_vals: list[float], p: float) -> float:
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _iqr_outliers(records, value_fn, cfg, code, field, label):
    """Flag records whose metric falls outside median±k·IQR within their
    (product × station) group — contextual anomalies fixed thresholds miss."""
    out: dict[int, list[tuple[str, ValidationRule, Finding]]] = defaultdict(list)
    k = cfg.error_threshold if cfg.error_threshold is not None else 3.0
    MIN_GROUP = 8  # need a meaningful distribution before calling anything an outlier

    groups: dict[tuple, list] = defaultdict(list)
    for rec in records:
        if rec.stok_adi and rec.is_istasyon_adi and value_fn(rec) is not None:
            groups[(rec.stok_adi, rec.is_istasyon_adi)].append(rec)

    for members in groups.values():
        if len(members) < MIN_GROUP:
            continue
        xs = sorted(value_fn(m) for m in members)
        q1, q3 = _percentile(xs, 0.25), _percentile(xs, 0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - k * iqr, q3 + k * iqr
        for m in members:
            v = value_fn(m)
            if v < lo or v > hi:
                out[m.id].append((code, cfg, Finding(
                    cfg.default_severity,
                    f"{label}: grup normalinden istatistiksel sapma "
                    f"(beklenen ~{lo:.1f}–{hi:.1f}, gerçek {v:.1f}).",
                    field_name=field, expected_value=f"{lo:.1f}–{hi:.1f}", actual_value=f"{v:.1f}")))
    return out


def _statistical_findings(
    records: list[ProductionRecord], rules: dict[str, ValidationRule]
) -> dict[int, list[tuple[str, ValidationRule, Finding]]]:
    out: dict[int, list[tuple[str, ValidationRule, Finding]]] = defaultdict(list)
    oee_cfg = rules.get("STATISTICAL_OEE_OUTLIER")
    if oee_cfg is not None:
        f = _iqr_outliers(records, lambda m: m.oee if _present(m.oee) else None,
                          oee_cfg, "STATISTICAL_OEE_OUTLIER", "OEE", "OEE aykırı değer")
        for rid, t in f.items():
            out[rid].extend(t)
    rate_cfg = rules.get("PRODUCTION_RATE_OUTLIER")
    if rate_cfg is not None:
        def rate(m):
            if _present(m.uretilen_miktar) and _present(m.calisma_suresi) and m.calisma_suresi > 0:
                return m.uretilen_miktar / m.calisma_suresi
            return None
        f = _iqr_outliers(records, rate, rate_cfg, "PRODUCTION_RATE_OUTLIER",
                          "Üretim Hızı", "Üretim hızı aykırı değer")
        for rid, t in f.items():
            out[rid].extend(t)
    return out


def _duplicate_findings(
    records: list[ProductionRecord], rules: dict[str, ValidationRule]
) -> dict[int, list[tuple[str, ValidationRule, Finding]]]:
    """DUPLICATE_RECORD: two complementary uniqueness checks.

    1. record_id — the MES technical key; the same id appearing twice means the
       export duplicated a row.
    2. business key (Tarih, Vardiya, İstasyon, İş Emri No, Stok) — what makes a
       record unique semantically; the same work reported twice would double-count
       production in metrics and in the day×shift submission.

    Every member of a duplicate group is flagged (with the CSV line numbers of
    its twins) so the operator decides which copy to keep.
    """
    out: dict[int, list[tuple[str, ValidationRule, Finding]]] = defaultdict(list)
    cfg = rules.get("DUPLICATE_RECORD")
    if cfg is None:
        return out

    by_record_id: dict[int, list[ProductionRecord]] = defaultdict(list)
    by_business_key: dict[tuple, list[ProductionRecord]] = defaultdict(list)
    for rec in records:
        if rec.record_id is not None:
            by_record_id[rec.record_id].append(rec)
        key = (rec.tarih, rec.vardiya, rec.is_istasyon_adi, rec.is_emri_no, rec.stok_adi)
        if all(part is not None for part in key):
            by_business_key[key].append(rec)

    def flag(members: list[ProductionRecord], field: str, what: str) -> None:
        for m in members:
            twins = ", ".join(str(t.csv_row_number) for t in members if t.id != m.id)
            out[m.id].append((
                "DUPLICATE_RECORD", cfg,
                Finding(cfg.default_severity,
                        f"{what} — aynı kayıt {len(members)} kez görünüyor "
                        f"(diğer CSV satırları: {twins}).",
                        field_name=field, expected_value="tekil kayıt",
                        actual_value=f"{len(members)} kopya"),
            ))

    flagged_ids: set[int] = set()
    for members in by_record_id.values():
        if len(members) > 1:
            flag(members, "record_id", "Yinelenen record_id")
            flagged_ids.update(m.id for m in members)
    for members in by_business_key.values():
        # Skip groups already reported via record_id to avoid double-flagging.
        if len(members) > 1 and not all(m.id in flagged_ids for m in members):
            flag(members, "Tarih+Vardiya+İstasyon+İş Emri+Stok",
                 "Yinelenen iş kaydı (aynı gün/vardiya/istasyon/iş emri/ürün)")
    return out


def _batch_level_findings(
    records: list[ProductionRecord], rules: dict[str, ValidationRule]
) -> dict[int, list[tuple[str, ValidationRule, Finding]]]:
    """Merge all whole-batch passes (systematic + statistical + duplicate) by record id."""
    merged: dict[int, list[tuple[str, ValidationRule, Finding]]] = defaultdict(list)
    for pass_fn in (_systematic_findings, _statistical_findings, _duplicate_findings):
        for rec_id, triples in pass_fn(records, rules).items():
            merged[rec_id].extend(triples)
    return merged


async def validate_batch(session: AsyncSession, batch_id: int) -> dict[str, int]:
    """Validate every record of a batch using bulk inserts/updates.

    Findings are collected as plain dicts and inserted with executemany; final
    statuses are grouped and applied with a handful of bulk UPDATEs. This keeps
    the work O(few queries) instead of O(rows) ORM round-trips — the difference
    between ~30s and a few seconds at 60K+ rows.
    """
    rules = await _load_active_rules(session)
    records = (await session.scalars(
        select(ProductionRecord).where(ProductionRecord.import_batch_id == batch_id)
    )).all()

    # Clear prior findings for this batch (idempotent re-runs).
    await session.execute(
        delete(ValidationError).where(ValidationError.import_batch_id == batch_id)
    )

    batch_level = _batch_level_findings(list(records), rules)  # systematic + statistical
    counts = {"clean": 0, "warning": 0, "error": 0}
    finding_rows: list[dict] = []
    status_updates: list[dict] = []  # [{id, status}] for executemany update-by-PK

    for i, rec in enumerate(records):
        triples = _run_record_rules(rec, rules) + batch_level.get(rec.id, [])
        for code, cfg, f in triples:
            finding_rows.append(_finding_dict(rec.id, batch_id, code, cfg, f))
        if rec.status in _PROTECTED:
            new_status = rec.status
        else:
            new_status = _status_from_findings([t[2] for t in triples])
            status_updates.append({"id": rec.id, "status": new_status})
        counts[new_status if new_status in counts else "clean"] += 1
        if i % 2000 == 0:
            await asyncio.sleep(0)  # yield so polling requests stay responsive

    for chunk in _chunks(finding_rows, 1000):
        await session.execute(insert(ValidationError), chunk)
    # Bulk update-by-primary-key (executemany) — far faster than IN-list UPDATEs.
    for chunk in _chunks(status_updates, 2000):
        await session.execute(update(ProductionRecord), chunk)
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
