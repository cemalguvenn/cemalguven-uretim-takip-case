# Bonus Özellikler ve Endüstriyel Yol Haritası

## 1. Case Study PDF'indeki Bonus Maddeler (Durum)

| # | Bonus (PDF §10) | Durum | Nerede |
|---|------------------|-------|--------|
| 1 | Validasyon kurallarının UI'dan düzenlenebilmesi | ✅ Tamam | Ayarlar sayfası — eşik/şiddet/aktiflik + "Yeniden Doğrula" |
| 2 | Birim testleri (özellikle validasyon) | ✅ Tamam | 37 pytest; her kural geçerli/uyarı/hata + gerçek vakalar |
| 3 | Sistemik vs tekil anomali ayrımı | ✅ Tamam | `SYSTEMATIC_HIGH_P` (ürün+istasyon grup analizi) |
| 4 | OpenAPI/Swagger | ✅ Tamam | FastAPI `/docs` (otomatik) |
| 5 | Data lineage (CSV satır izlenebilirliği) | ✅ Tamam | `original_data` (JSON) + `csv_row_number` |
| 6 | İndirilebilir validation report (Excel/PDF) | ✅ Tamam | CSV + PDF export (Kayıtlar & Validasyon) |
| 7 | API gönderim geçmişi UI | ✅ Tamam | API Gönderim → Gönderim Geçmişi (`sync_logs`) |
| 8 | Toplu (batch) gönderim | ✅ Tamam | "Tüm Hazır Verileri Gönder" (1 sn aralıkla) |
| 9 | Exponential backoff / retry | ✅ Tamam | `sync_service`: 429 bekleme, 5xx 2/4/8s, max 3 |
| 10 | Circuit breaker | 🟡 Kısmi | Backoff var; tam circuit-breaker (açık/yarı-açık durum) gelecek iş |
| 11 | 100K+ satır import performansı | ✅ Tamam | Bulk insert + WAL + arka plan; 60K ~10s (önceden ~30s) |
| 12 | Async/background gönderim | ✅ Tamam | Yükleme anında döner, iş arka planda; ilerleme polling'i + APScheduler auto-sync |

