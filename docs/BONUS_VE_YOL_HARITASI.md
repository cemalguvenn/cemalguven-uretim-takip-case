# Bonus Özellikler ve Endüstriyel Yol Haritası

## 1. Case Study PDF'indeki Bonus Maddeler (Durum)

| # | Bonus (PDF §10) | Durum | Nerede |
|---|------------------|-------|--------|
| 1 | Validasyon kurallarının UI'dan düzenlenebilmesi | ✅ Tamam | Ayarlar sayfası — eşik/şiddet/aktiflik + "Yeniden Doğrula" |
| 2 | Birim testleri (özellikle validasyon) | ✅ Tamam | 32 pytest; her kural geçerli/uyarı/hata + gerçek vakalar |
| 3 | Sistemik vs tekil anomali ayrımı | ✅ Tamam | `SYSTEMATIC_HIGH_P` (ürün+istasyon grup analizi) |
| 4 | OpenAPI/Swagger | ✅ Tamam | FastAPI `/docs` (otomatik) |
| 5 | Data lineage (CSV satır izlenebilirliği) | ✅ Tamam | `original_data` (JSON) + `csv_row_number` |
| 6 | İndirilebilir validation report (Excel/PDF) | ✅ Tamam | CSV + PDF export (Kayıtlar & Validasyon) |
| 7 | API gönderim geçmişi UI | ✅ Tamam | API Gönderim → Gönderim Geçmişi (`sync_logs`) |
| 8 | Toplu (batch) gönderim | ✅ Tamam | "Tüm Hazır Verileri Gönder" (1 sn aralıkla) |
| 9 | Exponential backoff / retry | ✅ Tamam | `sync_service`: 429 bekleme, 5xx 2/4/8s, max 3 |
| 10 | Circuit breaker | 🟡 Kısmi | Backoff var; tam circuit-breaker (açık/yarı-açık durum) gelecek iş |
| 11 | 100K+ satır import performansı | 🟡 Kısmi | pandas chunked okuma + 60K satır doğrulandı (~30s, senkron); async/background + bulk-insert ile ölçeklenir |
| 12 | Async/background gönderim | 🟡 Kısmi | UI bloklamadan sıralı gönderim var; gerçek arka plan kuyruğu gelecek iş |

**Ek olarak yapılanlar (PDF'de istenmeyen):** dinamik durum makinesi
(düzelt/reddet/gizle/geri al), audit trail, dark + Türkçe enterprise UI,
ağırlıklı OEE agregasyonu, mock-first API (.env ile gerçek API'ye sıfır-kod
geçiş), büyük veri jeneratörü (`scripts/generate_mock_data.py`).

## 2. 100K+ Performans — Mevcut Durum ve Plan
- **Mevcut:** 60.000 satır içe aktarma ~14s, validasyon ~16s (in-memory). Tüm 21
  hata tipi tetikleniyor. Dosya: `data/production_data_50k.csv`.
- **Darboğaz:** satır-başına ORM `add` + tek tek `ValidationError` insert.
- **Plan:** (a) `BackgroundTasks` + ilerleme polling'i; (b) `bulk_insert_mappings`
  / `executemany` ile toplu yazım; (c) import + validasyonu kayıt yerine chunk
  bazında pipeline; (d) gerekirse Postgres'e geçiş (SQLite tek-yazar limiti).

## 3. Endüstriyel En İyi Uygulamalar — İleri Fikirler

### OEE / Yalın Üretim derinliği
- **Six Big Losses & kayıp şelalesi (waterfall):** Availability/Performance/
  Quality kayıplarını dakika/adet bazında ayrıştıran görsel — yöneticinin "nerede
  kaybediyoruz?" sorusunun doğrudan cevabı.
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
- **Denetimsiz anomali tespiti** (Isolation Forest / autoencoder) — kural-dışı,
  bilinmeyen desenleri yakalamak için kural motorunu tamamlar.
- **Otomatik düzeltme önerileri:** formülden beklenen değeri öneren "tek tık düzelt".
- **Güven skoru:** her kayda veri kalitesi skoru; eşikle otomatik karantina.

### Operasyonel UX
- **Alerting:** eşik ihlali / başarısız gönderimde e-posta/Slack bildirimi.
- **Zamanlanmış raporlar:** vardiya devir (handover) PDF'i otomatik e-posta.
- **Dashboard drill-down:** KPI → ilgili kayıtlara tıklayarak inme.
- **Kaydedilebilir filtre profilleri** ve i18n/erişilebilirlik.

## 4. Öncelik Önerisi (sonraki sprint)
1. İdeal çevrim süresi master-data + P yeniden hesaplama (kök neden).
2. Duruş neden kodları + Pareto + kayıp şelalesi.
3. 100K+ için background import + bulk insert.
4. RBAC + secrets manager.
5. SPC kontrol kartları & alerting.
