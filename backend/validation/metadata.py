"""Static metadata about built-in rules — kept import-free so it can be read by
both the ORM model (for the `threshold_kind` property) and the API layer without
risking an import cycle.

`threshold_kind` tells the Settings UI which threshold inputs are meaningful for a
rule, so it can hide the ones that don't apply:

- "dual"   → uses BOTH warning_threshold and error_threshold (two-tier rules)
- "single" → uses error_threshold only (tolerance / single-bound rules)
- "none"   → uses no threshold (presence/format/relationship checks)

Custom (`custom_range`) rules are always treated as "dual" (min/max two-tier).
"""
from __future__ import annotations

# Numeric record fields a custom_range rule may target: (field, Turkish label).
# Mirrors validation.rules._NUMERIC_FIELDS but kept here import-free for reuse.
CUSTOM_RULE_FIELDS: list[tuple[str, str]] = [
    ("availability", "A (Kullanılabilirlik)"),
    ("performance", "P (Performans)"),
    ("quality", "Q (Kalite)"),
    ("oee", "OEE"),
    ("calisma_suresi", "Çalışma Süresi"),
    ("durus_suresi", "Duruş Süresi"),
    ("planli_durus", "Planlı Duruş"),
    ("plansiz_durus", "Plansız Duruş"),
    ("uretilen_miktar", "Üretilen Miktar"),
    ("hatali_uretilen", "Hatalı Üretilen"),
]
CUSTOM_RULE_FIELD_SET = {f for f, _ in CUSTOM_RULE_FIELDS}
CUSTOM_RULE_COMPARISONS = {"max", "min"}

# Built-in rule_code → which thresholds it actually uses.
_DUAL = {
    "Q_OUT_OF_RANGE", "OEE_OUT_OF_RANGE", "P_OUT_OF_RANGE", "WORK_TIME_EXCESSIVE",
}
_SINGLE = {
    "A_OUT_OF_RANGE", "OEE_FORMULA_MISMATCH", "Q_FORMULA_MISMATCH",
    "A_FORMULA_MISMATCH", "STOP_TIME_MISMATCH", "ZERO_PROD_LONG_RUN",
    "SYSTEMATIC_HIGH_P", "STATISTICAL_OEE_OUTLIER", "PRODUCTION_RATE_OUTLIER",
}
THRESHOLD_KIND: dict[str, str] = (
    {code: "dual" for code in _DUAL} | {code: "single" for code in _SINGLE}
)


def threshold_kind_for(rule_code: str, rule_type: str) -> str:
    if rule_type == "custom_range":
        return "dual"
    return THRESHOLD_KIND.get(rule_code, "none")
