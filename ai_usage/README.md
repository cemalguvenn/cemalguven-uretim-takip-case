# AI Kullanım Şeffaflığı

Bu proje, **Claude Code (Anthropic, Claude Opus)** yapay zeka asistanı ile
eşli-programlama (pair-programming) yaklaşımıyla geliştirilmiştir. Aşağıdaki
dosyalar her aşamada AI'ın hangi amaçla kullanıldığını özetler.

> **Not (aday için):** Tam sohbet geçmişini (ekran görüntüsü / paylaşım linki /
> text dump) bu klasöre ekleyin. Aşağıdaki dosyalar, değerlendiriciye hızlı bir
> harita sunmak için aşama-aşama özetlerdir. Mülakatta kodun her satırını
> açıklayabilecek düzeyde gözden geçirilmiştir.

## Kullanım İlkesi
- AI; analiz, iskelet üretimi, kural motoru tasarımı ve UI bileşenleri için
  kullanıldı. Üretilen her çıktı çalıştırılarak (pytest, canlı önizleme,
  gerçek CSV üzerinde doğrulama) teyit edildi.
- Mimari kararlar (kural-kayıt motoru, mock-first API, durum makinesi) AI ile
  tartışılarak gerekçelendirildi; körü körüne kopyalama yapılmadı.

## Dosyalar
- `01_analysis_and_plan.md` — Veri/PDF analizi ve uygulama planının netleştirilmesi
- `02_backend_validation_engine.md` — Şema, import, validasyon motoru, testler
- `03_api_sync_and_frontend.md` — Kayıt/rapor API'leri, React arayüzü, API gönderim
