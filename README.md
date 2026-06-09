# Üretim Performans Takip Uygulaması

Magna enjeksiyon kalıplama hattının MES sisteminden gelen CSV üretim verisini
içe aktaran, kapsamlı **veri kalitesi validasyonu** çalıştıran, kullanıcının
hatalı kayıtları inceleyip düzeltebildiği/reddedebildiği ve **yalnızca
doğrulanmış veriyi** gün × vardiya bazında hedef REST API'ye gönderen tam-stack
bir MVP.

> Veri "temiz" varsayılmaz. 2.117 satırlık MES verisinde tespit edilen
> tutarsızlıkların nasıl yakalandığı, sınıflandırıldığı ve yalnızca güvenilir
> verinin nasıl ileri taşındığı bu projenin merkezindedir.

---

## Hızlı Kurulum & Çalıştırma

Önkoşullar: **Python 3.11+** ve **Node.js 18+**.

```bash
# 1) Kök dizinde ortam dosyası (mock API varsayılanlarıyla gelir)
cp .env.example .env

# 2) Backend (Terminal 1)
cd backend && python3 -m venv .venv && source .venv/bin/activate \
  && pip install -r requirements.txt && uvicorn main:app --reload

# 3) Frontend (Terminal 2)
cd frontend && npm install && npm run dev
```

Uygulama: **http://localhost:5173** · API/Swagger: **http://localhost:8000/docs**

İlk açılışta **Veri Yükle** sayfasından `data/production_data.csv` dosyasını
yükleyin; sistem otomatik validasyon çalıştırır. `.env` olmasa bile uygulama
yerleşik mock API varsayılanlarıyla çalışır.

---

## Ekran Görüntüleri

> `docs/` altına eklenecek: Dashboard, Veri Yükle, Validasyon Raporu, Kayıp Analizi, API Gönderim, Ayarlar.

| Dashboard | Validasyon |
|-----------|-----------|
| KPI kartları + OEE trend, vardiya/istasyon kıyas, kalite dağılımı | Sınıflandırılmış hata listesi, kategori dağılımı, düzeltme modalı |

---

## Tespit Edilen Veri Kalitesi Sorunları

CSV'de **23+ farklı hata tipi** otomatik tespit edilir (toplam ~1.880 bulgu).
Tüm eşikler veritabanında saklanır ve **Ayarlar** sayfasından düzenlenebilir.

| Kural | Seviye | Adet | Örnek / Açıklama |
|-------|--------|------|------------------|
| `OEE_OUT_OF_RANGE` | warn/err | 543 | OEE>100 uyarı, >150 hata (rec 1091: OEE=348500) |
| `A_FORMULA_MISMATCH` | warning | 482 | A ≠ Çalışma/(Çalışma+Plansız), sapma >5 puan |
| `DEFECT_EXCEEDS_PRODUCTION` | error | 164 | Hatalı>Üretilen, fiziksel olarak imkânsız (rec 84: 94>79) |
| `MISSING_PRODUCT` | warning | 124 | Stok Adı boş |
| `ZERO_PROD_LONG_RUN` | error | 80 | Çalışma>60dk ama üretim 0 |
| `P_OUT_OF_RANGE` | warn/err | 37 | P>200 uyarı, >1000 hata |
| `Q_FORMULA_MISMATCH` | error | 15 | Q ≠ (Üretilen−Hatalı)/Üretilen·100 |
| `SYSTEMATIC_HIGH_P` | info | 14 | `ICA-2…Lower Bumper`+`IMM-4000-2`: tüm kayıtlarda P 4.000–348.500 (ideal çevrim süresi yanlış tanımlı) |
| `STATISTICAL_OEE_OUTLIER` | warning | ~34 | Ürün×istasyon grubunda OEE, median±3·IQR dışında (bağlamsal/istatistiksel anomali) |
| `PRODUCTION_RATE_OUTLIER` | info | ~48 | Ürün×istasyon grubunda üretim hızı (Üretilen/Çalışma) IQR dışında |
| `SENTINEL_VALUE` | error | 8 | MES `-10` placeholder (rec 869/921/1811 vb.) |
| `STOP_TIME_MISMATCH` | error | 8 | Duruş ≠ Planlı+Plansız |
| `SENTINEL_STOP_PATTERN` | warning | 8 | Çalışma=350 & Duruş=250 MES varsayılan deseni |
| `Q_OUT_OF_RANGE` | warn/err | 5 | Q<0 veya >120 (rec 388: Q=120, rec 2064: Q=−3) |
| `OEE_FORMULA_MISMATCH` | error | 3 | OEE ≠ A·P·Q/10000 |
| `MISSING_SHIFT / WORK_TIME / STOP_TIME / STATION` | error | 10/7/2/1 | Zorunlu alan boş |
| `MISSING_JOB_ORDER / WORK_CENTER` | warning | 10/12 | Opsiyonel alan boş |
| `INVALID_SHIFT_VALUE`, `NEGATIVE_*`, `STOP_NOT_CATEGORIZED`, `ZERO_PROD_SHORT_RUN` | — | — | Format / işaret / kategori kontrolleri |

