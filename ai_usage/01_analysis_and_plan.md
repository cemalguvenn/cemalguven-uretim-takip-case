# 01 — Analiz ve Plan

**AI:** Claude Code (Claude Opus)

## Amaç
Case study PDF'i ve `production_data.csv` dosyasını analiz edip, hazırladığım
taslak uygulama planını değerlendirici beklentileriyle hizalanmış nihai bir
plana dönüştürmek.

## Yapılanlar
- PDF metni çıkarıldı; değerlendirme ağırlıkları, API sözleşmesi ve zorunlu
  teslimatlar teyit edildi (Validasyon %25, API %15, …).
- CSV ham veride hata sayıları **doğrulandı** (kod ile sayım): sentinel `-10`=8,
  P>200=37, OEE>100=543, Hatalı>Üretilen=166, tümü-sıfır=386, 350/250 deseni=8,
  sistemik ICA-2/IMM-4000-2 kombinasyonu=14, tekrar kayıt=0.
- Önemli düzeltmeler: gerçek API endpoint'inin var olduğu, idempotency'nin zorunlu
  olduğu, A/Q/OEE formülleri; kolonların **pozisyon bazlı** eşlenmesi gerektiği
  (başlıklar cp1254 altında bozuk).
- SOLID, adım-adım inşa sırası kararlaştırıldı.

## Örnek istem (özet)
> "Bu 2 dökümanı incele, taslak planımı değerlendir ve nihai bir plan çıkar."
