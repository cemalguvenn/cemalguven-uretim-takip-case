"""Validation rules — one self-contained function per rule_code.

Each rule implements the same contract:

    def check(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]

and is registered in RULE_REGISTRY by its rule_code. Thresholds and severity
come from `cfg` (the DB row) — nothing is hardcoded — so the Settings UI can
retune behaviour without code changes (Open/Closed). Adding a rule = write a
function + add a seed row.

Two-tier rules (OEE/P/Q/work-time) decide warning-vs-error at runtime from
cfg.warning_threshold / cfg.error_threshold.

Sentinel value -10 is owned by SENTINEL_VALUE; other numeric rules ignore it to
avoid double-flagging (which would read as false positives).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from models import ProductionRecord, ValidationRule

SENTINEL = -10
# Numeric fields scanned for the MES sentinel placeholder.
_NUMERIC_FIELDS = [
    ("availability", "A"), ("performance", "P"), ("quality", "Q"), ("oee", "OEE"),
    ("calisma_suresi", "Calisma Suresi"), ("durus_suresi", "Durus Suresi"),
    ("planli_durus", "Planli Durus"), ("plansiz_durus", "Plansiz Durus"),
    ("uretilen_miktar", "Uretilen Miktar"), ("hatali_uretilen", "Hatali Uretilen"),
]

_ACTION_BY_SEVERITY = {"error": "reddet", "warning": "düzelt", "info": "incele"}


@dataclass
class Finding:
    severity: str            # error | warning | info
    message: str
    field_name: str | None = None
    expected_value: str | None = None
    actual_value: str | None = None
    suggested_action: str | None = None

    def action(self) -> str:
        return self.suggested_action or _ACTION_BY_SEVERITY.get(self.severity, "incele")


RuleFn = Callable[[ProductionRecord, ValidationRule], list[Finding]]
RULE_REGISTRY: dict[str, RuleFn] = {}
# Rules evaluated over the whole batch rather than a single record.
BATCH_RULES: set[str] = {"SYSTEMATIC_HIGH_P"}


def rule(code: str) -> Callable[[RuleFn], RuleFn]:
    def deco(fn: RuleFn) -> RuleFn:
        RULE_REGISTRY[code] = fn
        return fn
    return deco


def _is_sentinel(v: float | int | None) -> bool:
    return v is not None and v == SENTINEL


def _present(v: float | int | None) -> bool:
    """A value we should evaluate: not None and not the sentinel placeholder."""
    return v is not None and v != SENTINEL


# --------------------------------------------------------------------------- #
# Missing / empty values
# --------------------------------------------------------------------------- #
def _missing(field: str, label: str) -> RuleFn:
    def check(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
        if getattr(rec, field) is None:
            return [Finding(cfg.default_severity, f"{label} boş.", field_name=label)]
        return []
    return check


RULE_REGISTRY["MISSING_SHIFT"] = _missing("vardiya", "Vardiya")
RULE_REGISTRY["MISSING_WORK_TIME"] = _missing("calisma_suresi", "Çalışma Süresi")
RULE_REGISTRY["MISSING_STATION"] = _missing("is_istasyon_adi", "İş İstasyon Adı")
RULE_REGISTRY["MISSING_STOP_TIME"] = _missing("durus_suresi", "Duruş Süresi")
RULE_REGISTRY["MISSING_PRODUCT"] = _missing("stok_adi", "Stok Adı")
RULE_REGISTRY["MISSING_JOB_ORDER"] = _missing("is_emri_no", "İş Emri No")
RULE_REGISTRY["MISSING_WORK_CENTER"] = _missing("is_merkezi_no", "İş Merkezi No")


# --------------------------------------------------------------------------- #
# Sentinel / placeholder
# --------------------------------------------------------------------------- #
@rule("SENTINEL_VALUE")
def sentinel_value(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    out: list[Finding] = []
    for field, label in _NUMERIC_FIELDS:
        if _is_sentinel(getattr(rec, field)):
            out.append(Finding(
                cfg.default_severity,
                f"{label} alanında MES sentinel değeri (-10) tespit edildi.",
                field_name=label, expected_value="geçerli sayı", actual_value="-10",
            ))
    return out


@rule("SENTINEL_STOP_PATTERN")
def sentinel_stop_pattern(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    if rec.calisma_suresi == 350 and rec.durus_suresi == 250:
        return [Finding(
            cfg.default_severity,
            "MES varsayılan deseni: Çalışma=350, Duruş=250 (toplam 600 dk).",
            field_name="Çalışma/Duruş Süresi", actual_value="350/250",
        )]
    return []


# --------------------------------------------------------------------------- #
# Out of range (sign / bounds)
# --------------------------------------------------------------------------- #
def _negative(field: str, label: str) -> RuleFn:
    def check(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
        v = getattr(rec, field)
        if _present(v) and v < 0:
            return [Finding(cfg.default_severity, f"{label} negatif.", field_name=label,
                            expected_value=">= 0", actual_value=str(v))]
        return []
    return check


RULE_REGISTRY["NEGATIVE_WORK_TIME"] = _negative("calisma_suresi", "Çalışma Süresi")
RULE_REGISTRY["NEGATIVE_QUANTITY"] = _negative("uretilen_miktar", "Üretilen Miktar")
RULE_REGISTRY["NEGATIVE_DEFECT"] = _negative("hatali_uretilen", "Hatalı Üretilen")


@rule("A_OUT_OF_RANGE")
def a_out_of_range(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    a = rec.availability
    if not _present(a):
        return []
    hi = cfg.error_threshold if cfg.error_threshold is not None else 100
    if a > hi or a < 0:
        return [Finding("error", f"A (Kullanılırlık) aralık dışı (0–{hi:g}).",
                        field_name="A", expected_value=f"0–{hi:g}", actual_value=str(a))]
    return []


@rule("Q_OUT_OF_RANGE")
def q_out_of_range(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    q = rec.quality
    if not _present(q):
        return []
    warn = cfg.warning_threshold if cfg.warning_threshold is not None else 100
    err = cfg.error_threshold if cfg.error_threshold is not None else 120
    if q < 0 or q > err:
        sev = "error"
    elif q > warn:
        sev = "warning"
    else:
        return []
    return [Finding(sev, f"Q (Kalite) aralık dışı (0–{warn:g} normal).",
                    field_name="Q", expected_value=f"0–{warn:g}", actual_value=str(q))]


def _two_tier(field: str, label: str, allow_negative_error: bool = False) -> RuleFn:
    """Generic >warning→warning, >error→error rule (OEE, P, work-time)."""
    def check(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
        v = getattr(rec, field)
        if not _present(v):
            return []
        warn, err = cfg.warning_threshold, cfg.error_threshold
        if err is not None and v > err:
            sev = "error"
        elif allow_negative_error and v < 0:
            sev = "error"
        elif warn is not None and v > warn:
            sev = "warning"
        else:
            return []
        bound = f"<= {warn:g}" if warn is not None else f"<= {err:g}"
        return [Finding(sev, f"{label} aralık dışı.", field_name=label,
                        expected_value=bound, actual_value=str(v))]
    return check


RULE_REGISTRY["OEE_OUT_OF_RANGE"] = _two_tier("oee", "OEE", allow_negative_error=True)
RULE_REGISTRY["P_OUT_OF_RANGE"] = _two_tier("performance", "P (Performans)")
RULE_REGISTRY["WORK_TIME_EXCESSIVE"] = _two_tier("calisma_suresi", "Çalışma Süresi")


# --------------------------------------------------------------------------- #
# Inconsistency (formula / relationship)
# --------------------------------------------------------------------------- #
@rule("OEE_FORMULA_MISMATCH")
def oee_formula(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    a, p, q, oee = rec.availability, rec.performance, rec.quality, rec.oee
    if not all(_present(x) for x in (a, p, q, oee)):
        return []
    tol = cfg.error_threshold if cfg.error_threshold is not None else 0.5
    computed = a * p * q / 10000
    if abs(oee - computed) > tol:
        return [Finding(cfg.default_severity,
                        "OEE != A*P*Q/10000.", field_name="OEE",
                        expected_value=f"{computed:.2f}", actual_value=str(oee))]
    return []


@rule("Q_FORMULA_MISMATCH")
def q_formula(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    u, h, q = rec.uretilen_miktar, rec.hatali_uretilen, rec.quality
    if not all(_present(x) for x in (u, h, q)) or u == 0:
        return []
    tol = cfg.error_threshold if cfg.error_threshold is not None else 1.0
    computed = (u - h) / u * 100
    if abs(q - computed) > tol:
        return [Finding(cfg.default_severity,
                        "Q != (Üretilen-Hatalı)/Üretilen*100.", field_name="Q",
                        expected_value=f"{computed:.2f}", actual_value=str(q))]
    return []


@rule("A_FORMULA_MISMATCH")
def a_formula(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    a, work, unplanned = rec.availability, rec.calisma_suresi, rec.plansiz_durus
    if not all(_present(x) for x in (a, work, unplanned)) or (work + unplanned) == 0:
        return []
    tol = cfg.error_threshold if cfg.error_threshold is not None else 1.0
    computed = work / (work + unplanned) * 100
    if abs(a - computed) > tol:
        return [Finding(cfg.default_severity,
                        "A != Çalışma/(Çalışma+Plansız Duruş)*100.", field_name="A",
                        expected_value=f"{computed:.2f}", actual_value=str(a))]
    return []


@rule("DEFECT_EXCEEDS_PRODUCTION")
def defect_exceeds(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    u, h = rec.uretilen_miktar, rec.hatali_uretilen
    if _present(u) and _present(h) and h > u:
        return [Finding(cfg.default_severity,
                        "Hatalı üretim toplam üretimden büyük — fiziksel olarak imkânsız.",
                        field_name="Hatalı Üretilen",
                        expected_value=f"<= {u}", actual_value=str(h))]
    return []


@rule("STOP_TIME_MISMATCH")
def stop_time_mismatch(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    d, pl, pls = rec.durus_suresi, rec.planli_durus, rec.plansiz_durus
    if not all(_present(x) for x in (d, pl, pls)):
        return []
    tol = cfg.error_threshold if cfg.error_threshold is not None else 0.1
    if abs(d - (pl + pls)) > tol:
        return [Finding(cfg.default_severity,
                        "Duruş != Planlı + Plansız.", field_name="Duruş Süresi",
                        expected_value=f"{pl + pls:g}", actual_value=str(d))]
    return []


@rule("STOP_NOT_CATEGORIZED")
def stop_not_categorized(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    d, pl, pls = rec.durus_suresi, rec.planli_durus, rec.plansiz_durus
    if _present(d) and d > 0 and (pl or 0) == 0 and (pls or 0) == 0:
        return [Finding(cfg.default_severity,
                        "Duruş > 0 ama planlı/plansız kırılımı yok.",
                        field_name="Duruş Süresi", actual_value=str(d))]
    return []


# --------------------------------------------------------------------------- #
# Format
# --------------------------------------------------------------------------- #
@rule("INVALID_SHIFT_VALUE")
def invalid_shift(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    if rec.vardiya is not None and rec.vardiya not in (1, 2, 3):
        return [Finding(cfg.default_severity, "Vardiya 1, 2 veya 3 olmalı.",
                        field_name="Vardiya", expected_value="1|2|3",
                        actual_value=str(rec.vardiya))]
    return []


# --------------------------------------------------------------------------- #
# Domain logic
# --------------------------------------------------------------------------- #
@rule("ZERO_PROD_LONG_RUN")
def zero_prod_long_run(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    work, u = rec.calisma_suresi, rec.uretilen_miktar
    threshold = cfg.error_threshold if cfg.error_threshold is not None else 60
    if _present(work) and work > threshold and u == 0:
        return [Finding(cfg.default_severity,
                        f"Çalışma > {threshold:g} dk olmasına rağmen üretim sıfır.",
                        field_name="Üretilen Miktar", actual_value="0")]
    return []


@rule("ZERO_PROD_SHORT_RUN")
def zero_prod_short_run(rec: ProductionRecord, cfg: ValidationRule) -> list[Finding]:
    work, u = rec.calisma_suresi, rec.uretilen_miktar
    long_threshold = 60
    if _present(work) and 0 < work <= long_threshold and u == 0:
        return [Finding(cfg.default_severity,
                        "Kısa çalışma süresinde üretim sıfır.",
                        field_name="Üretilen Miktar", actual_value="0")]
    return []
