# kapi_uret.py — her blok için bir kapı noktası (güney kenar orta noktası) + bölge adı.
# Kullanıcı davranışı: "bir binaya giriş → o dükkanın katı" — kapılar blok başına,
# başlık imar bölgesinden; dükkan isimleri sonra elle/mülki veriyle değişir.
# Çıktı: uretim/kapilar_genis.json
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

import bina_uret as bu

BASE = os.path.dirname(os.path.abspath(__file__))
URETIM = os.path.join(BASE, "uretim")

ZONE_AD = {
    "PL_KONUT": "Konut Alanı", "PL_KONUT_TICARET": "Konut + Ticaret", "PL_TICARET": "Ticaret Alanı",
    "PL_TICARET_T1": "Ticaret Alanı", "PL_RESMI_KURUM": "Resmi Kurum", "PL_ILKOKUL_ALANI": "Okul",
    "PL_ORTAOKUL_ALANI": "Okul", "PL_SAGLIK_TESISI": "Sağlık Tesisi", "PL_CAMI": "Cami",
    "PL_KULTUREL_TESIS": "Kültürel Tesis", "PL_MIA": "MIA", "PL_TEKNIK_ALTYAPI": "Teknik Altyapı",
    "PL_TRAFO_ALANI": "Trafo", "PL_OTOPARK": "Otopark",
}


def ana():
    carpisma = json.load(open(os.path.join(URETIM, "carpisma.json"), encoding="utf-8"))
    ringler = [[(p[0], p[1]) for p in poly["points"]] for poly in carpisma["polygons"]]
    bolgeler = bu.bolge_katmani()

    kapilar = []
    for bi, ring in enumerate(ringler):
        # blok merkezinin bölgesi (bina_uret ile aynı mantık)
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        zone = None
        for katman, poly in bolgeler:
            if bu.icinde(cx, cy, poly):
                zone = katman
                break
        if zone is None or zone in bu.BOS_ZONE:
            continue  # park/su/verisiz blokta kapı yok (bina yok)
        # güney kenar (en düşük ortalama y): sokağa bakan kapı varsayımı
        best_e, best_my = None, 1e18
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            my = (a[1] + b[1]) / 2
            if my < best_my:
                best_my = my
                best_e = ((a[0] + b[0]) / 2, my)
        kapilar.append({
            "blok": bi,
            "x_m": round(best_e[0], 2),
            "y_m": round(best_e[1], 2),
            "width_m": 1.0,
            "zone": zone,
            "baslik": ZONE_AD.get(zone, "Bina"),
        })

    cikti = {
        "meta": {"birim": "m", "not": "kapılar blok başına güney kenar orta noktası; başlıklar imar bölgesinden"},
        "kapilar": kapilar,
    }
    hedef = os.path.join(URETIM, "kapilar_genis.json")
    json.dump(cikti, open(hedef, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK ->", hedef, f"({len(kapilar)} kapi)")


if __name__ == "__main__":
    ana()