**Yanlış pozitiflerden kaçınma:** Sentinel `-10` değeri yalnızca
`SENTINEL_VALUE` ile işaretlenir (negatiflik kuralları onu atlar). A-formül
toleransı 5 puana ayarlandı: medyan sapma 0.01 olduğundan formül doğrulanmış,
yalnızca gerçek tutarsızlıklar (>5 puan) raporlanır.

### Hatalı Kayıt Yönetimi
Tüm kayıtlar içe aktarılır, hatalılar işaretlenir. Kullanıcı her kaydı
**düzeltebilir** (`corrected`, yeniden doğrulanır), **reddedebilir**
(`rejected`), **gizleyebilir** (`is_hidden`). `rejected`/`hidden`/`error`
kayıtlar dashboard metriklerine **ve API gönderimine dahil edilmez** ama
veritabanından silinmez (geri alınabilir). Her değişiklik `audit_logs`'a yazılır.

---

## API Entegrasyon Akışı

Gönderim **gün × vardiya** bazında, yalnızca sayılabilir kayıtlar
(`clean`/`warning`/`corrected`, gizli değil) üzerinden:

```
oe_value               = ağırlıklı_ortalama(OEE, Çalışma Süresi), min(·,100) ile sınırlı
machine_count          = benzersiz istasyon sayısı (1–1000)
total_production_units = Σ Üretilen Miktar   (veri sözlüğüne göre fire dahil toplam)
production_date        = YYYY-MM-DD          (gelecek tarih reddedilir)
shift                  = 1 | 2 | 3
→ POST /api/v1/submit   header: X-Production-Key
```

- **Auth:** `X-Production-Key` header (`.env`).
- **Idempotency:** `sync_logs UNIQUE(production_date, shift)` — başarılı gönderim
  tekrar gönderilmez; kullanıcı açıkça "Yeniden Gönder" (force) demeli.
- **Retry:** 429 → `Retry-After` kadar bekle · 5xx/timeout → exponential backoff
  (2/4/8s, max 3 deneme) · 401/422/413 → retry yok, `detail` kullanıcıya gösterilir.
- **Mock-first:** Yerleşik `/mock/api/v1/submit` gerçek sözleşmeyi birebir
  taklit eder (401/422/413/200). Gerçek endpoint'e geçiş yalnızca `.env`
  (`API_BASE_URL`, `API_KEY`) değişikliğiyle olur — **kod değişmez**.

> **Önemli veri bulgusu:** Fire içeren 164 kaydın tamamı aynı zamanda
> `Hatalı>Üretilen` ihlali (error) içerir. Yani doğrulanmış veride kayıtlı fire
> efektif olarak **0**'dır — fire kolonu bütünüyle güvenilmezdir. Bu nedenle
> kalite görseli, fire oranı yerine **kayıt durum dağılımını** gösterir.

---

## Gelişmiş Özellikler

- **Asenkron / arka plan içe aktarma (100K+):** Yükleme isteği batch'i oluşturup
  anında döner; ağır içe aktarma + validasyon arka planda (toplu/bulk insert +
  SQLite WAL) çalışır, arayüz bir ilerleme çubuğuyla `GET /api/import/batches/{id}`
  durumunu yoklar (poll) ve bloklanmaz. 60.000 satır ~10s'de işlenir
  (`scripts/generate_mock_data.py` ile üretilen `data/production_data_50k.csv`).
- **İstatistiksel anomali tespiti:** Ürün×istasyon grubunda IQR tabanlı bağlamsal
  aykırı değer kuralları (`STATISTICAL_OEE_OUTLIER`, `PRODUCTION_RATE_OUTLIER`) —
  sabit eşiklerin kaçırdığı anomalileri yakalar; yalnızca tespit eder (otomatik
  düzeltme yok), warning/info şiddetinde, Ayarlar'dan kapatılabilir.
