# 03 — API Gönderim & Frontend

**AI:** Claude Code (Claude Opus)

## Amaç
Kayıt/rapor API'lerini, React arayüzünü (Dashboard, Kayıtlar, Validasyon,
Ayarlar) ve gün × vardiya API gönderim akışını tamamlamak.

## Yapılanlar
- **Backend API:** kayıt filtreleme/düzeltme/durum/audit, dashboard agregasyonları
  (rejected/hidden/error hariç), validasyon raporu, dinamik kural yönetimi
  (`settings_routes`), mock API (`/mock/api/v1/submit`) ve `sync_service`
  (ağırlıklı OEE, idempotency, retry/backoff).
- **Frontend:** Ant Design 5 (dark + TR locale) kabuk; Recharts ile OEE trend,
  vardiya/istasyon kıyas, kalite dağılımı; kayıt tablosu + tüm filtreler;
  düzeltme modalı (dropdown vardiya/istasyon, birimli alanlar); Ayarlar kural
  editörü; gün × vardiya gönderim matrisi + önizleme + geçmiş; CSV/PDF export.
- **Doğrulama:** tüm sayfalar canlı veriyle önizlemede görsel olarak teyit edildi;
  mock API hata kodları (401/422/413/200) ve sync idempotency uçtan uca test edildi.

## Geri bildirimle iyileştirmeler
- Grafik tooltip'leri tutarlı/özelleştirilmiş hale getirildi (istasyon hover).
- Kart hover geçişleri yumuşatıldı.
- Düzeltme modalında vardiya/istasyon dropdown'a çevrildi, birim ekleri eklendi.
- Dinamik kural editörü (Ayarlar) eklendi + Validasyon sayfasından bağlantı.

## Örnek istemler (özet)
> "Frontend de eşit derecede önemli; grafikler doğru ve şık görünmeli." ·
> "Validasyon'da kuralları güncelleyebilmeliyiz." · "Gerisi için devam et."
