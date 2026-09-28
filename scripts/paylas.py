"""Siradaki postu Instagram'a atar (resmi Content Publishing API, Instagram Login).

Akis:
  1) sira.csv'de durum/paylasilanlar.jsonl'de olmayan ilk postu bul
  2) gorsellerin herkese acik adresini kur ve ulasilabildigini dogrula
  3) tek gorsel: POST /{ig}/media (image_url)             -> bekle -> media_publish
     kaydirmali: her gorsel icin is_carousel_item container -> bekle
                 POST /{ig}/media (media_type=CAROUSEL, children) -> bekle -> media_publish
  4) sonucu durum/paylasilanlar.jsonl'e hemen yaz (is akisi sonra commit eder)

Gorseller bu reponun kendisinden, raw.githubusercontent.com adresinden
okunur; bu yuzden repo public olmali.

Kullanim:
  python3 scripts/paylas.py                 # siradaki 1 post
  python3 scripts/paylas.py --adet 3
  python3 scripts/paylas.py --kuru --adet 5 # Instagram'a dokunmadan kontrol
  python3 scripts/paylas.py --kontrol       # token hangi hesaba ait, kota ne

Ortam: IG_ACCESS_TOKEN (secret), istege bagli IG_USER_ID,
GITHUB_REPOSITORY + GITHUB_SHA (Actions verir) ya da GORSEL_TABAN.

Token hicbir zaman loga, dosyaya ya da hata mesajina yazilmaz.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
POSTLAR = KOK / "posts"
SIRA = KOK / "sira.csv"
DURUM = KOK / "durum" / "paylasilanlar.jsonl"
TOKEN_DURUM = KOK / "durum" / "token.json"

# IG_API_TABAN yalnizca yerel sahte sunucuyla test icin
API = os.getenv("IG_API_TABAN", "https://graph.instagram.com") + "/" + os.getenv("IG_API_VERSION", "v23.0")
KAYDIRMA_SINIRI = 10  # API'nin kaydirmali post basina kabul ettigi gorsel sayisi
ACIKLAMA_SINIRI = 2200
HASHTAG_SINIRI = 30


class IGHata(RuntimeError):
    def __init__(self, mesaj, kod=None):
        super().__init__(mesaj)
        self.kod = kod


def log(m):
    print(m, flush=True)


def uyari(m):
    print(f"::warning::{m}", flush=True)


def hata(m):
    print(f"::error::{m}", flush=True)


def ozet(m):
    yol = os.getenv("GITHUB_STEP_SUMMARY")
    if yol:
        with open(yol, "a", encoding="utf-8") as f:
            f.write(m + "\n")


# --- zamanlama -----------------------------------------------------------------
# GitHub zamanlanmis isleri saatlerce geciktirebiliyor, bazen hic baslatmiyor.
# Bu yuzden is akisi sik sik (yarim saatte bir) tetiklenir ve paylasim
# saatinin gelip gelmedigine burada bakilir: bugun gecilen saat sayisi,
# bugun paylasilan sayidan fazlaysa sira gelmistir. Kacan bir saat bir
# sonraki tetiklemede telafi edilir.

TR = dt.timezone(dt.timedelta(hours=3))


def zamani_geldi_mi(kayitlar, saatler, en_az_ara_dk, simdi=None):
    simdi = (simdi or dt.datetime.now(dt.timezone.utc)).astimezone(TR)
    gecen = 0
    for s in saatler.split(","):
        sa, dk = (int(x) for x in s.strip().split(":"))
        if simdi >= simdi.replace(hour=sa, minute=dk, second=0, microsecond=0):
            gecen += 1
    zamanlar = []
    for k in kayitlar:
        if k.get("durum") != "paylasildi" or not k.get("zaman"):
            continue
        try:
            zamanlar.append(dt.datetime.fromisoformat(k["zaman"]).astimezone(TR))
        except ValueError:
            continue
    bugun = sum(1 for z in zamanlar if z.date() == simdi.date())
    if bugun >= gecen:
        log(f"sira gelmedi: bugun {gecen} paylasim saati gecti, {bugun} paylasim yapildi")
        return False
    if zamanlar:
        ara = (simdi - max(zamanlar)).total_seconds() / 60
        if ara < en_az_ara_dk:
            log(f"son paylasimdan bu yana {ara:.0f} dk gecti; en az {en_az_ara_dk} dk bekleniyor")
            return False
    log(f"sira geldi: bugun {gecen} paylasim saati gecti, {bugun} paylasim yapildi")
    return True


# --- Instagram API --------------------------------------------------------

def _ipucu(kod, mesaj):
    m = (mesaj or "").lower()
    if kod == 190:
        return " -> Token gecersiz ya da suresi dolmus; IG_ACCESS_TOKEN secret'ini yenileyin."
    if kod in (10, 200) or "permission" in m:
        return " -> Izin eksik: instagram_business_basic ve instagram_business_content_publish gerekli."
    if kod in (4, 9, 17, 32, 613) or "limit" in m:
        return " -> Istek ya da 24 saatlik yayin kotasi dolmus."
    if "url" in m or "fetch" in m or "download" in m or "media" in m:
        return " -> Instagram gorseli indiremedi: repo public mi, adres aciliyor mu?"
    return ""


def _istek(yontem, yol, veri=None):
    token = os.environ["IG_ACCESS_TOKEN"]
    veri = dict(veri or {})
    url = f"{API}/{yol}"
    govde = None
    if yontem == "GET":
        url += "?" + urllib.parse.urlencode({**veri, "access_token": token})
    else:
        govde = urllib.parse.urlencode({**veri, "access_token": token}).encode()
    istek = urllib.request.Request(url, data=govde, method=yontem)
    for deneme in range(3):
        try:
            with urllib.request.urlopen(istek, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode()).get("error", {})
            except Exception:
                err = {}
            kod = err.get("code")
            mesaj = err.get("message", "")
            # Gecici sunucu hatalarinda bir daha dene, digerlerinde dur
            if (e.code >= 500 or err.get("is_transient")) and deneme < 2:
                time.sleep(10 * (deneme + 1))
                continue
            raise IGHata(f"{yontem} {yol.split('?')[0]} -> HTTP {e.code} kod={kod} "
                         f"alt={err.get('error_subcode')}: {mesaj}{_ipucu(kod, mesaj)}", kod)
        except urllib.error.URLError as e:
            if deneme < 2:
                time.sleep(10 * (deneme + 1))
                continue
            raise IGHata(f"{yontem} {yol} -> baglanti hatasi: {e.reason}")
    raise IGHata(f"{yontem} {yol} -> uc denemede de olmadi")


def hesap_kimligi():
    kimlik = os.getenv("IG_USER_ID", "").strip().lstrip("@")
    if kimlik.isdigit():
        return kimlik
    me = _istek("GET", "me", {"fields": "user_id,username"})
    kimlik = str(me.get("user_id") or me.get("id") or "")
    if not kimlik:
        raise IGHata("/me hesap kimligi dondurmedi")
    log(f"hesap: @{me.get('username')} ({kimlik})")
    return kimlik


def kota(ig):
    try:
        v = _istek("GET", f"{ig}/content_publishing_limit", {"fields": "config,quota_usage"})
        d = (v.get("data") or [{}])[0]
        return d.get("quota_usage", 0), (d.get("config") or {}).get("quota_total", 50)
    except IGHata as e:
        uyari(f"kota okunamadi (kritik degil): {e}")
        return 0, 50


def son_aciklamalar(ig, adet=25):
    try:
        v = _istek("GET", f"{ig}/media", {"fields": "id,caption,permalink", "limit": adet})
        return v.get("data", [])
    except IGHata as e:
        uyari(f"son postlar okunamadi, mukerrer kontrolu atlandi: {e}")
        return []


def bekle(cid, sure=600):
    son = time.time() + sure
    ara = 3
    while time.time() < son:
        v = _istek("GET", cid, {"fields": "status_code,status"})
        kod = v.get("status_code")
        if kod in ("FINISHED", "PUBLISHED"):
            return
        if kod in ("ERROR", "EXPIRED"):
            raise IGHata(f"container {kod}: {v.get('status', '')}", kod="CONTAINER_" + kod)
        time.sleep(ara)
        ara = min(20, ara * 1.5)
    raise IGHata(f"container {sure} sn icinde hazir olmadi")


def container(ig, veri):
    v = _istek("POST", f"{ig}/media", veri)
    if not v.get("id"):
        raise IGHata(f"container kimligi donmedi: {v}")
    return v["id"]


def yayinla(ig, urller, aciklama):
    if len(urller) == 1:
        cid = container(ig, {"image_url": urller[0], "caption": aciklama})
    else:
        cocuklar = []
        for u in urller:
            cocuklar.append(container(ig, {"image_url": u, "is_carousel_item": "true"}))
        for c in cocuklar:
            bekle(c)
        cid = container(ig, {"media_type": "CAROUSEL", "children": ",".join(cocuklar),
                             "caption": aciklama})
    bekle(cid)
    v = _istek("POST", f"{ig}/media_publish", {"creation_id": cid})
    mid = v.get("id")
    if not mid:
        raise IGHata(f"media_publish kimlik dondurmedi: {v}")
    bilgi = {"media_id": mid}
    try:
        bilgi["permalink"] = _istek("GET", mid, {"fields": "permalink"}).get("permalink")
    except IGHata:
        pass
    return bilgi


# --- sira ve durum ----------------------------------------------------------

def sira_oku():
    return list(csv.DictReader(open(SIRA, encoding="utf-8")))


def durum_oku():
    kayitlar = []
    if DURUM.exists():
        for satir in DURUM.read_text(encoding="utf-8").splitlines():
            if satir.strip():
                kayitlar.append(json.loads(satir))
    return kayitlar


def durum_yaz(kayit):
    DURUM.parent.mkdir(exist_ok=True)
    kayit = {"zaman": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **kayit}
    with open(DURUM, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def post_yolu(s):
    return f"{s['seri']}/{s['klasor']}"


def gorsel_tabani():
    taban = os.getenv("GORSEL_TABAN")
    if taban:
        return taban.rstrip("/")
    repo = os.getenv("GITHUB_REPOSITORY")
    sha = os.getenv("GITHUB_SHA") or "main"
    if not repo:
        raise SystemExit("GITHUB_REPOSITORY ya da GORSEL_TABAN tanimli degil")
    return f"https://raw.githubusercontent.com/{repo}/{sha}/posts"


def gorsel_dosyalari(s):
    n = int(s["gorsel_sayisi"])
    dosyalar = [f"{i:02d}.jpg" for i in range(1, n + 1)]
    if n > KAYDIRMA_SINIRI:
        # Kapak + ilk arizalar + kapanis karti; en sondaki ariza(lar) cikar.
        dosyalar = dosyalar[:KAYDIRMA_SINIRI - 1] + dosyalar[-1:]
        uyari(f"{post_yolu(s)}: {n} gorsel var, API siniri {KAYDIRMA_SINIRI}; "
              f"sondan bir onceki {n - KAYDIRMA_SINIRI} gorsel atlanacak")
    return dosyalar


def aciklama_oku(s):
    yol = POSTLAR / s["seri"] / s["klasor"] / "aciklama.txt"
    metin = yol.read_text(encoding="utf-8").strip()
    if len(metin) > ACIKLAMA_SINIRI:
        raise SystemExit(f"{yol}: aciklama {len(metin)} karakter, sinir {ACIKLAMA_SINIRI}")
    if len(re.findall(r"#\w+", metin)) > HASHTAG_SINIRI:
        raise SystemExit(f"{yol}: {HASHTAG_SINIRI}'dan fazla hashtag")
    return metin


def url_dogrula(url):
    for deneme in range(4):
        try:
            istek = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(istek, timeout=30) as r:
                tur = r.headers.get("Content-Type", "")
                if r.status == 200 and tur.startswith("image/jpeg"):
                    return
                raise IGHata(f"{url} -> {r.status} {tur}")
        except (urllib.error.URLError, IGHata) as e:
            if deneme == 3:
                raise IGHata(f"gorsel adresi acilmiyor: {url} ({e})")
            time.sleep(5 * (deneme + 1))


def ilk_satir(metin):
    return (metin or "").strip().split("\n", 1)[0].strip()


def token_suresi_kontrol():
    if not TOKEN_DURUM.exists():
        return
    try:
        bitis = dt.datetime.fromisoformat(json.loads(TOKEN_DURUM.read_text())["bitis"])
    except Exception:
        return
    kalan = (bitis - dt.datetime.now(dt.timezone.utc)).days
    if kalan < 14:
        uyari(f"Instagram tokeninin bitmesine {kalan} gun kaldi; 'Instagram tokenini yenile' "
              f"is akisinin calistigini kontrol edin.")


# --- ana akis ----------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--adet", type=int, default=1)
    p.add_argument("--kuru", action="store_true", help="Instagram'a dokunmadan kontrol et")
    p.add_argument("--kontrol", action="store_true", help="token ve kotayi goster")
    p.add_argument("--zamanli", action="store_true",
                   help="zamanlanmis tetikleme: yalnizca paylasim saati geldiyse at")
    a = p.parse_args()

    if not a.kuru and not os.getenv("IG_ACCESS_TOKEN"):
        # Kurulum bitmeden zamanlanmis is her gun kirmizi yanmasin
        uyari("IG_ACCESS_TOKEN secret'i tanimli degil; paylasim atlandi.")
        ozet("IG_ACCESS_TOKEN tanimli degil, paylasim yapilmadi.")
        return 0

    if a.kontrol:
        ig = hesap_kimligi()
        kul, top = kota(ig)
        log(f"24 saatlik kota: {kul}/{top}")
        token_suresi_kontrol()
        return 0

    kayitlar = durum_oku()
    if a.zamanli and not zamani_geldi_mi(kayitlar, os.getenv("PAYLASIM_SAATLERI", "09:37,13:37,20:37"), 120):
        return 0
    bitenler = {k["post"] for k in kayitlar if k.get("durum") in ("paylasildi", "atlandi")}
    hata_sayisi = {}
    for k in kayitlar:
        if k.get("durum") == "hata":
            hata_sayisi[k["post"]] = hata_sayisi.get(k["post"], 0) + 1

    kalanlar = [s for s in sira_oku() if post_yolu(s) not in bitenler]
    log(f"toplam {len(bitenler)} post bitti, {len(kalanlar)} post kaldi")
    if not kalanlar:
        ozet("Butun postlar paylasildi.")
        return 0

    taban = gorsel_tabani()
    ig = None
    sonuncular = []
    if not a.kuru:
        token_suresi_kontrol()
        ig = hesap_kimligi()
        kul, top = kota(ig)
        if kul >= top:
            uyari(f"24 saatlik kota dolu ({kul}/{top}); bu tur atlandi")
            return 0
        sonuncular = son_aciklamalar(ig)

    basarisiz = False
    atilan = 0
    for s in kalanlar:
        if atilan >= a.adet:
            break
        yol = post_yolu(s)
        aciklama = aciklama_oku(s)
        urller = [f"{taban}/{yol}/{d}" for d in gorsel_dosyalari(s)]
        log(f"\n#{s['sira']} {yol} ({len(urller)} gorsel)")
        try:
            for u in urller:
                url_dogrula(u)
        except IGHata as e:
            hata(f"{yol}: {e}")
            return 1

        if a.kuru:
            log(f"  kuru calistirma: adresler acik, aciklama {len(aciklama)} karakter")
            log("  " + ilk_satir(aciklama)[:120])
            atilan += 1
            continue

        # Onceki tur yayinlayip kaydi yazamadiysa ikinci kez atma
        onceki = next((m for m in sonuncular if ilk_satir(m.get("caption")) == ilk_satir(aciklama)), None)
        if onceki:
            log(f"  zaten Instagram'da ({onceki.get('permalink')}), kayda gecildi")
            durum_yaz({"post": yol, "sira": int(s["sira"]), "durum": "paylasildi",
                       "media_id": onceki["id"], "permalink": onceki.get("permalink"),
                       "not": "mukerrer kontrolunde bulundu"})
            continue

        try:
            bilgi = yayinla(ig, urller, aciklama)
        except IGHata as e:
            hata(f"{yol}: {e}")
            if str(e.kod).startswith("CONTAINER_"):
                # Instagram bu gorselleri isleyemedi; iki kez olursa postu atla ki sira tikanmasin
                durum = "atlandi" if hata_sayisi.get(yol, 0) >= 1 else "hata"
                durum_yaz({"post": yol, "sira": int(s["sira"]), "durum": durum, "hata": str(e)[:300]})
                ozet(f"- {yol}: {durum} ({e})")
            basarisiz = True
            break

        durum_yaz({"post": yol, "sira": int(s["sira"]), "durum": "paylasildi", **bilgi})
        log(f"  paylasildi: {bilgi.get('permalink') or bilgi['media_id']}")
        ozet(f"- #{s['sira']} {yol}: {bilgi.get('permalink') or bilgi['media_id']}")
        atilan += 1

    return 1 if basarisiz else 0


if __name__ == "__main__":
    sys.exit(main())
