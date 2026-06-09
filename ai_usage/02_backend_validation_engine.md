# 02 — Backend & Validasyon Motoru

**AI:** Claude Code (Claude Opus)

## Amaç
FastAPI iskeleti, 6 tablolu şema, CSV import ve **dinamik validasyon motoru**
(projenin en yüksek ağırlıklı %25'i) ile kapsamlı testleri kurmak.

## Yapılanlar
- `models.py` (6 tablo), `database.py` (async engine), `seed.py` (27 kural kataloğu).
- `import_service.py`: cp1254 encoding kademesi, pozisyon bazlı 18-kolon eşleme,
  SHA-256 duplicate kontrolü, orijinal satırın JSON olarak saklanması (lineage).
- `validation/rules.py` + `engine.py`: kural-kayıt deseni; eşikler DB'den okunur,
  iki-katmanlı şiddet (OEE/P/Q/çalışma), batch-seviyesi sistemik anomali.
- **Kalibrasyon:** A-formül toleransı 5.0'a çekildi (yanlış pozitif önleme,
  medyan sapma 0.01 → formül doğrulandı); sistemik kural grup içi ≥%80 P kriteri
  (ICA grubundaki 2 sıfır-P satırına dayanıklı).
- Sonuç gerçek veride doğrulandı: 21 farklı hata tipi, sayımlar referansla eşleşti.
- `pytest`: 15 validasyon kuralı testi (geçerli/uyarı/hata + gerçek vakalar) +
  import/kayıt/endpoint testleri.

## Örnek istemler (özet)
> "Adım adım, SOLID, önce çekirdek." · "Validasyon motorunu kur ve gerçek CSV'ye
> karşı sayımları doğrula." · "A_FORMULA neden 625 satır işaretliyor, yanlış
> pozitif mi?"
