# 04 — Frontend İnceleme Döngüsü (somut geri bildirim → düzeltme)

**AI:** Claude Code (Claude Opus) · **Aşama:** UI cilası + dinamik kurallar

Bu dosya, eşli programlamanın en görünür kısmını gösterir: ben uygulamayı
tıklayıp **somut geri bildirim** verdim, Claude her maddeyi uygulayıp önizlemede
kanıtladı.

## Verdiğim geri bildirim → Claude'un yaptığı

1. **"İstasyon OEE grafiği hover'da değeri göstermiyor."**
   → Tüm grafiklere tutarlı özel tooltip (`ChartTooltip`) + cursor eklendi.
2. **"Hover animasyonları biraz sert, yumuşatalım."**
   → Kart hover geçişleri (translateY + gölge) + Recharts animasyon süresi/easing.
3. **"Detay modalındaki alanlar geliştirilebilir; vardiya, filtredeki gibi
   dropdown olmalı — şu an tek tek artıran sayı kutusu."**
   → Vardiya & istasyon **dropdown**'a çevrildi; metrikler birim ekleriyle
   (%/dk/adet) gruplandı.
4. **"Validasyonda kuralları ayarlayıp güncelleyebilmeliyiz — bunu konuşmuştuk
   ama göremiyorum."**
   → Eksik olan **dinamik kural editörü** (Ayarlar sayfası: eşik/şiddet/aktiflik
   + "Tüm Verileri Yeniden Doğrula" + "Sıfırla") backend + UI olarak eklendi;
   Validasyon sayfasından "Kuralları Yönet" bağlantısı kondu.

Her turda Claude değişikliği yapıp önizlemeyi yeniden ekran görüntüsüyle gösterdi;
ben onaylayınca bir sonraki maddeye geçildi. Bir noktada Recharts tooltip'ini
sentetik olayla doğrulayamayınca **bunu dürüstçe belirtti** ve benden manuel teyit
istedi — abartılı "çalışıyor" demedi.

## Örnek istemler
> "1- istasyon OEE hover'da oran göstermiyor. 2- hover animasyonları sert.
> 3- modal alanları geliştirilebilir, vardiya dropdown olmalı. 4- kuralları
> ayarlayabilmeliyiz." · "looks good, devam."
