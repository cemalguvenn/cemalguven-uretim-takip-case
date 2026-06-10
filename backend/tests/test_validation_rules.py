"""Validation-rule unit tests — the highest-weighted part of the brief.

Each rule is exercised for: a clean record (no finding), and the boundary/error
condition (finding with the right severity). Specific real-data cases from the
dataset are pinned to guard against regressions and false positives.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from models import ValidationRule
from validation.rules import RULE_REGISTRY


async def cfg(session, code: str) -> ValidationRule:
    return await session.scalar(select(ValidationRule).where(ValidationRule.rule_code == code))


def sev(findings) -> set[str]:
    return {f.severity for f in findings}


# --------------------------------------------------------------------------- #
# Missing values
# --------------------------------------------------------------------------- #
async def test_missing_shift(session, make_record):
    c = await cfg(session, "MISSING_SHIFT")
    assert RULE_REGISTRY["MISSING_SHIFT"](make_record(vardiya=1), c) == []
    out = RULE_REGISTRY["MISSING_SHIFT"](make_record(vardiya=None), c)
    assert sev(out) == {"error"}


async def test_missing_product_is_warning(session, make_record):
    c = await cfg(session, "MISSING_PRODUCT")
    assert RULE_REGISTRY["MISSING_PRODUCT"](make_record(stok_adi="X"), c) == []
    assert sev(RULE_REGISTRY["MISSING_PRODUCT"](make_record(stok_adi=None), c)) == {"warning"}


# --------------------------------------------------------------------------- #
# Sentinel
# --------------------------------------------------------------------------- #
async def test_sentinel_value_detected(session, make_record):
    c = await cfg(session, "SENTINEL_VALUE")
    assert RULE_REGISTRY["SENTINEL_VALUE"](make_record(), c) == []
    out = RULE_REGISTRY["SENTINEL_VALUE"](make_record(calisma_suresi=-10), c)
    assert sev(out) == {"error"} and out[0].field_name == "Calisma Suresi"


async def test_sentinel_stop_pattern(session, make_record):
    c = await cfg(session, "SENTINEL_STOP_PATTERN")
    out = RULE_REGISTRY["SENTINEL_STOP_PATTERN"](
        make_record(calisma_suresi=350, durus_suresi=250), c)
    assert sev(out) == {"warning"}
    assert RULE_REGISTRY["SENTINEL_STOP_PATTERN"](make_record(), c) == []


# --------------------------------------------------------------------------- #
# Out of range / two-tier
# --------------------------------------------------------------------------- #
async def test_q_out_of_range_two_tier(session, make_record):
    c = await cfg(session, "Q_OUT_OF_RANGE")
    fn = RULE_REGISTRY["Q_OUT_OF_RANGE"]
    assert fn(make_record(quality=95), c) == []                 # normal
    assert sev(fn(make_record(quality=110), c)) == {"warning"}  # 100<Q<=120
    assert sev(fn(make_record(quality=120.0001), c)) == {"error"}
    assert sev(fn(make_record(quality=-3), c)) == {"error"}     # rec_id 2064 case


async def test_oee_two_tier(session, make_record):
    c = await cfg(session, "OEE_OUT_OF_RANGE")
    fn = RULE_REGISTRY["OEE_OUT_OF_RANGE"]
    assert fn(make_record(oee=80), c) == []
    assert sev(fn(make_record(oee=130), c)) == {"warning"}      # 100-150
    assert sev(fn(make_record(oee=348500), c)) == {"error"}     # rec_id 1091 case


async def test_p_excessive(session, make_record):
    c = await cfg(session, "P_OUT_OF_RANGE")
    fn = RULE_REGISTRY["P_OUT_OF_RANGE"]
    assert fn(make_record(performance=150), c) == []
    assert sev(fn(make_record(performance=300), c)) == {"warning"}
    assert sev(fn(make_record(performance=348500), c)) == {"error"}


async def test_a_out_of_range(session, make_record):
    c = await cfg(session, "A_OUT_OF_RANGE")
    fn = RULE_REGISTRY["A_OUT_OF_RANGE"]
    assert fn(make_record(availability=90), c) == []
    assert sev(fn(make_record(availability=120), c)) == {"error"}
    assert sev(fn(make_record(availability=-5), c)) == {"error"}


# --------------------------------------------------------------------------- #
# Inconsistency
# --------------------------------------------------------------------------- #
async def test_defect_exceeds_production(session, make_record):
    c = await cfg(session, "DEFECT_EXCEEDS_PRODUCTION")
    fn = RULE_REGISTRY["DEFECT_EXCEEDS_PRODUCTION"]
    assert fn(make_record(uretilen_miktar=100, hatali_uretilen=2), c) == []
    out = fn(make_record(uretilen_miktar=79, hatali_uretilen=94), c)  # rec_id 84 case
    assert sev(out) == {"error"}


async def test_oee_formula_mismatch(session, make_record):
    c = await cfg(session, "OEE_FORMULA_MISMATCH")
    fn = RULE_REGISTRY["OEE_FORMULA_MISMATCH"]
    # A*P*Q/10000 = 90*95*100/10000 = 85.5 -> matches default
    assert fn(make_record(availability=90, performance=95, quality=100, oee=85.5), c) == []
    assert sev(fn(make_record(availability=90, performance=95, quality=100, oee=50), c)) == {"error"}


async def test_q_formula_mismatch(session, make_record):
    c = await cfg(session, "Q_FORMULA_MISMATCH")
    fn = RULE_REGISTRY["Q_FORMULA_MISMATCH"]
    # (100-2)/100*100 = 98 ; record with quality 98 is consistent
    assert fn(make_record(uretilen_miktar=100, hatali_uretilen=2, quality=98), c) == []
    assert sev(fn(make_record(uretilen_miktar=100, hatali_uretilen=2, quality=50), c)) == {"error"}


async def test_stop_time_mismatch(session, make_record):
    c = await cfg(session, "STOP_TIME_MISMATCH")
    fn = RULE_REGISTRY["STOP_TIME_MISMATCH"]
    assert fn(make_record(durus_suresi=80, planli_durus=30, plansiz_durus=50), c) == []
    assert sev(fn(make_record(durus_suresi=250, planli_durus=0, plansiz_durus=0), c)) == {"error"}


# --------------------------------------------------------------------------- #
# Format / domain logic
# --------------------------------------------------------------------------- #
async def test_invalid_shift_value(session, make_record):
    c = await cfg(session, "INVALID_SHIFT_VALUE")
    fn = RULE_REGISTRY["INVALID_SHIFT_VALUE"]
    assert fn(make_record(vardiya=3), c) == []
    assert sev(fn(make_record(vardiya=5), c)) == {"error"}


async def test_zero_prod_long_run(session, make_record):
    c = await cfg(session, "ZERO_PROD_LONG_RUN")
    fn = RULE_REGISTRY["ZERO_PROD_LONG_RUN"]
    assert fn(make_record(calisma_suresi=400, uretilen_miktar=100), c) == []
    assert sev(fn(make_record(calisma_suresi=120, uretilen_miktar=0), c)) == {"error"}


async def test_no_false_positive_on_clean_record(session, make_record):
    """A fully consistent record must not trigger ANY rule (guards false positives)."""
    rec = make_record(
        availability=80.0, performance=90.0, quality=98.0, oee=70.56,
        calisma_suresi=400.0, plansiz_durus=100.0, durus_suresi=130.0,
        planli_durus=30.0, uretilen_miktar=100, hatali_uretilen=2, vardiya=2,
    )
    triggered = []
    for code, fn in RULE_REGISTRY.items():
        c = await cfg(session, code)
        if c and fn(rec, c):
            triggered.append(code)
    assert triggered == [], f"clean record falsely triggered: {triggered}"


# --------------------------------------------------------------------------- #
# Format — job order (data dictionary: 302 + 7 digits)
# --------------------------------------------------------------------------- #
async def test_job_order_format(session, make_record):
    c = await cfg(session, "JOB_ORDER_FORMAT")
    fn = RULE_REGISTRY["JOB_ORDER_FORMAT"]
    assert fn(make_record(is_emri_no="3025678325"), c) == []          # spec example
    assert sev(fn(make_record(is_emri_no="9925678325"), c)) == {"warning"}  # wrong prefix
    assert sev(fn(make_record(is_emri_no="302567"), c)) == {"warning"}      # too short
    assert sev(fn(make_record(is_emri_no="302567832599"), c)) == {"warning"}  # too long
    assert fn(make_record(is_emri_no=None), c) == []  # emptiness is MISSING_JOB_ORDER's job


# --------------------------------------------------------------------------- #
# Duplicates (batch-level)
# --------------------------------------------------------------------------- #
async def test_duplicate_record_id_flags_all_copies(session, make_record):
    from datetime import date

    from validation.engine import _duplicate_findings

    c = await cfg(session, "DUPLICATE_RECORD")
    rules = {"DUPLICATE_RECORD": c}
    a = make_record(record_id=7, csv_row_number=2, tarih=date(2025, 11, 5))
    b = make_record(record_id=7, csv_row_number=9, tarih=date(2025, 11, 6),
                    is_emri_no="3020000001")
    other = make_record(record_id=8, csv_row_number=3, tarih=date(2025, 11, 7),
                        is_emri_no="3020000002")
    a.id, b.id, other.id = 1, 2, 3

    out = _duplicate_findings([a, b, other], rules)
    assert set(out) == {1, 2}  # both copies flagged, the unique row untouched
    finding = out[1][0][2]
    assert finding.severity == "warning"
    assert "9" in finding.message  # points at the twin's CSV line


async def test_duplicate_business_key(session, make_record):
    from datetime import date

    from validation.engine import _duplicate_findings

    c = await cfg(session, "DUPLICATE_RECORD")
    rules = {"DUPLICATE_RECORD": c}
    # Different record_id but identical work: same day/shift/station/job-order/product.
    common = dict(tarih=date(2025, 11, 5), vardiya=2, is_istasyon_adi="IMM-4000-1",
                  is_emri_no="3025678325", stok_adi="Part-A")
    a = make_record(record_id=10, csv_row_number=4, **common)
    b = make_record(record_id=11, csv_row_number=12, **common)
    a.id, b.id = 1, 2

    out = _duplicate_findings([a, b], rules)
    assert set(out) == {1, 2}
    assert out[2][0][2].field_name == "Tarih+Vardiya+İstasyon+İş Emri+Stok"


async def test_duplicate_skips_incomplete_business_key(session, make_record):
    from datetime import date

    from validation.engine import _duplicate_findings

    c = await cfg(session, "DUPLICATE_RECORD")
    # Missing station → business key incomplete; MISSING_STATION owns that problem.
    a = make_record(record_id=20, csv_row_number=5, tarih=date(2025, 11, 5),
                    is_istasyon_adi=None)
    b = make_record(record_id=21, csv_row_number=6, tarih=date(2025, 11, 5),
                    is_istasyon_adi=None)
    a.id, b.id = 1, 2
    assert _duplicate_findings([a, b], {"DUPLICATE_RECORD": c}) == {}
