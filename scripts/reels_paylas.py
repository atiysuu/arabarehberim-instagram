"""Siradaki Reels videosunu Instagram'a atar.

Akis:
  1) reels/sira.csv'de durum/reels.jsonl'de olmayan ilk videoyu bul
  2) videoyu bu reponun "reels-barinak" release'ine yukle ve adresi oradan ver
     (catreels'te Meta'nin release adresinden Reels indirdigi dogrulandi;
     GitHub her iki adreste de application/octet-stream donduruyor)
  3) POST /{ig}/media (media_type=REELS, video_url, cover_url) -> bekle -> media_publish
  4) sonucu durum/reels.jsonl'e yaz; release'te yalnizca son birkac video tutulur

Kapak gorseli raw.githubusercontent.com'dan verilir (jpg dogru tiple geliyor).

Kullanim:
  python3 scripts/reels_paylas.py            # siradaki 1 Reels
  python3 scripts/reels_paylas.py --kuru     # Instagram'a ve release'e dokunmadan kontrol

Ortam: IG_ACCESS_TOKEN, GITHUB_TOKEN (release icin; is akisi verir),
GITHUB_REPOSITORY, GITHUB_SHA. Token degerleri hicbir yere yazilmaz.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paylas as p  # noqa: E402

KOK = p.KOK
REELS = KOK / "reels"
SIRA = REELS / "sira.csv"
DURUM = KOK / "durum" / "reels.jsonl"
GH_API = os.getenv("GH_API_TABAN", "https://api.github.com")
GH_UPLOAD = os.getenv("GH_UPLOAD_TABAN", "https://uploads.github.com")
RELEASE_ETIKETI = "reels-barinak"
TUTULACAK_VIDEO = 5
VIDEO_SINIRI = 300 * 1024 * 1024


# --- GitHub release barinagi ------------------------------------------------

def _gh(yontem, url, veri=None, basliklar=None, govde=None):
    b = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
         "Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28", **(basliklar or {})}
    if veri is not None:
        govde = json.dumps(veri).encode()
        b["Content-Type"] = "application/json"
    istek = urllib.request.Request(url, data=govde, method=yontem, headers=b)
    try:
        with urllib.request.urlopen(istek, timeout=900) as r:
            icerik = r.read()
            return r.status, (json.loads(icerik) if icerik else {})
    except urllib.error.HTTPError as e:
        return e.code, {"hata": e.read().decode(errors="replace")[:300]}


def release_al():
    repo = os.environ["GITHUB_REPOSITORY"]
    kod, v = _gh("GET", f"{GH_API}/repos/{repo}/releases/tags/{RELEASE_ETIKETI}")
    if kod == 200:
        return v
    kod, v = _gh("POST", f"{GH_API}/repos/{repo}/releases", veri={
        "tag_name": RELEASE_ETIKETI, "name": "Reels barinagi",
        "body": "Instagram'in Reels videolarini indirdigi gecici barinak. "
                "Otomatik doluyor ve temizleniyor; elle degistirmeyin.",
        "draft": False, "prerelease": True})
    if kod not in (200, 201):
        raise p.IGHata(f"release olusturulamadi: HTTP {kod} {v}")
    return v


def video_yukle(yerel: Path, ad: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    rel = release_al()
    for a in rel.get("assets", []):
        if a.get("name") == ad:
            _gh("DELETE", f"{GH_API}/repos/{repo}/releases/assets/{a['id']}")
    url = f"{GH_UPLOAD}/repos/{repo}/releases/{rel['id']}/assets?" + urllib.parse.urlencode({"name": ad})
    kod, v = _gh("POST", url, basliklar={"Content-Type": "video/mp4"}, govde=yerel.read_bytes())
    if kod not in (200, 201):
        raise p.IGHata(f"video release'e yuklenemedi: HTTP {kod} {v}")
    return v["browser_download_url"]


def eski_videolari_temizle():
    repo = os.environ["GITHUB_REPOSITORY"]
    kod, rel = _gh("GET", f"{GH_API}/repos/{repo}/releases/tags/{RELEASE_ETIKETI}")
    if kod != 200:
        return
    varliklar = sorted(rel.get("assets", []), key=lambda a: a.get("created_at", ""), reverse=True)
    for a in varliklar[TUTULACAK_VIDEO:]:
        _gh("DELETE", f"{GH_API}/repos/{repo}/releases/assets/{a['id']}")


# --- repo icindeki dosyalar -----------------------------------------------------

def git_dosyasi(yol: str, hedef: Path):
    """Is akisi mp4'leri indirmeden cekiyor; git gereken tek videoyu burada getirir."""
    with open(hedef, "wb") as f:
        islem = subprocess.run(["git", "-C", str(KOK), "show", f"HEAD:{yol}"], stdout=f,
                               stderr=subprocess.PIPE)
    if islem.returncode != 0:
        raise p.IGHata(f"{yol} repoda bulunamadi: {islem.stderr.decode()[:200]}")


def git_dosyasi_var(yol: str) -> bool:
    return subprocess.run(["git", "-C", str(KOK), "cat-file", "-e", f"HEAD:{yol}"],
                          capture_output=True).returncode == 0


def durum_oku():
    if not DURUM.exists():
        return []
    return [json.loads(s) for s in DURUM.read_text(encoding="utf-8").splitlines() if s.strip()]


def durum_yaz(kayit):
    eski_durum = p.DURUM
    p.DURUM = DURUM
    try:
        p.durum_yaz(kayit)
    finally:
        p.DURUM = eski_durum


