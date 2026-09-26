"""icerik-listesi.csv'den paylasim sirasini (sira.csv) kurar.

icerik-listesi.csv seri seri gruplu (once butun bakim takvimleri, sonra
butun kritik arizalar...). Hepsini bu sirayla atmak profilde aylarca tek
tip post demek; bu betik serileri birbirine karistirir:

- Buyuk seriler (kunye, kronik, bakim, kritik, marka, liste) butun takvime
  esit aralikla yayilir. Her serinin kendi ici sirasi korunur, yani en
  yaygin modeller once gelir.
- Site tanitimi ve rehber yazilari ilk ~120 posta serpistirilir; hesabin
  ilk postu site tanitimi olur.
- Ayni araca ait iki post (ornegin Clio kunyesi ve Clio kronik arizalari)
  arka arkaya gelirse biri bir sonrakiyle yer degistirir.

Kullanim: python3 scripts/sira_olustur.py
Dikkat: paylasim basladiktan sonra calistirmak sorun degil; paylasilanlar
durum/paylasilanlar.jsonl'de klasor yoluyla tutuldugu icin sira degisse de
ayni post iki kez atilmaz.
"""
import csv
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

# Kucuk seriler: (ilk postun sirasi, iki post arasi mesafe)
ERKEN = {
    "site-tanitimi": (0, 30),
    "rehber": (12, 30),
}


def arac_anahtari(klasor: str) -> str:
    return re.sub(r"^\d+-", "", klasor)


def main() -> None:
    satirlar = list(csv.DictReader(open(KOK / "icerik-listesi.csv", encoding="utf-8")))
    seriler: dict[str, list[dict]] = {}
    for s in satirlar:
        seriler.setdefault(s["seri"], []).append(s)

    toplam = len(satirlar)
    anahtarli = []
    for seri, liste in seriler.items():
        n = len(liste)
        for i, s in enumerate(liste):
            if seri in ERKEN:
                bas, ara = ERKEN[seri]
                k = bas + i * ara
            else:
                k = (i + 0.5) * toplam / n
            anahtarli.append((k, seri, i, s))
    anahtarli.sort(key=lambda t: (t[0], t[1], t[2]))
    sira = [t[3] for t in anahtarli]

    # Ayni araci arka arkaya koyma
    for _ in range(3):
        for i in range(1, len(sira) - 1):
            if arac_anahtari(sira[i]["klasor"]) == arac_anahtari(sira[i - 1]["klasor"]):
                sira[i], sira[i + 1] = sira[i + 1], sira[i]

    with open(KOK / "sira.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sira", "seri", "klasor", "gorsel_sayisi"])
        for n, s in enumerate(sira, 1):
            w.writerow([n, s["seri"], s["klasor"], s["gorsel_sayisi"]])
    print(f"sira.csv yazildi: {len(sira)} post")


if __name__ == "__main__":
    main()
