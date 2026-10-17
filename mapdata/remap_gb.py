# remap_gb.py — harita_zemin.png'i GBC (Pokemon Gold/Silver) paletine remap eder.
# Kaynak renkler harita_uret.py sabitlerinden birebir alindi (20 benzersiz RGB).
# Dithering YOK: kaynak %100 duz renk, dither gurultu katar.
# Cikti: uretim/harita_zemin_gb.png + uretim/_preview/harita_zemin_gb_preview.png
from PIL import Image
import json
import os
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "uretim", "harita_zemin.png")
DST = os.path.join(BASE, "uretim", "harita_zemin_gb.png")
PREVIEW = os.path.join(BASE, "uretim", "_preview")

# kaynak RGB -> hedef RGB (GBC tarzi: cim yesili, koyu gri yol, acik kaldirim)
HARITA = {
    (228, 224, 208): (155, 188, 15),   # BG -> cim
    (196, 190, 178): (85, 85, 85),     # PL_YOL -> koyu gri yol
    (168, 196, 150): (139, 172, 15),   # PL_PARK -> koyu yesil
    (188, 206, 168): (139, 172, 15),   # PL_PASIF_YESIL -> koyu yesil
    (150, 180, 200): (72, 120, 192),   # PL_SU_YUZEYI -> su mavisi
    (232, 214, 178): (212, 212, 200),  # PL_KONUT -> acik
    (232, 198, 168): (170, 170, 170),  # PL_KONUT_TICARET
    (230, 182, 160): (139, 139, 139),  # PL_TICARET (=PL_TICARET_T1)
    (206, 192, 214): (170, 170, 170),  # PL_RESMI_KURUM
    (222, 180, 180): (139, 139, 139),  # PL_SAGLIK_TESISI
    (206, 214, 190): (155, 188, 15),   # PL_CAMI -> cim
    (210, 196, 206): (170, 170, 170),  # PL_KULTUREL_TESIS
    (214, 208, 196): (200, 200, 200),  # KALDIRIM = PL_OTOPARK -> acik kaldirim
    (208, 200, 190): (200, 200, 200),  # PL_TEKNIK_ALTYAPI
    (224, 196, 172): (170, 170, 170),  # PL_MIA
    (210, 204, 196): (200, 200, 200),  # PL_TRAFO_ALANI
    (172, 164, 150): (139, 139, 139),  # PARSEL_CIZGI
    (150, 138, 124): (192, 192, 192),  # BINA_DOLGU -> kaldirim tonu (Faz B binalari ustune gelecek)
    (56, 52, 44):    (32, 32, 32),     # BINA_CERCEVE -> koyu cerceve
    (160, 150, 138): (139, 139, 139),  # ham blok kenari
}

def en_yakin(c):
    return min(HARITA.values(), key=lambda h: sum((a - b) ** 2 for a, b in zip(c, h)))

# ---- OSM yollari: Overpass'ten cekilir, zemin dokusunun ustune cizilir ----
# harita penceresi (harita_uret.py meta'sindan, carpisma.json ile ayni cerceve)
OX, OY = 575867.03, 4388840.62  # UTM 35N min kose
W_M, H_M = 764.34, 600.0

GENISLIK = {  # highway tipi -> yol genisligi (m)
    "motorway": 12, "trunk": 12, "primary": 10, "secondary": 8,
    "tertiary": 7, "residential": 6, "unclassified": 5, "living_street": 5,
    "service": 4, "pedestrian": 6, "footway": 2, "path": 2, "cycleway": 2, "track": 3,
}

def osm_yollar():
    from pyproj import Transformer
    t_wgs = Transformer.from_crs("EPSG:32635", "EPSG:4326", always_xy=True)  # utm->wgs84
    t_utm = Transformer.from_crs("EPSG:4326", "EPSG:32635", always_xy=True)  # wgs84->utm
    lon_min, lat_min = t_wgs.transform(OX, OY)
    lon_max, lat_max = t_wgs.transform(OX + W_M, OY + H_M)
    bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"
    sorgu = f'[out:json][timeout:60];(way["highway"]({bbox}););(._;>;);out;'
    url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(sorgu)
    istek = urllib.request.Request(url, headers={"User-Agent": "krater-map/1.0 (yerel harita)"})
    with urllib.request.urlopen(istek, timeout=120) as r:
        data = json.loads(r.read().decode())
    nodeler = {e["id"]: (e["lon"], e["lat"]) for e in data["elements"] if e["type"] == "node"}
    yollar = []
    for e in data["elements"]:
        if e["type"] != "way":
            continue
        hw = e.get("tags", {}).get("highway", "")
        if hw not in GENISLIK:
            continue
        pts = []
        for nid in e.get("nodes", []):
            if nid in nodeler:
                x, y = t_utm.transform(*nodeler[nid])
                pts.append((x, y))
        if len(pts) >= 2:
            yollar.append((hw, pts))
    print(f"OSM: {len(yollar)} yol cekildi")
    return yollar

def ciz_yollar(img):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    s = 2048 / W_M  # px/m (2.6794)
    for hw, pts in osm_yollar():
        gen = GENISLIK[hw]
        w_px = max(2, round(gen * s))
        renk = (60, 60, 60) if gen >= 8 else (85, 85, 85)  # ana yollar daha koyu
        px = [((x - OX) * s, (H_M - (y - OY)) * s) for x, y in pts]
        # segment cizgileri + dugum noktalari (kose boslugu kalmasin)
        for a, b in zip(px, px[1:]):
            d.line([a, b], fill=renk, width=w_px)
        for n in px:
            d.ellipse([n[0] - w_px / 2, n[1] - w_px / 2, n[0] + w_px / 2, n[1] + w_px / 2], fill=renk)

def unity_json():
    # JsonUtility ic ice listeyi ([[x,y],...]) parse edemiyor -> Vector2 uyumlu {"x","y"} ciftlerine cevir
    kaynak = os.path.join(BASE, "uretim", "carpisma.json")
    hedef = os.path.join(BASE, "uretim", "carpisma_unity.json")
    d = json.load(open(kaynak, encoding="utf-8"))
    for poly in d["polygons"]:
        poly["points"] = [{"x": p[0], "y": p[1]} for p in poly["points"]]
    json.dump(d, open(hedef, "w", encoding="utf-8"))
    print("OK ->", hedef)

def main():
    img = Image.open(SRC).convert("RGB")
    p = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    pal = p.getpalette()
    yeni = []
    for i in range(256):
        c = tuple(pal[3 * i:3 * i + 3])
        yeni += list(HARITA.get(c, en_yakin(c)))
    p.putpalette(yeni)
    out = p.convert("RGB")
    ciz_yollar(out)
    out.save(DST)
    os.makedirs(PREVIEW, exist_ok=True)
    out.resize((1024, 804), Image.NEAREST).save(os.path.join(PREVIEW, "harita_zemin_gb_preview.png"))
    print("OK ->", DST)
    unity_json()

if __name__ == "__main__":
    main()
