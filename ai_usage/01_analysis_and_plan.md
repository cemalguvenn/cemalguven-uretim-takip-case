# 01 — Analiz ve Mimari Planlama

**AI:** Claude Code (Claude Opus) · **Aşama:** Başlangıç → onaylı plan

## Nasıl başladık
Klasöre case study PDF'i, `production_data.csv` ve **kendi taslak uygulama planımı**
koydum. İlk istemim şuydu (özet):

> "İki döküman var: PDF projeyi, CSV mock veriyi içeriyor. Bir de taslak planım
> var ama eksik olabilir. Dosyalara ve planıma bak, nihai bir plan çıkar."

## Claude'un yaptıkları (sadece okuyup özetlemek değil — doğruladı)
1. PDF metnini çıkardı; **değerlendirme ağırlıklarını** ve API sözleşmesini teyit
   etti (Validasyon %25, API %15, …).
2. **CSV'yi kodla taradı** ve taslağımdaki hata sayılarını doğruladı:
   sentinel −10 = 8, P>200 = 37, OEE>100 = 543, Hatalı>Üretilen = 166,
   tümü-sıfır = 386, 350/250 deseni = 8, sistemik ICA/IMM-4000-2 = 14, tekrar = 0.
   *(Önemli: bunlar varsayım değil, çalıştırılmış sayımlardı.)*
3. Planımdaki **eksikleri/yanlışları düzeltti:** gerçek API endpoint'inin var
   olduğu, idempotency'nin zorunlu olduğu, OEE/A/Q formülleri ve başlık satırı
   cp1254 altında bozuk olduğundan kolonların **pozisyon bazlı** eşlenmesi gerektiği.

## Benim verdiğim kararlar (Claude sordu, ben seçtim)
Plan modunda bana çoktan seçmeli sorular soruldu; seçimlerim:
- **Kapsam:** "Her şeyi istiyoruz ama dikkatli; adım adım, SOLID ilerleyelim ki
  ekstralar mevcut özellikleri bozmadan eklenebilsin."
- **API:** Mock-first, `.env` ile gerçek API'ye geçişe hazır.
- **Frontend:** React + Vite + Ant Design + Recharts.

## Çıktı
Bu kararlar, gerekçeli ve doğrulanmış nihai bir plana dönüştü: **kural-kayıt
motoru + servis katmanı + API-client stratejisi** belkemiği üzerine, çekirdeği
önce biten, ekstraların additive eklendiği 0–9 adımlık inşa sırası.

## Örnek istemler
> "Let's see what kind of plan we come up." ·
> "Go for everything asked, including extras, but careful — step by step, SOLID." ·
> "Mock-first, real-ready via .env."
