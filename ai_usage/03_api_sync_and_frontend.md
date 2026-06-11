# 03 — Kayıt/Rapor API'leri, Frontend ve API Gönderim

**AI:** Claude Code (Claude Opus) · **Aşama:** Adım 4–7

## Backend API (Adım 4)
Kayıt filtreleme/düzeltme/durum/audit + dashboard agregasyonları (rejected/hidden/
error hariç) + validasyon raporu. ASGI ile in-process duman testi: upload→validate
(2117), 409 duplicate, tüm rapor uçları, filtreli kayıtlar, düzelt→re-validate,
reddet→audit — hepsi 200.

**Gerçek bir mühendislik içgörüsü (bug değil):** `total_defect = 0` çıktı. Claude
araştırdı: fire içeren 164 kaydın **tamamı** aynı zamanda `Hatalı>Üretilen` ihlali
(error) → doğrulanmış veride kayıtlı fire efektif 0; fire kolonu bütünüyle
güvenilmez. Bunu boş bir donut yerine **kayıt durum dağılımı** görseline çevirdik.

## Mock API + Gönderim (Adım 7)
- Mock `/mock/api/v1/submit` gerçek sözleşmeyi taklit eder.
- **Bulduğumuz bug:** gelecek tarih 422 yerine **500** dönüyordu. Sebep: Pydantic
  v2 `errors()` ham `ValueError`'ı `ctx`'e gömüyor, JSON serileştirme patlıyordu.
  Detayı serileştirilebilir alanlara indirgeyerek düzeltildi → 422.
- Idempotency `UNIQUE(date,shift)` ile; gün×vardiya matrisi, önizleme, retry/backoff.

## Frontend (Adım 5–6)
Ant Design (dark + TR) kabuk; Dashboard (5 KPI + 4 Recharts), Kayıtlar (tüm
filtreler), Import, Validasyon raporu + düzeltme modalı. Claude her sayfayı
**önizlemede ekran görüntüsüyle** kendi doğruladı (canlı veriyle OEE 86.5%,
Temiz oran %39 = 823/2117 ✓).

## Örnek istemler
> "Step 4'e geç ki Swagger'dan test edebileyim." ·
> "Frontend de eşit derecede önemli; grafikler doğru ve şık görünmeli." ·
> "total_defect=0 — bu bir bug mı?"
