# 04 — Güvenlik İncelemesi ve Case Uyum Tamamlama

**AI:** Claude Code (Claude Fable)

## Amaç
Teslim öncesi son kontrol: (1) güvenlik/zafiyet taraması, (2) case study PDF'i
ile mevcut uygulamanın gereksinim-gereksinim karşılaştırılması ve tespit edilen
eksiklerin kapatılması.

## Yapılanlar
- **Güvenlik taraması** (statik inceleme): SQL injection / XSS / tehlikeli
  primitifler temiz; `.env` hijyeni doğru. Bulgular `PROJECT_SECURITY_REPORT.md`
  dosyasına yazıldı. Sınırsız dosya yükleme (bellek tüketimi) düzeltildi:
  upload artık 1 MB'lık parçalarla okunur, `max_upload_mb` (varsayılan 50 MB)
  aşılırsa 413 döner. Auth bilinçli olarak kapsam dışı (yerel tek kullanıcı MVP).
- **Uyum denetimi**: PDF madde madde kontrol edildi → `CASE_COMPLIANCE_CHECKLIST.md`.
  Tespit edilen eksikler ve kapatılması:
  - **Yükleme öncesi önizleme (§5.1 zorunlu)**: ilk 10 satır istemci tarafında
    okunup (UTF-8 → Windows-1254 geri dönüşü) onay tablosunda gösteriliyor;
    yükleme yalnızca "Yükle ve Doğrula" ile başlıyor. Gerçek CSV ile uçtan uca
    doğrulandı (Playwright + Chrome).
  - **`DUPLICATE_RECORD` kuralı (§5.4 ipucu kategorisi)**: batch düzeyinde,
    aynı `record_id` VEYA aynı iş anahtarı (Tarih+Vardiya+İstasyon+İş Emri+Stok);
    tüm kopyalar ikiz CSV satır numaralarıyla işaretlenir. Bu veri setinde 0
    bulgu (yanlış pozitif yok — kod ile doğrulandı), 3 birim testi eklendi.
  - **`JOB_ORDER_FORMAT` kuralı**: veri sözlüğündeki "302 + 7 hane" formatı;
    bu veri setinde 0 bulgu, 1 birim testi.
  - **README ekran görüntüleri (§7.1 zorunlu)**: çalışan uygulamadan 8 ekran
    görüntüsü alınıp `docs/screenshots/` altına kaydedildi ve README'ye gömüldü.
  - Çoklu CSV birleştirme yapılmadı; README "Yapamadıklarım" bölümünde dürüstçe
    belirtildi.
- Test sayısı 37 → **41** (tümü geçiyor); kural kataloğu 29 → **31**.

## Örnek istemler (özet)
> "Projeyi zafiyet ve güvenlik açısından incele; projenin nasıl çalıştığını,
> veri kalitesini, validasyonları ve Q/P/OEE metriklerini açıklayan bir rapor çıkar."
> "Case study PDF'i ile projeyi karşılaştır — istedikleri proje bu mu, eksik
> özellik var mı?" → "Eksikleri tamamla."
