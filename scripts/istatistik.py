#!/usr/bin/env python3
"""Paylasilan icerigin istatistiklerini ozetler (yalniz okur, hicbir sey paylasmaz).

Her medya icin Instagram'in verdigi metrikleri ceker ve ture gore
(gorsel post / Reels / seslendirmeli video) karsilastirir. Ortam: IG_ACCESS_TOKEN.
"""
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paylas as p  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
REELS_METRIK = ["views", "reach", "likes", "comments", "shares", "saved",
                "total_interactions", "ig_reels_avg_watch_time",
                "ig_reels_video_view_total_time", "reels_skip_rate"]
FEED_METRIK = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions"]


def sesli_adlari():
    # Seslendirmeli videolarin media_id'leri kendi kayit dosyasinda
    ids = set()
    yol = KOK / "durum" / "seslendirmeli.jsonl"
    if yol.exists():
        for satir in yol.read_text().splitlines():
            try:
                k = json.loads(satir)
            except ValueError:
                continue
            if k.get("media_id"):
                ids.add(str(k["media_id"]))
    return ids


def metrikler(mid, liste):
    sonuc, eksik = {}, []
    try:
        v = p._istek("GET", f"{mid}/insights", {"metric": ",".join(liste)})
        for m in v.get("data", []):
            sonuc[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
        return sonuc, eksik
    except p.IGHata:
        pass
    # Toplu istek reddedildiyse tek tek dene; hangi metrigin olmadigini gorelim
    for ad in liste:
        try:
            v = p._istek("GET", f"{mid}/insights", {"metric": ad})
            d = (v.get("data") or [{}])[0]
            sonuc[ad] = (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value"))
        except p.IGHata as e:
            eksik.append(f"{ad}: {str(e)[:120]}")
    return sonuc, eksik


def main():
    ig = p.hesap_kimligi()
    me = p._istek("GET", ig, {"fields": "username,followers_count,follows_count,media_count"})
    print("HESAP", json.dumps(me, ensure_ascii=False))

    for metric, ek in [("reach,views,follower_count", {"period": "day"}),
                       ("reach,views,profile_views,accounts_engaged,total_interactions",
                        {"period": "day", "metric_type": "total_value"})]:
        try:
            v = p._istek("GET", f"{ig}/insights", {"metric": metric, **ek})
            for m in v.get("data", []):
                print("HESAP_METRIK", m.get("name"), json.dumps(m.get("values") or m.get("total_value"), ensure_ascii=False))
        except p.IGHata as e:
            print("HESAP_METRIK_HATA", metric, e)

    medya, sonraki = [], None
    while True:
        ek = {"fields": "id,caption,media_type,media_product_type,timestamp,like_count,comments_count,permalink",
              "limit": 50}
        if sonraki:
            ek["after"] = sonraki
        v = p._istek("GET", f"{ig}/media", ek)
        medya += v.get("data", [])
        sonraki = ((v.get("paging") or {}).get("cursors") or {}).get("after")
        if not (v.get("paging") or {}).get("next") or len(medya) >= 400:
            break

    sesli = sesli_adlari()
    gruplar = {}
    eksik_ozet = set()
    for m in sorted(medya, key=lambda x: x["timestamp"]):
        reels = m.get("media_product_type") == "REELS"
        tur = "seslendirmeli" if m["id"] in sesli else ("reels" if reels else "post")
        s, eksik = metrikler(m["id"], REELS_METRIK if reels else FEED_METRIK)
        eksik_ozet.update(e.split(":")[0] + ":" + e.split(":", 1)[1][:90] for e in eksik)
        ilk = ((m.get("caption") or "").splitlines() or [""])[0][:50]
        print("MEDYA", json.dumps({"tur": tur, "zaman": m["timestamp"], "ilk": ilk,
                                   "begeni": m.get("like_count"), "yorum": m.get("comments_count"),
                                   **s, "link": m.get("permalink")}, ensure_ascii=False))
        gruplar.setdefault(tur, []).append(s)

    print("EKSIK_METRIK", json.dumps(sorted(eksik_ozet), ensure_ascii=False))
    for tur, liste in gruplar.items():
        alanlar = sorted({k for s in liste for k in s})
        ozet = {"adet": len(liste)}
        for a in alanlar:
            deger = [s[a] for s in liste if isinstance(s.get(a), (int, float))]
            if deger:
                ozet[a] = {"ort": round(statistics.mean(deger), 1), "medyan": statistics.median(deger),
                           "max": max(deger)}
        print("OZET", tur, json.dumps(ozet, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
