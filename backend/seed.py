"""Default validation-rule catalog seeded into the `validation_rules` table.

Each rule's thresholds/severity/active flag live in the DB so the engine reads
them at runtime and the Settings UI edits them. Seeding is idempotent: existing
rules (matched by rule_code) are left untouched so user edits survive re-seed.

Two-tier rules (marked `*severity`) decide warning-vs-error at runtime from
warning_threshold / error_threshold; their default_severity is informational.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ValidationRule

# rule_code, display_name, category, default_severity, warning_th, error_th, description
RULE_CATALOG: list[dict] = [
    # --- Missing / empty values ---
    dict(rule_code="MISSING_SHIFT", display_name="Vardiya boş", category="missing_value",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Vardiya alanı boş — API gönderimi için zorunlu."),
    dict(rule_code="MISSING_WORK_TIME", display_name="Çalışma Süresi boş", category="missing_value",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Çalışma Süresi boş — OEE/Availability hesaplanamaz."),
    dict(rule_code="MISSING_STATION", display_name="İş İstasyon Adı boş", category="missing_value",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="İstasyon boş — makine bazlı raporlama yapılamaz."),
    dict(rule_code="MISSING_STOP_TIME", display_name="Duruş Süresi boş", category="missing_value",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Duruş Süresi boş — süre tutarlılığı doğrulanamaz."),
    dict(rule_code="MISSING_PRODUCT", display_name="Stok Adı boş", category="missing_value",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="Stok/ürün adı boş — raporlamayı etkiler, OEE'yi etkilemez."),
    dict(rule_code="MISSING_JOB_ORDER", display_name="İş Emri No boş", category="missing_value",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="İş Emri No boş."),
    dict(rule_code="MISSING_WORK_CENTER", display_name="İş Merkezi No boş", category="missing_value",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="İş Merkezi No boş."),

    # --- Sentinel / placeholder ---
    dict(rule_code="SENTINEL_VALUE", display_name="Sentinel değer (-10)", category="sentinel",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="MES 'bilinmeyen/null' kodu -10 sayısal bir alanda tespit edildi."),
    dict(rule_code="SENTINEL_STOP_PATTERN", display_name="Sentinel desen (Çalışma=350, Duruş=250)",
         category="sentinel", default_severity="warning",
         warning_threshold=None, error_threshold=None,
         description="MES varsayılan deseni: Çalışma=350 ve Duruş=250 (toplam 600 dk)."),

    # --- Out of range ---
    dict(rule_code="NEGATIVE_WORK_TIME", display_name="Negatif çalışma süresi", category="out_of_range",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Çalışma Süresi < 0."),
    dict(rule_code="NEGATIVE_QUANTITY", display_name="Negatif üretim miktarı", category="out_of_range",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Üretilen Miktar < 0."),
    dict(rule_code="NEGATIVE_DEFECT", display_name="Negatif fire miktarı", category="out_of_range",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Hatalı Üretilen Miktar < 0."),
    dict(rule_code="A_OUT_OF_RANGE", display_name="A (Kullanılırlık) aralık dışı", category="out_of_range",
         default_severity="error", warning_threshold=None, error_threshold=100,
         description="A > error_threshold veya A < 0 (yüzde 0–100 olmalı)."),
    dict(rule_code="Q_OUT_OF_RANGE", display_name="Q (Kalite) aralık dışı", category="out_of_range",
         default_severity="error", warning_threshold=100, error_threshold=120,
         description="Q < 0 ya da warning/error eşiklerini aşıyor (iki katmanlı)."),
    dict(rule_code="OEE_OUT_OF_RANGE", display_name="OEE aralık dışı", category="out_of_range",
         default_severity="warning", warning_threshold=100, error_threshold=150,
         description="100–150 arası WARNING, >150 ERROR (iki katmanlı)."),
    dict(rule_code="P_OUT_OF_RANGE", display_name="P (Performans) aralık dışı", category="out_of_range",
         default_severity="warning", warning_threshold=200, error_threshold=1000,
         description="200–1000 arası WARNING, >1000 ERROR (iki katmanlı)."),
    dict(rule_code="WORK_TIME_EXCESSIVE", display_name="Çalışma süresi aşımı", category="domain_logic",
         default_severity="warning", warning_threshold=480, error_threshold=720,
         description="İş emri çalışma süresi vardiya sınırlarını aşıyor (iki katmanlı)."),

    # --- Inconsistency (formula / relationship) ---
    dict(rule_code="OEE_FORMULA_MISMATCH", display_name="OEE formül tutarsızlığı", category="inconsistency",
         default_severity="error", warning_threshold=None, error_threshold=0.5,
         description="OEE != A*P*Q/10000 (tolerans = error_threshold)."),
    dict(rule_code="Q_FORMULA_MISMATCH", display_name="Q formül tutarsızlığı", category="inconsistency",
         default_severity="error", warning_threshold=None, error_threshold=1.0,
         description="Q != (Üretilen-Hatalı)/Üretilen*100 (tolerans = error_threshold)."),
    dict(rule_code="A_FORMULA_MISMATCH", display_name="A formül tutarsızlığı", category="inconsistency",
         default_severity="warning", warning_threshold=None, error_threshold=5.0,
         description="A != Çalışma/(Çalışma+Plansız Duruş)*100 — sapma > tolerans (yüzde puan). "
                     "Tolerans 5.0: yuvarlama gürültüsü hariç, gerçek tutarsızlıkları yakalar."),
    dict(rule_code="DEFECT_EXCEEDS_PRODUCTION", display_name="Hatalı > Üretilen", category="inconsistency",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Fire miktarı toplam üretimden büyük — fiziksel olarak imkânsız."),
    dict(rule_code="STOP_TIME_MISMATCH", display_name="Duruş süresi tutarsızlığı", category="inconsistency",
         default_severity="error", warning_threshold=None, error_threshold=0.1,
         description="Duruş != Planlı + Plansız (tolerans = error_threshold)."),
    dict(rule_code="STOP_NOT_CATEGORIZED", display_name="Duruş kategorize edilmemiş", category="inconsistency",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="Duruş > 0 ama Planlı = Plansız = 0."),

    # --- Format ---
    dict(rule_code="INVALID_SHIFT_VALUE", display_name="Geçersiz vardiya değeri", category="format",
         default_severity="error", warning_threshold=None, error_threshold=None,
         description="Vardiya 1, 2 veya 3 dışında bir değer."),
    dict(rule_code="JOB_ORDER_FORMAT", display_name="İş Emri No format hatası", category="format",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="İş Emri No, veri sözlüğündeki formata uymuyor "
                     "(302 ile başlayan 10 haneli sayı, örn. 3025678325)."),

    # --- Duplicate records (batch-level) ---
    dict(rule_code="DUPLICATE_RECORD", display_name="Yinelenen kayıt", category="duplicate",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="Aynı record_id veya aynı iş anahtarı (Tarih+Vardiya+İstasyon+İş Emri+Stok) "
                     "birden fazla satırda görünüyor — üretim çift sayılır. Tüm kopyalar, "
                     "ikizlerinin CSV satır numaralarıyla işaretlenir; hangisinin kalacağına "
                     "operatör karar verir."),

    # --- Domain logic ---
    dict(rule_code="ZERO_PROD_LONG_RUN", display_name="Uzun çalışma, sıfır üretim", category="domain_logic",
         default_severity="error", warning_threshold=None, error_threshold=60,
         description="Çalışma > error_threshold dk olmasına rağmen Üretilen = 0."),
    dict(rule_code="ZERO_PROD_SHORT_RUN", display_name="Kısa çalışma, sıfır üretim", category="domain_logic",
         default_severity="warning", warning_threshold=None, error_threshold=None,
         description="Çalışma > 0 ama Üretilen = 0 (kısa süre)."),

    # --- Systematic (batch-level) ---
    dict(rule_code="SYSTEMATIC_HIGH_P", display_name="Sistemik yüksek P", category="systematic",
         default_severity="info", warning_threshold=None, error_threshold=1000,
         description="Ürün+istasyon kombinasyonunda tüm kayıtlarda P > error_threshold — "
                     "tekil hata değil, sistemik sorun (ideal çevrim süresi yanlış)."),

    # --- Statistical / contextual (batch-level, detection only) ---
    dict(rule_code="STATISTICAL_OEE_OUTLIER", display_name="OEE istatistiksel aykırı değer",
         category="statistical", default_severity="warning", warning_threshold=None, error_threshold=3.0,
         description="Ürün×istasyon grubunda OEE, median ± k·IQR dışında (k = error_threshold). "
                     "Sabit eşiklerin kaçırdığı bağlamsal anomalileri yakalar; yanlış pozitifi "
                     "sınırlamak için k=3 (uç değer) ve grup boyutu ≥ 8."),
    dict(rule_code="PRODUCTION_RATE_OUTLIER", display_name="Üretim hızı istatistiksel aykırı değer",
         category="statistical", default_severity="info", warning_threshold=None, error_threshold=3.0,
         description="Ürün×istasyon grubunda üretim hızı (Üretilen/Çalışma) median ± k·IQR dışında."),
]


async def seed_rules(session: AsyncSession) -> int:
    """Insert any catalog rules not already present. Returns count inserted."""
    existing = set(
        (await session.scalars(select(ValidationRule.rule_code))).all()
    )
    inserted = 0
    for spec in RULE_CATALOG:
        if spec["rule_code"] in existing:
            continue
        session.add(ValidationRule(is_active=True, **spec))
        inserted += 1
    if inserted:
        await session.commit()
    return inserted


async def reset_rules(session: AsyncSession) -> None:
    """Restore every catalog rule to its default thresholds/severity/active state."""
    by_code = {
        r.rule_code: r for r in (await session.scalars(select(ValidationRule))).all()
    }
    for spec in RULE_CATALOG:
        rule = by_code.get(spec["rule_code"])
        if rule is None:
            session.add(ValidationRule(is_active=True, **spec))
            continue
        rule.display_name = spec["display_name"]
        rule.description = spec["description"]
        rule.category = spec["category"]
        rule.default_severity = spec["default_severity"]
        rule.warning_threshold = spec["warning_threshold"]
        rule.error_threshold = spec["error_threshold"]
        rule.is_active = True
    await session.commit()
