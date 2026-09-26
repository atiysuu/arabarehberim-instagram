# Araba Rehberim · Instagram paylaşımı

[arabarehberim.net](https://arabarehberim.net) için hazırlanan 1.546 Instagram
postunu sırayla, günde üç kez kendi kendine paylaşır. GitHub Actions üzerinde
çalışır; bilgisayarın kapalı olabilir.

```
sira.csv ──► scripts/paylas.py ──► Instagram Graph API ──► durum/paylasilanlar.jsonl
             (günde 3 kez)          (resmi yayınlama API'si)   (ne paylaşıldı, bağlantısı)
```

- **Saatler:** her gün yaklaşık 09:37, 13:37 ve 20:37 (Türkiye). GitHub
  zamanlanmış işleri yoğunlukta birkaç dakika geciktirebilir.
- **Sıra:** `sira.csv`. Seriler karışık gider (künye, kronik arıza, bakım
  takvimi, kritik arıza, marka, liste); her serinin içinde Türkiye'de en
  yaygın modeller önce gelir. İlk post site tanıtımı. Sırayı yeniden kurmak
  için `python3 scripts/sira_olustur.py`.
- **Süre:** 1.546 post, günde 3 → yaklaşık 17 ay.
- Görseller bu reponun `posts/` klasöründen, `raw.githubusercontent.com`
  adresinden Instagram'a verilir. Bu yüzden repo **public** kalmalı; içinde
  gizli bir şey yok.

## Kurulum

Secrets → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Zorunlu | Ne için |
|---|---|---|
| `IG_ACCESS_TOKEN` | evet | Instagram'a paylaşım (60 günlük uzun ömürlü token) |
| `GH_PAT` | önerilir | Token yenilenince secret'ı güncellemek (fine-grained, yalnız bu repo, izin: Secrets → Read and write) |
| `IG_USER_ID` | hayır | Boş bırakılırsa tokenden bulunur |

`IG_ACCESS_TOKEN` girilmeden zamanlanmış iş hiçbir şey yapmaz, yalnız uyarı
yazar.

## Elle çalıştırma

**Actions → "Instagram'a paylas" → Run workflow**

- `kuru` işaretli: Instagram'a dokunmaz; sıradaki postların görsel adreslerini
  ve açıklamalarını kontrol eder.
- `adet`: kaç post atılacağı (varsayılan 1).

## Durdurma ve sıklık

- Durdurmak: **Actions → "Instagram'a paylas" → ··· → Disable workflow**.
  Açınca kaldığı yerden devam eder.
- Günde kaç post: `.github/workflows/paylas.yml` içindeki
  `cron: "37 6,10,17 * * *"` satırındaki saat listesi (UTC). Örneğin
  `"37 7,17 * * *"` günde iki post (10:37 ve 20:37 TR) demek.

## Güvenlik ağları

- **Aynı post iki kez gitmez.** Her paylaşım anında `durum/paylasilanlar.jsonl`
  dosyasına yazılır. Kayıt yazılamadan iş yarıda kalırsa bir sonraki tur,
  Instagram'daki son 25 postun açıklamasına bakıp aynı postu tekrar atmaz.
- **Bozuk post sırayı tıkamaz.** Instagram bir postun görsellerini iki kez
  işleyemezse post `atlandi` diye işaretlenir, sıra devam eder.
- **Kota.** Instagram'ın 24 saatlik yayın sınırı doluysa tur atlanır.
- **Token 60 günde ölür.** "Instagram tokenini yenile" işi her pazartesi
  yeniler ve bitiş tarihini `durum/token.json`'a yazar (token değil, yalnız
  tarih). Bitişe 14 günden az kalırsa paylaşım işi uyarı verir.
- Bir iş kırmızı yanarsa GitHub hesabınızdaki e-postaya bildirim gelir.

## Kaydırmalı postlar

Instagram'ın API'si kaydırmalı postta en fazla 10 görsel kabul ediyor. 11
görselli 10 kronik arıza postunda son arıza kartı
atlanır (sıralama ciddiyete göre olduğu için en hafif arıza), kapanış kartı kalır.

## Dosyalar

```
posts/<seri>/<sıra>-<araç>/NN.jpg   görseller (1080×1350)
posts/<seri>/<sıra>-<araç>/aciklama.txt   açıklama, site bağlantısı, fotoğraf atfı, hashtag
icerik-listesi.csv                  üreticinin seri seri listesi
sira.csv                            paylaşım sırası
durum/paylasilanlar.jsonl           paylaşılanlar (post, zaman, Instagram bağlantısı)
durum/token.json                    token bitiş tarihi
scripts/paylas.py                   paylaşım
scripts/token_yenile.py             token yenileme
scripts/sira_olustur.py             sırayı kurar
```

Postlar Araç Rehberim projesindeki Instagram üreticisinden gelir. Şablon
değişip seri yeniden basılırsa yeni dosyalar `posts/` altına aynı adlarla
konur; paylaşılanlar klasör adıyla tutulduğu için tekrar gitmez.
