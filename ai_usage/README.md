# AI Kullanım Şeffaflığı

Bu proje, **Claude Code (Anthropic — Claude Opus)** ile **eşli programlama
(pair-programming)** yöntemiyle geliştirildi. Bu klasör, yapay zekayı yazılım
geliştirmede *nasıl* kullandığımı — mimariden yürütmeye kadar — adım adım ve
dürüstçe belgeler. Amaç: değerlendiricinin iş birliğinin ritmini net görmesi.

> **Tam sohbet kayıtları:** Aşağıdaki özetler, uzun oturumların okunabilir bir
> haritasıdır. Ham transcript / paylaşım linki bu klasöre eklenecektir. Mülakatta
> kodun her satırını açıklayabilecek düzeyde gözden geçirildi; AI çıktısı
> anlaşılmadan commit edilmedi.

## İş Birliği Modeli (kim ne yaptı)

| Ben (mühendis) | Claude (AI) |
|----------------|-------------|
| Hedefi, kapsamı ve önceliği belirledim ("önce çekirdek, SOLID, adım adım") | Kararları seçeneklerle sundu, gerekçelendirdi, ben onayladıktan sonra uyguladı |
| Mimari ve ürün kararlarını verdim (mock-first API, durum makinesi, kapsam kesimleri) | Her adımı **gerçek veriye karşı doğrulayıp** sayıları gösterdi (varsayım değil) |
| UI/UX ve davranış üzerine somut geri bildirim verdim | Geri bildirimi tek tek uyguladı, önizlemede ekran görüntüsüyle kanıtladı |
| Güvenlik sertleştirme, batch filtreleme, iş-emri format kuralı gibi parçaları **doğrudan kendim** ekledim/değiştirdim | Hata ayıkladı (ör. 30s performans regresyonunu profil çıkararak buldu) |

**Karar mekanizması:** Belirsiz her noktada Claude bana çoktan seçmeli sorular
sordu (plan modunda `AskUserQuestion`), ben karar verdim, sonra yürütüldü. Körü
körüne kod üretip kabul etme olmadı.

## Doğrulama Disiplini (en önemli alışkanlık)

Her adım "yazıldı → **çalıştırıldı/test edildi** → sayılar gösterildi → bir sonraki
adım" döngüsüyle ilerledi:
- İçe aktarma yazıldı → gerçek CSV ile 2117 satır + boş-değer sayıları doğrulandı.
- Validasyon motoru yazıldı → kural-bazlı sayımlar, elle doğrulanmış referansla
  birebir karşılaştırıldı (ör. OEE>100=543, sentinel=8).
- Frontend yazıldı → önizlemede ekran görüntüleriyle kontrol edildi.
- Testler her aşamada yeşil tutuldu (son durumda **41 test**).

## Dosyalar (kronolojik)

1. `01_analysis_and_plan.md` — Dökümanların analizi, planın gerçeğe göre düzeltilmesi, kapsam kararları
2. `02_backend_validation_engine.md` — Şema, import, **validasyon motoru** (%25) ve kalibrasyon döngüsü
3. `03_api_sync_and_frontend.md` — Kayıt/rapor API'leri, React arayüzü, mock API + gönderim
4. `04_frontend_review_loop.md` — UI geri bildirim döngüsü (somut düzeltmeler)
5. `05_milestone2_enhancements.md` — Yeniden planlama, performans teşhisi, gelişmiş özellikler
6. `04_security_review_and_case_gap_fixes.md` — Teslim öncesi güvenlik taraması + case uyum denetimi ve eksik kapatma (kronolojik olarak en son adım; `PROJECT_SECURITY_REPORT.md` ve `CASE_COMPLIANCE_CHECKLIST.md` çıktıları)

## Hangi prompt → hangi AI
Geliştirmenin büyük kısmı **Claude Code (Claude Opus)** ile yapıldı; teslim öncesi
güvenlik/uyum incelemesi pass'i **Claude Code (Claude Fable)** ile yürütüldü. Her
dosyanın başında kullanılan model ve ilgili "Örnek istem"ler belirtilmiştir.
