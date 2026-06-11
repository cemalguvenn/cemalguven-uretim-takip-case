"""Custom (user-defined) validation rules, threshold metadata, and the
dashboard quarantine surfacing — the Milestone enhancements for clean data."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from models import ValidationRule
from services import validation_service
from validation.engine import _load_active_rules, _run_record_rules
from validation.rules import custom_range_check


def _rule(**kw) -> ValidationRule:
    base = dict(
        rule_code="CUSTOM_X", display_name="x", category="custom",
        default_severity="warning", is_active=True, rule_type="custom_range",
    )
    base.update(kw)
    return ValidationRule(**base)


def sev(findings) -> set[str]:
    return {f.severity for f in findings}


# --------------------------------------------------------------------------- #
# Generic custom_range logic
# --------------------------------------------------------------------------- #
def test_custom_max_two_tier(make_record):
    r = _rule(target_field="oee", comparison="max", warning_threshold=100, error_threshold=150)
    assert custom_range_check(make_record(oee=90), r) == []
    assert sev(custom_range_check(make_record(oee=120), r)) == {"warning"}
    assert sev(custom_range_check(make_record(oee=200), r)) == {"error"}


def test_custom_min_single_threshold_uses_default_severity(make_record):
    # Only one threshold set → that bound takes the rule's default_severity.
    r = _rule(target_field="quality", comparison="min", warning_threshold=50,
              error_threshold=None, default_severity="error")
    assert custom_range_check(make_record(quality=80), r) == []
    assert sev(custom_range_check(make_record(quality=20), r)) == {"error"}


def test_custom_ignores_missing_and_sentinel(make_record):
    r = _rule(target_field="oee", comparison="max", error_threshold=150)
    assert custom_range_check(make_record(oee=None), r) == []
    assert custom_range_check(make_record(oee=-10), r) == []  # MES sentinel ignored


# --------------------------------------------------------------------------- #
# Engine dispatch (rule_code not in the registry → generic checker)
# --------------------------------------------------------------------------- #
async def test_engine_dispatches_custom_rule(session, make_record):
    await validation_service.create_rule(session, dict(
        display_name="OEE>150", target_field="oee", comparison="max",
        error_threshold=150, default_severity="error"))
    rules = await _load_active_rules(session)
    out = _run_record_rules(make_record(oee=200), rules)
    assert any(cfg.rule_type == "custom_range" for _, cfg, _ in out)


# --------------------------------------------------------------------------- #
# Service CRUD + guards
# --------------------------------------------------------------------------- #
async def test_create_and_delete_custom_rule(session):
    rule = await validation_service.create_rule(session, dict(
        display_name="OEE>150", target_field="oee", comparison="max",
        error_threshold=150, default_severity="error"))
    assert rule.rule_type == "custom_range"
    assert rule.rule_code.startswith("CUSTOM_OEE_MAX")
    assert await validation_service.delete_rule(session, rule.id) == "deleted"


async def test_unique_rule_code(session):
    a = await validation_service.create_rule(session, dict(
        display_name="a", target_field="oee", comparison="max", error_threshold=150))
    b = await validation_service.create_rule(session, dict(
        display_name="b", target_field="oee", comparison="max", error_threshold=160))
    assert a.rule_code != b.rule_code


async def test_builtin_cannot_be_deleted(session):
    builtin = await session.scalar(
        select(ValidationRule).where(ValidationRule.rule_code == "MISSING_SHIFT"))
    assert await validation_service.delete_rule(session, builtin.id) == "builtin"


async def test_create_rule_validates_field(session):
    with pytest.raises(validation_service.RuleValidationError):
        await validation_service.create_rule(session, dict(
            display_name="bad", target_field="not_a_field", comparison="max",
            error_threshold=1))


async def test_create_rule_requires_threshold(session):
    with pytest.raises(validation_service.RuleValidationError):
        await validation_service.create_rule(session, dict(
            display_name="no threshold", target_field="oee", comparison="max"))


async def test_threshold_kind(session):
    rules = {r.rule_code: r for r in await validation_service.list_rules(session)}
    assert rules["OEE_OUT_OF_RANGE"].threshold_kind == "dual"
    assert rules["A_OUT_OF_RANGE"].threshold_kind == "single"
    assert rules["MISSING_SHIFT"].threshold_kind == "none"


# --------------------------------------------------------------------------- #
# API: quarantine surfacing + rule CRUD endpoints (full CSV imported by fixture)
# --------------------------------------------------------------------------- #
async def test_summary_surfaces_quarantine(client):
    body = (await client.get("/api/reports/summary")).json()
    # Every defect row in the dataset has defect > production → all quarantined.
    assert body["total_defect"] == 0
    assert body["quarantined_defect_records"] == 164
    assert body["quarantined_defect_units"] > 0


async def test_rule_crud_endpoints(client):
    created = await client.post("/api/settings/validation-rules", json=dict(
        display_name="API OEE>150", target_field="oee", comparison="max",
        error_threshold=150))
    assert created.status_code == 201
    assert created.json()["rule_type"] == "custom_range"
    rid = created.json()["id"]

    assert (await client.delete(f"/api/settings/validation-rules/{rid}")).status_code == 204

    rules = (await client.get("/api/settings/validation-rules")).json()
    builtin = next(x for x in rules if x["rule_type"] == "builtin")
    assert (await client.delete(
        f"/api/settings/validation-rules/{builtin['id']}")).status_code == 400

    bad = await client.post("/api/settings/validation-rules", json=dict(
        display_name="bad", target_field="nope", comparison="max", error_threshold=1))
    assert bad.status_code == 400