**Ek olarak yapılanlar (PDF'de istenmeyen):** dinamik durum makinesi
(düzelt/reddet/gizle/geri al), audit trail, dark + Türkçe enterprise UI,
ağırlıklı OEE agregasyonu, mock-first API (.env ile gerçek API'ye sıfır-kod
geçiş), büyük veri jeneratörü (`scripts/generate_mock_data.py`).

### Milestone 2'de tamamlananlar (önceki yol haritasından)
- **Asenkron/arka plan içe aktarma + 100K performans** — bulk insert (executemany
  update-by-PK) + SQLite WAL + ilerleme çubuğu (poll). 60K ~10s.
- **İstatistiksel/bağlamsal anomali tespiti** — ürün×istasyon IQR aykırı değer
  (`STATISTICAL_OEE_OUTLIER`, `PRODUCTION_RATE_OUTLIER`); kural-tabanlı motoru
  tamamlar (ML'siz, yalnızca tespit).
- **OEE Kayıp Şelalesi (Kayıp Analizi sayfası)** — A/P/Q kayıpları + planlı/plansız
  duruş dağılımı + istasyon bazlı kayıp (Six Big Losses'ın veri-destekli alt kümesi).
- **Zamanlanmış auto-sync** — APScheduler ile opt-in periyodik gönderim + "Şimdi Çalıştır".
- **Dashboard drill-down** — grafik→filtreli Kayıtlar (URL parametreli).
- **Uygulama içi uyarı merkezi** — başarısız sync / yüksek hata oranı / sistemik anomali.

## 2. 100K+ Performans — Tamamlandı
- **Çözüm:** satır-başına ORM `add` → **bulk `insert()`**; satır-başına status
  güncellemesi → **executemany update-by-PK** (kritik: `id.in_(...)` ile 60K için
  ~30s'di, executemany ile saniyeler); **SQLite WAL** ile arka plan yazarken UI
  okuyabiliyor; iş **arka planda** (BackgroundTasks), UI ilerleme çubuğuyla yokluyor.
- **Sonuç:** 60.000 satır içe aktarma ~2.8s + validasyon ~7.7s ≈ **10.5s**
  (önceden ~30s). Tüm 23 hata tipi tetikleniyor. Dosya: `data/production_data_50k.csv`.
- **Daha ileri (≥500K):** chunk-bazlı streaming validasyon ve gerekirse Postgres
  + kalıcı kuyruk (Celery) — şu an kapsam dışı.

## 3. Endüstriyel En İyi Uygulamalar — İleri Fikirler

### OEE / Yalın Üretim derinliği
- **Six Big Losses & kayıp şelalesi (waterfall):** ✅ 3 aşamalı (A/P/Q) waterfall +
  planlı/plansız duruş dağılımı **yapıldı** (Kayıp Analizi). Tam 6-kayıp ayrımı
  (idling vs hız kaybı, setup vs arıza) **neden kodu** gerektirir → aşağıya bağlı.
- **Duruş Pareto'su:** Duruş nedeni kodları (reason codes) ile %80/20 analizi.
  *Veri eksikliği:* mevcut CSV'de neden kodu yok → MES'ten neden kodu alınmalı.
- **SPC kontrol kartları:** OEE/Q için X̄-R kartları, kontrol limitleri ve
  kural-tabanlı kayma (Western Electric) uyarıları.
- **TEEP & planlama kaybı:** takvim bazlı kullanım (utilization) metriği.
- **İdeal çevrim süresi (master data) yönetimi:** sistemik yüksek-P sorununun
  kök nedeni; ürün×istasyon ideal hız tablosu → P'nin doğru hesaplanması.

### Mimari / ölçeklenme
- **Gerçek zamanlı ingestion:** CSV batch yerine MQTT/Kafka akışı.
- **RBAC + kullanıcı bazlı audit:** operatör/mühendis/yönetici rolleri; API
  anahtarı için secrets manager (Vault) — şu an `.env`.
- **Çok hat / çok tesis hiyerarşisi:** iş merkezi → hat → tesis rollup'ları.
- **Dockerize + CI/CD + gözlemlenebilirlik:** yapılandırılmış log, metrik, healthz.

### Veri kalitesi / ML
- **İstatistiksel/bağlamsal anomali tespiti:** ✅ ürün×istasyon IQR aykırı değer
  **yapıldı** (ML'siz). Sonraki adım: denetimsiz ML (Isolation Forest / autoencoder)
  ile bilinmeyen çok-boyutlu desenler.
- **Güven skoru:** her kayda veri kalitesi skoru; eşikle otomatik karantina.
- (Not: otomatik düzeltme/doldurma bilinçli olarak kapsam dışı — yalnızca tespit.)

### Operasyonel UX
- **Uyarı merkezi:** ✅ uygulama içi zil (başarısız sync / yüksek hata oranı /
  sistemik anomali) **yapıldı**. Sonraki adım: e-posta/Slack bildirimi.
- **Dashboard drill-down:** ✅ grafik→filtreli Kayıtlar **yapıldı**.
- **Zamanlanmış gönderim:** ✅ APScheduler auto-sync **yapıldı**. Sonraki adım:
  vardiya devir (handover) PDF'i otomatik e-posta.
- **Kaydedilebilir filtre profilleri** ve i18n/erişilebilirlik.

## 4. Öncelik Önerisi (sonraki sprint)
1. İdeal çevrim süresi master-data + P yeniden hesaplama (sistemik yüksek-P kök nedeni).
2. Duruş neden kodları → Pareto + tam Six Big Losses ayrımı.
3. SPC kontrol kartları (X̄-R) + e-posta/Slack alerting.
4. RBAC + secrets manager (API anahtarı).
5. Denetimsiz ML anomali tespiti + kayıt güven skoru.
