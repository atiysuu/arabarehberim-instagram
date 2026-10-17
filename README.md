# Araba Rehberim · Instagram paylaşımı

[arabarehberim.net](https://arabarehberim.net) için hazırlanan 1.546 Instagram
postunu, 176 Reels videosunu ve seslendirmeli videoları kendi kendine
paylaşır. GitHub Actions üzerinde çalışır; bilgisayarın kapalı olabilir.

```
sira.csv ──► scripts/paylas.py ──► Instagram Graph API ──► durum/paylasilanlar.jsonl
             (günde 1-2 kez)        (resmi yayınlama API'si)   (ne paylaşıldı, bağlantısı)
```

**Günlük düzen (Türkiye saati):**

| Saat | Ne | İş akışı |
|---|---|---|
| 13:37 | seslendirmeli video (`seslendirmeli/`) | "Instagram'a seslendirmeli video paylas" |
| 20:37 | seslendirmeli video (`seslendirmeli/`) | "Instagram'a seslendirmeli video paylas" |

2026-10-18'den itibaren yalnız seslendirmeli videolar paylaşılıyor; görsel
postlar ve `reels/` videoları durduruldu (Reels iş akışı yalnız elle çalışır).
`seslendirmeli/` boşsa ya da videolar bittiyse bu iki saati görsel post
doldurur (`paylas.yml` içindeki `YEDEK_SAATLER`).

- **Saatler:** yukarıdaki tablo. GitHub zamanlanmış
  işleri saatlerce geciktirebildiği, bazen hiç başlatmadığı için iş yarım
  saatte bir uyanır; saati gelmiş ama atılmamış post varsa onu atar. Kaçan
  saat bir sonraki uyanışta telafi edilir, iki post arasında en az 2 saat olur.
- **Sıra:** `sira.csv`. Seriler karışık gider (künye, kronik arıza, bakım
  takvimi, kritik arıza, marka, liste); her serinin içinde Türkiye'de en
  yaygın modeller önce gelir. İlk post site tanıtımı. Sırayı yeniden kurmak
  için `python3 scripts/sira_olustur.py`.
- **Süre:** günde 1 post (seslendirmeli videolar bitince 2).
- Görseller bu reponun `posts/` klasöründen, `raw.githubusercontent.com`
  adresinden Instagram'a verilir. Bu yüzden repo **public** kalmalı; içinde
  gizli bir şey yok.

## Reels

- **Saat:** her gün 13:37'den sonraki ilk uyanışta (Türkiye; iş saatte bir uyanır), iş akışı "Instagram'a Reels paylas".
- **Sıra:** `reels/sira.csv` (seriler dönüşümlü). 176 video, günde 1 → yaklaşık 6 ay.
- **Kayıt:** `durum/reels.jsonl`.
- Instagram videoyu kendisi indiriyor. O günün videosu önce bu reponun
  `reels-barinak` release'ine yüklenir, adresi oradan verilir (catreels'te
  Instagram'ın bu adresten Reels indirdiği doğrulandı). Release'te yalnızca son 5 video tutulur, eskileri
  silinir (Instagram'daki Reels etkilenmez). Kapak görseli `-kapak.jpg`
  raw adresinden gider.
- Ek secret gerekmez; release için iş akışının kendi `GITHUB_TOKEN`'ı yeter.

## Seslendirmeli videolar

- `seslendirmeli/` klasörü `reels/` ile aynı düzende: mp4 + açıklama `.txt` +
  `-kapak.jpg`, sıra `seslendirmeli/sira.csv` (sütunlar `sira,video,aciklama,kapak`).
- Kayıt `durum/seslendirmeli.jsonl`. Aynı betik (`scripts/reels_paylas.py --klasor seslendirmeli`).

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

Reels için aynısı: **Actions → "Instagram'a Reels paylas" → Run workflow**.

- `kontrol` işaretli: paylaşım yapmaz; token hangi hesaba bağlı ve kota ne, onu yazar.
- `kuru` işaretli: Instagram'a dokunmaz; sıradaki postların görsel adreslerini
  ve açıklamalarını kontrol eder.
- `adet`: kaç post atılacağı (varsayılan 1).

## Durdurma ve sıklık

- Durdurmak: **Actions → "Instagram'a paylas" → ··· → Disable workflow**.
  Açınca kaldığı yerden devam eder.
- Günde kaç post: `.github/workflows/paylas.yml` içindeki
  `PAYLASIM_SAATLERI: "09:37,13:37,20:37"` (Türkiye saati). Örneğin
  `"10:37,20:37"` günde iki post demek.

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
scripts/reels_paylas.py             Reels paylaşımı
reels/                              Reels videoları, kapakları, açıklamaları ve sira.csv
durum/reels.jsonl                   paylaşılan Reels
```

Postlar Araç Rehberim projesindeki Instagram üreticisinden gelir. Şablon
değişip seri yeniden basılırsa yeni dosyalar `posts/` altına aynı adlarla
konur; paylaşılanlar klasör adıyla tutulduğu için tekrar gitmez.