- **Kayıp Analizi (OEE Waterfall):** OEE'nin nerede kaybedildiğini gösteren
  kullanılabilirlik/performans/kalite kayıp şelalesi + planlı/plansız duruş
  dağılımı + istasyon bazlı kayıp tablosu (Six Big Losses'a doğru ilk adım).
- **Otomatik gönderim (zamanlanmış):** APScheduler ile opt-in (varsayılan kapalı)
  periyodik auto-sync — hazır gün/vardiyaları idempotent gönderir; "Şimdi Çalıştır"
  butonu da var.
- **Dashboard drill-down:** Grafikteki bir istasyon/vardiya/durum dilimine tıklayınca
  Kayıtlar sayfası ilgili filtrelerle açılır (URL parametreleriyle).
- **Uygulama içi uyarı merkezi:** Başlıktaki zil; başarısız gönderim, yüksek hata
  oranlı batch ve sistemik anomali uyarılarını canlı listeler.

---

## Mimari

```
backend/                         FastAPI + SQLAlchemy(async) + aiosqlite
  validation/   engine.py        kural-kayıt motoru: kuralları DB'den okur,
                rules.py          her kural bağımsız fonksiyon (Open/Closed)
  services/     import, record, report, validation, sync, scheduler
  api/          ince router'lar (import/record/validation/report/sync/settings/alerts/mock)
  models.py     7 tablo · seed.py  varsayılan kural kataloğu
frontend/                        React 18 + Vite + Ant Design 5 + Recharts
  pages/        Dashboard, ImportData, Records, ValidationReport, LossAnalysis,
                SyncManager, Settings
  components/   AppLayout, RecordDetailModal, ChartTooltip, ExportMenu, AlertBell, ...
data/           production_data.csv · production_data_50k.csv (60K, scale testi)
scripts/        generate_mock_data.py (büyük veri jeneratörü)
```

**Tasarım belkemiği (SOLID):**
1. **Kural-kayıt motoru** — her validasyon kuralı tek bir arayüzü uygular
   (`check(record, cfg) -> findings`); eşik/şiddet/aktiflik DB'den okunur.
   Yeni kural eklemek = bir fonksiyon + bir seed satırı. Ayarlar UI'ı sadece
   `validation_rules` tablosu üzerinde CRUD.
2. **Servis katmanı + ince router'lar** — tüm mantık servislerde, router'lar
   yalnızca request/response.
3. **API-client stratejisi** — mock vs gerçek tamamen konfigürasyon.

**Veritabanı (7 tablo):** `production_records` (orijinal satır JSON olarak
saklanır — data lineage), `validation_errors`, `validation_rules` (dinamik),
`audit_logs`, `import_batches` (SHA-256 ile duplicate kontrol + ilerleme alanları),
`sync_logs`, `app_settings` (auto-sync yapılandırması).

---

## Kütüphane Seçimleri ve Gerekçeleri

| Katman | Tercih | Gerekçe |
|--------|--------|---------|
| Backend | **FastAPI** | Async, otomatik Swagger, Pydantic tip güvenliği; case'de önerilen |
| ORM | **SQLAlchemy 2.0 + aiosqlite** | Async SQLite, olgun ekosistem |
| Veri | **pandas** | Chunked okuma (100K+), encoding/tip dönüşümü, grup istatistikleri |
| HTTP | **httpx** | Async client, timeout/retry |
| Zamanlama | **APScheduler** | Opt-in periyodik auto-sync (uygulama yaşam döngüsünde) |
| Test | **pytest + pytest-asyncio** | 37 test (validasyon ağırlıklı) |
| Frontend | **React + Vite** | SPA, anlık filtreleme; case'de tercih edilen |
| UI | **Ant Design 5** | Enterprise Table/Form/Filter, TR locale, dark; case FAQ'da onaylı |
| Grafik | **Recharts** | React-native, responsive |
| Export | **jsPDF + autotable** | İstemci tarafı PDF (CSV native Blob) |

---

## Test

```bash
cd backend && pytest -q       # 37 test: validasyon kuralları, import, kayıt, agregasyon, sync, endpoint, istatistiksel anomali, auto-sync, kayıp analizi
```

In-memory SQLite fixture ile her test izole. Validasyon kuralları için her kural
geçerli/uyarı/hata senaryolarıyla ve gerçek veri vakalarıyla (rec 388, 1091, 84
vb.) test edilir; "temiz kayıt hiçbir kuralı tetiklemez" testi yanlış pozitifi
korur.

---

## Yapamadıklarım / Daha Fazla Zaman Olsaydı

- **Gerçek API doğrulaması**: mock ile geliştirildi; gerçek endpoint anahtarıyla
  uçtan uca demo `.env` değişikliğiyle yapılabilir.
- **PDF Türkçe glifleri**: jsPDF'te ASCII'ye transliterasyon yapılıyor (gömülü
  Unicode font yerine) — okunur ama Türkçe karakterler sadeleştirilmiş.
- **Duruş neden kodları + Pareto**: veride neden kodu yok; MES'ten gelirse Kayıp
  Analizi tam **Six Big Losses**'a genişler (bkz. `docs/BONUS_VE_YOL_HARITASI.md`).
- **Kimlik doğrulama/çok kullanıcılı** kapsam dışı (tek operatör MVP); API anahtarı
  şimdilik `.env`, ileride secrets manager.
- Daha derin ölçek (≥500K): arka plan içe aktarma hazır; Postgres'e geçiş ve
  kalıcı iş kuyruğu (Celery) ile büyütülebilir.

> Not: Async/background import (100K+), istatistiksel anomali tespiti, OEE kayıp
> şelalesi, zamanlanmış auto-sync, dashboard drill-down ve uyarı merkezi **Milestone
> 2 kapsamında tamamlandı** (yukarıdaki "Gelişmiş Özellikler").
