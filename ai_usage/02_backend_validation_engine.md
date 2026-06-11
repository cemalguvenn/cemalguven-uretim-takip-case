# 02 — Backend Çekirdeği ve Validasyon Motoru

**AI:** Claude Code (Claude Opus) · **Aşama:** Adım 0–3 (en yüksek ağırlıklı %25)

## Yürütme ritmi: yaz → çalıştır → sayıları göster → sonraki adım
1. **İskelet + DB:** FastAPI, 6 tablolu şema, async engine. Çalıştırıldı: tablolar
   oluştu, 27 kural seed edildi, idempotent re-seed (2. çalıştırma 0 ekledi).
2. **CSV import:** cp1254 encoding kademesi, **pozisyon bazlı** 18-kolon eşleme,
   SHA-256 duplicate, orijinal satırın JSON saklanması (lineage). Gerçek dosyada
   doğrulandı: 2117 satır, Türkçe karakterler sağlam, boş-değer sayıları (vardiya
   10, stok 124, çalışma 7) referansla eşleşti.
3. **Validasyon motoru:** kural-kayıt deseni; eşikler DB'den okunur, iki-katmanlı
   şiddet, batch-seviyesi sistemik anomali.

## Pair-programming'in en net göründüğü an: yanlış pozitif avı
Motoru gerçek veriye çalıştırınca Claude **kendi çıktısını sorguladı**:
- `A_FORMULA_MISMATCH` 625 satır işaretliyordu → "bu yanlış pozitif olabilir."
  Sapma dağılımını çıkardı: **medyan 0.01** (formül doğru!), ama gerçek bir kuyruk
  var. Toleransı 5 puana çekerek yuvarlama gürültüsünü eledi, 482 gerçek
  tutarsızlığı tuttu.
- `SYSTEMATIC_HIGH_P` 0 çıktı (14 beklerken). Sebebi buldu: ICA grubunda 2 satırda
  P=0 olduğu için "hepsi yüksek" koşulu çöküyordu → kuralı "grubun ≥%80'i"
  olarak sağlamlaştırdı → tam 14.

Bu, brief'in "yanlış pozitifler puan kaybettirir" uyarısına doğrudan yanıt: AI
ürettiğini körü körüne bırakmadı, ben de bu kalibrasyonları onayladım.

## Test
`test_validation_rules.py`: her kural için geçerli/uyarı/hata + **gerçek veri
vakaları** (rec 388 Q=120, rec 1091 OEE=348500, rec 84 Hatalı>Üretilen) +
"temiz kayıt hiçbir kuralı tetiklemez" yanlış-pozitif koruması.

## Örnek istemler
> "Validasyon motorunu kur ve gerçek CSV'ye karşı sayımları doğrula." ·
> "A_FORMULA neden 625 satır işaretliyor — yanlış pozitif mi?" ·
> "Sistemik anomali neden tetiklenmiyor?"
