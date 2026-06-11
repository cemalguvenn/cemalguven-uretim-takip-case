# 05 — Milestone 2: Yeniden Planlama ve Performans Teşhisi

**AI:** Claude Code (Claude Opus) · **Aşama:** MVP sonrası geliştirmeler

MVP bitince yol haritasını birlikte gözden geçirdik. Ben hangi maddelerin gerekli
olduğunu tartışmak istedim; Claude **plan moduna** geçip her öneriyi değerlendirdi
ve kapsam için bana sorular sordu.

## Kapsamı birlikte daralttık (önemli düzeltmeler)
- **"Veri kalitesi" = otomatik düzeltme DEĞİL.** Ben netleştirdim: "Anomalileri
  daha iyi/etkili tespit etmek istiyoruz; veri düzeltmek/doldurmak değil." →
  Claude yönü değiştirdi: kural-tabanlı motoru tamamlayan **istatistiksel/bağlamsal
  IQR aykırı değer** tespiti (otomatik düzeltme yok).
- **Gönderimi her vardiya sonrası otomatikleştirme.** "Cronjob veya event trigger
  kullanabiliriz." → APScheduler ile opt-in zamanlanmış auto-sync.
- "Mimari/ölçek eklentisi istemiyoruz" dedim → Kafka/Postgres/RBAC kapsam dışı
  bırakıldı; iyileştirmeler mevcut stack içinde kaldı.

## Pair-programming'in zirvesi: 30 saniyelik regresyonu profil çıkararak bulmak
100K performansı için toplu (bulk) insert'e geçtik. İlk ölçümde **validasyon 16s →
37s'ye çıktı** (regresyon!). Claude tahmin etmek yerine alt adımları zamanladı:

```
batch_level: 0.3s · rule loop: 1.0s · insert findings: 5.2s · status update: 29.7s
```

Darboğaz netti: `UPDATE ... WHERE id IN (500)` 120 kez = 29.7s. **executemany
update-by-PK**'ya geçince 60K toplam ~30s → **~10.5s**. (Bu ders hafızaya da
yazıldı ki tekrarlanmasın.)

## Benim doğrudan katkılarım (sadece AI değil)
Bu aşamada kodun bazı parçalarını **kendim** ekledim/değiştirdim — gerçek bir
ortak çalışma:
- Yükleme boyutu sınırı (`max_upload_mb`) — bellek tüketimi/DoS koruması.
- Validasyon ve kayıt uçlarına **batch_id** filtreleme.
- İş-emri format kuralı (`JOB_ORDER_FORMAT`, 302 + 7 hane) ve ilgili test.

## Doğrulama
37 birim testi yeşil; async upload 0.01s'de dönüyor (UI bloklanmıyor); Kayıp
Analizi waterfall, drill-down, uyarı zili önizlemede ekran görüntüleriyle teyit
edildi.

## Örnek istemler
> "100K performansa bakılmalı. UI bloklanması büyük sorun — async/background.
> Six Big Losses waterfall ekleyelim. Veri kalitesi = daha iyi anomali tespiti,
> düzeltme değil. Gönderimi cron/event ile otomatikleştirelim."
