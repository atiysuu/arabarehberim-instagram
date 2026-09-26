"""Instagram uzun omurlu tokenini yeniler ve yeni degeri IG_ACCESS_TOKEN secret'ina yazar.

Uzun omurlu token 60 gunde doluyor; yenilenmezse paylasim sessizce durur.
Secret yazmak icin is akisinin kendi GITHUB_TOKEN'i yetmez: bu repoya
sinirli, "Secrets: Read and write" izinli bir fine-grained PAT (GH_PAT)
gerekir. GH_PAT yoksa token yine yenilenir (ayni token 60 gun daha gecerli
olur) ama Instagram yeni bir deger dondurduyse secret guncellenemez; o
durumda is akisi kirmizi yanar ve GitHub size e-posta atar.

Token degeri hicbir zaman loga ya da dosyaya yazilmaz; durum/token.json
yalnizca bitis tarihini tutar.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
TOKEN_DURUM = KOK / "durum" / "token.json"


def main() -> int:
    token = os.getenv("IG_ACCESS_TOKEN")
    if not token:
        print("::warning::IG_ACCESS_TOKEN tanimli degil; yenileme atlandi.")
        return 0

    url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
        {"grant_type": "ig_refresh_token", "access_token": token})
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            veri = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            mesaj = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            mesaj = ""
        print(f"::error::token yenilenemedi: HTTP {e.code} {mesaj}")
        return 1

    yeni = veri.get("access_token", "")
    sure = int(veri.get("expires_in", 0))
    if not yeni:
        print("::error::yanitta access_token yok")
        return 1
    print(f"::add-mask::{yeni}")

    bitis = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=sure)
    TOKEN_DURUM.parent.mkdir(exist_ok=True)
    TOKEN_DURUM.write_text(json.dumps({
        "bitis": bitis.isoformat(timespec="seconds"),
        "yenilendi": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"token yenilendi, {sure // 86400} gun gecerli (bitis {bitis.date()})")

    if yeni == token:
        print("Instagram ayni tokeni dondurdu; secret'i guncellemeye gerek yok.")
        return 0

    pat = os.getenv("GH_PAT")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not pat or not repo:
        print("::error::Instagram yeni bir token dondurdu ama GH_PAT tanimli degil; "
              "IG_ACCESS_TOKEN secret'i guncellenemedi. README'deki GH_PAT adimini yapin.")
        return 1

    # Deger komut satirina degil stdin'e verilir
    islem = subprocess.run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--repo", repo],
                           input=yeni, capture_output=True, text=True,
                           env={**os.environ, "GH_TOKEN": pat})
    if islem.returncode != 0:
        print(f"::error::gh secret set basarisiz: {islem.stderr.strip()[:300]}")
        return 1
    print("IG_ACCESS_TOKEN secret'i guncellendi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