# --- ana akis -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adet", type=int, default=1)
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--barinak-dene", action="store_true",
                    help="kuru calistirmada ilk videoyu release'e yukleyip icerik tipini kontrol et")
    a = ap.parse_args()

    if not a.kuru and not os.getenv("IG_ACCESS_TOKEN"):
        p.uyari("IG_ACCESS_TOKEN secret'i tanimli degil; Reels paylasimi atlandi.")
        p.ozet("IG_ACCESS_TOKEN tanimli degil, Reels paylasilmadi.")
        return 0

    kayitlar = durum_oku()
    bitenler = {k["post"] for k in kayitlar if k.get("durum") in ("paylasildi", "atlandi")}
    hata_sayisi = {}
    for k in kayitlar:
        if k.get("durum") == "hata":
            hata_sayisi[k["post"]] = hata_sayisi.get(k["post"], 0) + 1

    sira = list(csv.DictReader(open(SIRA, encoding="utf-8")))
    kalanlar = [s for s in sira if s["video"] not in bitenler]
    p.log(f"toplam {len(bitenler)} Reels bitti, {len(kalanlar)} kaldi")
    if not kalanlar:
        p.ozet("Butun Reels videolari paylasildi.")
        return 0

    taban = p.gorsel_tabani().rsplit("/posts", 1)[0] + "/reels"
    ig = None
    sonuncular = []
    if not a.kuru:
        p.token_suresi_kontrol()
        ig = p.hesap_kimligi()
        kul, top = p.kota(ig)
        if kul >= top:
            p.uyari(f"24 saatlik kota dolu ({kul}/{top}); bu tur atlandi")
            return 0
        sonuncular = p.son_aciklamalar(ig)

    atilan = 0
    for s in kalanlar:
        if atilan >= a.adet:
            break
        video = s["video"]
        aciklama = (REELS / s["aciklama"]).read_text(encoding="utf-8").strip()
        if len(aciklama) > p.ACIKLAMA_SINIRI:
            raise SystemExit(f"{s['aciklama']}: aciklama {len(aciklama)} karakter")
        kapak_url = f"{taban}/{urllib.parse.quote(s['kapak'])}"
        p.log(f"\n#{s['sira']} {video}")
        try:
            if not git_dosyasi_var(f"reels/{video}"):
                raise p.IGHata(f"reels/{video} repoda yok")
            p.url_dogrula(kapak_url)
        except p.IGHata as e:
            p.hata(str(e))
            return 1

        if a.kuru and a.barinak_dene and atilan == 0:
            with tempfile.TemporaryDirectory() as gecici:
                yerel = Path(gecici) / Path(video).name
                git_dosyasi(f"reels/{video}", yerel)
                yerel_boyut = yerel.stat().st_size
                url = video_yukle(yerel, Path(video).name)
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
                boyut = int(r.headers.get("Content-Length") or 0)
                p.log(f"  barinak denemesi: {url} -> HTTP {r.status}, "
                      f"{r.headers.get('Content-Type', '')}, {boyut} bayt")
            if boyut != yerel_boyut:
                p.hata(f"barinaktaki video {boyut} bayt, yerelde {yerel_boyut} bayt")
                return 1

        if a.kuru:
            p.log(f"  kuru calistirma: video repoda, kapak acik, aciklama {len(aciklama)} karakter")
            p.log("  " + p.ilk_satir(aciklama)[:120])
            atilan += 1
            continue

        onceki = next((m for m in sonuncular if p.ilk_satir(m.get("caption")) == p.ilk_satir(aciklama)), None)
        if onceki:
            p.log(f"  zaten Instagram'da ({onceki.get('permalink')}), kayda gecildi")
            durum_yaz({"post": video, "sira": int(s["sira"]), "durum": "paylasildi",
                       "media_id": onceki["id"], "permalink": onceki.get("permalink"),
                       "not": "mukerrer kontrolunde bulundu"})
            continue

        try:
            with tempfile.TemporaryDirectory() as gecici:
                yerel = Path(gecici) / Path(video).name
                git_dosyasi(f"reels/{video}", yerel)
                if yerel.stat().st_size > VIDEO_SINIRI:
                    raise p.IGHata(f"{video} 300 MB'tan buyuk")
                video_url = video_yukle(yerel, Path(video).name)
            p.log(f"  barinak: {video_url}")
            cid = p.container(ig, {"media_type": "REELS", "video_url": video_url,
                                   "cover_url": kapak_url, "caption": aciklama,
                                   "share_to_feed": "true"})
            p.bekle(cid, sure=900)
            v = p._istek("POST", f"{ig}/media_publish", {"creation_id": cid})
            mid = v.get("id")
            if not mid:
                raise p.IGHata(f"media_publish kimlik dondurmedi: {v}")
            bilgi = {"media_id": mid}
            try:
                bilgi["permalink"] = p._istek("GET", mid, {"fields": "permalink"}).get("permalink")
            except p.IGHata:
                pass
        except p.IGHata as e:
            p.hata(f"{video}: {e}")
            if str(e.kod).startswith("CONTAINER_"):
                durum = "atlandi" if hata_sayisi.get(video, 0) >= 1 else "hata"
                durum_yaz({"post": video, "sira": int(s["sira"]), "durum": durum, "hata": str(e)[:300]})
                p.ozet(f"- {video}: {durum} ({e})")
            return 1

        durum_yaz({"post": video, "sira": int(s["sira"]), "durum": "paylasildi", **bilgi})
        p.log(f"  paylasildi: {bilgi.get('permalink') or mid}")
        p.ozet(f"- Reels #{s['sira']} {video}: {bilgi.get('permalink') or mid}")
        atilan += 1

    if not a.kuru:
        try:
            eski_videolari_temizle()
        except Exception as e:  # temizlik kritik degil
            p.uyari(f"eski videolar temizlenemedi: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
