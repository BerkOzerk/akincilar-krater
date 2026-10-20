# bina_uret.py — blok halkalarina imar bolgesinden yukseklik + GBC pseudo-3D cati katmani (W2).
# 3dm karari: halihazirin Brep'leri harita penceresinin TAMAMEN kuzeyinde (kanitli) —
# yukseklikler 1000'lik planin imar bolgelerinden (blok merkezi hangi PL_* icinde).
# Kullanici kurali: her yerde yurunur (su haric) -> binalar.json'da walkable=true.
# Çıktılar: uretim/binalar.json + uretim/harita_zemin_b.png + _preview/binalar_preview.png
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
URETIM = os.path.join(BASE, "uretim")
ZEMIN = os.path.join(URETIM, "harita_zemin_gb.png")
CIKTI_JSON = os.path.join(URETIM, "binalar.json")
CIKTI_PNG = os.path.join(URETIM, "harita_zemin_b.png")
PREVIEW = os.path.join(URETIM, "_preview", "binalar_preview.png")

SCALE = 2.6794
MH = 600.0

# Imar bolgesi -> tipik yapi yuksekligi (m) — halihazir verisi olmadigindan makul varsayimlar
ZONE_H = {
    "PL_KONUT": 7.0, "PL_KONUT_TICARET": 8.0, "PL_TICARET": 6.0, "PL_TICARET_T1": 6.0,
    "PL_RESMI_KURUM": 8.0, "PL_ILKOKUL_ALANI": 8.0, "PL_ORTAOKUL_ALANI": 8.0,
    "PL_SAGLIK_TESISI": 6.0, "PL_KULTUREL_TESIS": 5.0, "PL_CAMI": 8.0, "PL_MIA": 4.0,
    "PL_TEKNIK_ALTYAPI": 2.0, "PL_TRAFO_ALANI": 2.0, "PL_OTOPARK": 0.0,
}
BOS_ZONE = {"PL_PARK", "PL_PASIF_YESIL", "PL_SU_YUZEYI"}  # cati cizilmez (yesil/su kalir)
DEFAULT_H = 5.0

GOLGE_K = 0.35
SHADOW_RGB = (52, 52, 52)
WALL_RGB = (105, 105, 105)
ROOF_RGB = (170, 170, 170)


def icinde(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]  # 3'lü noktalar da gelebilir (x,y,z)
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def bolge_katmani():
    """imar_alanlari'ndan (PL_* poligonlari, ham DXF cercevesi) bolge listesi doner."""
    import harita_uret as hu

    bolgeler = []
    for dosya in ["1000_PLAN_TASLAK_AKINCILAR.dxf", "5000_PLAN_AKINCILAR.dxf"]:
        yol = os.path.join(BASE, dosya)
        # hu.imar_alanlari(dxf, katmanlar) -> [(katman, noktalar), ...]
        for katman, poly in hu.imar_alanlari(yol, set(list(ZONE_H.keys()) + list(BOS_ZONE))):
            pts = []
            for p in poly:
                try:
                    # ham DXF cercevesinden carpisma'nin yerel cercevesine
                    pts.append((float(p[0]) - 575893.03, float(p[1]) - 4390672.62))
                except Exception:
                    continue
            if len(pts) >= 3:
                bolgeler.append((katman, pts))
    return bolgeler


def ana():
    carpisma = json.load(open(os.path.join(URETIM, "carpisma.json"), encoding="utf-8"))
    ringler = [[(p[0], p[1]) for p in poly["points"]] for poly in carpisma["polygons"]]
    bolgeler = bolge_katmani()
    print(f"blok: {len(ringler)}, imar bolgesi poligonu: {len(bolgeler)}")

    # her blok merkezinin hangi bolgede oldugunu bul (ilk isabet; bolgeler ust uste binmez)
    binalar = []
    for ring in ringler:
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        zone = None
        for katman, poly in bolgeler:
            if icinde(cx, cy, poly):
                zone = katman
                break
        if zone in BOS_ZONE or zone is None:
            continue
        h = ZONE_H.get(zone, DEFAULT_H)
        binalar.append({"layer": zone, "points": [[round(p[0], 2), round(p[1], 2)] for p in ring],
                        "h_m": h, "walkable": True})
    print(f"cati cizilecek blok: {len(binalar)}")

    su = []
    import harita_uret as hu
    for dosya in ["1000_PLAN_TASLAK_AKINCILAR.dxf", "5000_PLAN_AKINCILAR.dxf"]:
        yol = os.path.join(BASE, dosya)
        for _katman, poly in hu.imar_alanlari(yol, {"PL_SU_YUZEYI"}):
            pts = []
            for p in poly:
                try:
                    pts.append((float(p[0]) - 575893.03, float(p[1]) - 4390672.62))
                except Exception:
                    continue
            if len(pts) >= 3:
                su.append([[round(p[0], 2), round(p[1], 2)] for p in pts])
    print(f"su poligonu: {len(su)}")

    cikti = {
        "meta": {"kaynak": "1000/5000 plan (imar bolgesi yukseklikleri)", "birim": "m",
                 "not": "3dm halihazir pencerenin kuzeyinde — yukseklikler bolgeden"},
        "binalar": [{"id": i, **b} for i, b in enumerate(binalar)],
        "su": su,
    }
    json.dump(cikti, open(CIKTI_JSON, "w", encoding="utf-8"), ensure_ascii=False)
    print("OK ->", CIKTI_JSON)

    # render: golge + duvar + cati
    zemin = Image.open(ZEMIN).convert("RGBA")
    kat = Image.new("RGBA", zemin.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)
    for b in sorted(binalar, key=lambda x: x["h_m"]):
        p = [(x * SCALE, (MH - y) * SCALE) for x, y in b["points"]]
        if b["h_m"] < 0.5:
            d.polygon(p, fill=(192, 192, 192, 255), outline=(32, 32, 32, 255))
            continue
        kay = b["h_m"] * GOLGE_K * SCALE
        d.polygon([(x + kay, y + kay) for x, y in p], fill=SHADOW_RGB + (255,))
        d.polygon([(x + kay * 0.6, y + kay * 0.6) for x, y in p], fill=WALL_RGB + (255,))
        d.polygon(p, fill=ROOF_RGB + (255,), outline=(32, 32, 32, 255))
    zemin.alpha_composite(kat)
    zemin.convert("RGB").save(CIKTI_PNG)
    print("OK ->", CIKTI_PNG)

    # preview: halkalar mavi kontur
    z2 = Image.open(ZEMIN).convert("RGBA")
    d2 = ImageDraw.Draw(z2)
    for b in binalar:
        d2.polygon([(x * SCALE, (MH - y) * SCALE) for x, y in b["points"]], outline=(0, 0, 255, 255))
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    z2.resize((1024, 804), Image.NEAREST).save(PREVIEW)
    print("OK ->", PREVIEW)


if __name__ == "__main__":
    ana()
