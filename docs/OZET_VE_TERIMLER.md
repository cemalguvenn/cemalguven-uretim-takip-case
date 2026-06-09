# Proje Özeti, Terimler ve Notasyon

## 1. Bir Cümlede Proje
MES'ten gelen CSV üretim verisini içe aktaran, **veri kalitesi validasyonu**
yapan, hatalı kayıtların incelenip düzeltildiği/reddedildiği ve **yalnızca
doğrulanmış verinin** gün × vardiya bazında REST API'ye gönderildiği tam-stack
bir üretim performans takip MVP'si.

## 2. Akış (uçtan uca)
```
CSV Yükle → Otomatik Validasyon → İncele/Düzelt/Reddet/Gizle
          → (Kuralları Ayarla → Yeniden Doğrula) → API Gönderim (gün×vardiya)
          → CSV/PDF Export
```

## 3. OEE Matematiği (referans)
| Sembol | Ad | Tanım | Aralık |
|--------|----|-------|--------|
| **A** | Availability (Kullanılırlık) | `Çalışma / (Çalışma + Plansız Duruş) · 100` | 0–100 % |
| **P** | Performance (Performans) | İdeal hıza karşı gerçekleşen hız | 0–100 % (ideal) |
| **Q** | Quality (Kalite) | `(Üretilen − Hatalı) / Üretilen · 100` | 0–100 % |
| **OEE** | Overall Equipment Effectiveness | `A · P · Q / 10000` | 0–100 % (ideal) |

> Endüstri yorumu: OEE ≥ %85 "dünya standardı", %60 civarı tipik, %40 altı düşük.
> Veride P ve OEE'nin >100 çıkması ideal çevrim süresinin yanlış tanımlandığını
> (özellikle sistemik combo'da) gösteren bir veri kalitesi sinyalidir.

## 4. Kayıt Durum Makinesi (`status`)
```
pending ──(validasyon)──▶ clean | warning | error
error ──(kullanıcı düzeltir + re-validate)──▶ corrected ──▶ clean | warning
herhangi ──(reddet)──▶ rejected ──(geri al + re-validate)──▶ pending ──▶ …
clean|warning|corrected ──(API gönderim)──▶ submitted
```
- `is_hidden` durumdan **bağımsız** bir bayraktır (gizle/göster).
- **Sayılabilir** (dashboard + API'ye dahil) durumlar: `clean, warning, corrected,
  submitted` ve `is_hidden = false`. `error, rejected, pending, hidden` **hariç**.

## 5. Validasyon Kategorileri
`missing_value` · `sentinel` · `out_of_range` · `inconsistency` (formül/ilişki)
· `domain_logic` · `format` · `systematic`. Şiddet: **error > warning > info**;
kaydın durumu en yüksek şiddetten belirlenir. İki-katmanlı kurallar (OEE/P/Q/
çalışma) `warning_threshold` ile `error_threshold` arasında uyarı, üstünde hata
verir. Tüm eşikler `validation_rules` tablosunda, **Ayarlar** sayfasından canlı
düzenlenir.

## 6. API Sözleşmesi (notasyon)
```
POST /api/v1/submit                  Header: X-Production-Key: <key>
{
  "oe_value": float 0.0–100.0,       # ağırlıklı OEE, 100 ile sınırlı
  "machine_count": int 1–1000,       # benzersiz istasyon sayısı
  "shift": 1|2|3,                    # 1 Sabah · 2 Öğle · 3 Gece
  "total_production_units": int 1–1_000_000,  # Σ Üretilen (fire dahil)
  "production_date": "YYYY-MM-DD"    # gelecek tarih reddedilir
}
HTTP: 200 başarı · 401 anahtar · 422 validasyon(detail) · 429 rate-limit · 413 >10KB
```
**Idempotency:** `sync_logs UNIQUE(production_date, shift)` — başarılı gönderim
tekrar edilmez (force ile zorlanır).

## 7. Önemli Veri Bulguları (2.117 satır)
- **21+ farklı hata tipi**, ~1.833 bulgu. Sayımlar ham CSV ile doğrulandı.
- **Fire kolonu güvenilmez:** fire içeren 164 kaydın tamamı `Hatalı>Üretilen`
  ihlali → doğrulanmış veride efektif fire = 0.
- **Sistemik anomali:** `ICA-2…Lower Bumper` + `IMM-4000-2` kombinasyonunda tüm
  kayıtlarda P 4.000–348.500 (tekil hata değil, ideal çevrim süresi hatası).
- **MES sentinel'leri:** `-10` placeholder, `Çalışma=350/Duruş=250` deseni.
- **Kodlama:** Windows-1254; başlık satırı bozuk → kolonlar **pozisyon** ile eşlenir.

## 8. Sözlük (kısa)
- **MES**: Manufacturing Execution System — vardiya sonu CSV üretir.
- **İş emri (work order)**: bir satır = bir iş emri kaydı (vardiya değil).
- **Sentinel/placeholder**: gerçek değer yerine geçen MES kodu (ör. `-10`).
- **Data lineage**: orijinal CSV satırının (`original_data`) JSON olarak
  değişmeden saklanması; düzeltmeler kaynağı bozmaz.
- **Audit trail**: her düzenleme/reddetme/gizleme `audit_logs`'ta tutulur.
- **Idempotency**: aynı gün/vardiyanın hedef sistemde tekrarlanmaması.
- **Countable kayıt**: metriklere/gönderime dahil edilen kayıt (bkz. §4).

## 9. Çalıştırma (özet)
Backend `uvicorn main:app --reload` (:8000) · Frontend `npm run dev` (:5173) ·
Swagger `:8000/docs`. Büyük veri testi: `data/production_data_50k.csv` (60K satır,
`scripts/generate_mock_data.py` ile üretildi).
