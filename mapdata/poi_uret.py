# poi_uret.py — Overpass OSM isletme POI'lerini kapilara isim olarak isler.
# Kanit: bolge sorgusu 437 guncel isletme donduruyor (Google scraper gerekmedi).
# Cikti: uretim/kapilar_genis.json (baslik = en yakin isletme adi) + uretim/poi.json
import json
import os
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

from pyproj import Transformer

BASE = os.path.dirname(os.path.abspath(__file__))
URETIM = os.path.join(BASE, "uretim")
OX, OY = 575867.03, 4388840.62  # carpisma orijin_utm (gercek UTM 35N)
MH = 600.0
MESAFE_M = 40.0  # kapiya bu mesafedeki isletmeler o binaya ait sayilir

BBOX = (39.644, 27.878, 39.656, 27.902)
t_utm = Transformer.from_crs("EPSG:4326", "EPSG:32635", always_xy=True)


def poi_cek():
    # Once yerel onbellege bak (Overpass sunuculari kararsiz olabiliyor)
    onbel = os.path.join(URETIM, "osm_poi.json")
    if os.path.exists(onbel):
        data = json.load(open(onbel, encoding="utf-8"))
        print(f"OSM verisi yerel onbellegten ({onbel})")
        return _isle(data)

    lat_min, lon_min, lat_max, lon_max = BBOX
    sorgu = f'[out:json][timeout:60];(node["shop"]({lat_min},{lon_min},{lat_max},{lon_max});node["amenity"]({lat_min},{lon_min},{lat_max},{lon_max});way["shop"]({lat_min},{lon_min},{lat_max},{lon_max}););out tags center;'
    url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(sorgu)
    aynalar = [
        "https://overpass-api.de/api/interpreter?data=",
        "https://overpass.kumi.systems/api/interpreter?data=",
        "https://overpass.private.coffee/api/interpreter?data=",
    ]
    data = None
    son_hata = None
    for taban in aynalar:
        try:
            istek = urllib.request.Request(taban + urllib.parse.quote(sorgu), headers={"User-Agent": "krater-map/1.0 (yerel harita)"})
            with urllib.request.urlopen(istek, timeout=90) as r:
                data = json.loads(r.read().decode())
            break
        except Exception as e:
            son_hata = e
    if data is None:
        raise RuntimeError(f"tum Overpass aynalari basarisiz: {son_hata}")
    json.dump(data, open(onbel, "w", encoding="utf-8"), ensure_ascii=False)
    return _isle(data)


def _isle(data):
    poi = []
    for e in data.get("elements", []):
        tags = e.get("tags", {})
        ad = tags.get("name")
        if not ad:
            continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lon = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        e_utm, n_utm = t_utm.transform(lon, lat)
        x_m = e_utm - OX
        y_m = n_utm - OY
        if not (-10 <= x_m <= 774 and -10 <= y_m <= 610):
            continue
        poi.append({"ad": ad, "tip": tags.get("shop") or tags.get("amenity") or "", "x_m": round(x_m, 2), "y_m": round(y_m, 2)})
    return poi


def ana():
    poi = poi_cek()
    print(f"cerceve icindeki isletme: {len(poi)}")

    kapi_yol = os.path.join(URETIM, "kapilar_genis.json")
    kapilar = json.load(open(kapi_yol, encoding="utf-8"))

    carpisma = json.load(open(os.path.join(URETIM, "carpisma.json"), encoding="utf-8"))
    ringler = [[(p[0], p[1]) for p in poly["points"]] for poly in carpisma["polygons"]]

    import math

    def ring_icinde(x, y, ring):
        return bu.icinde(x, y, ring)

    # 1) isletmeyi ICINDE oldugu blok halkasina ata (en saglam eslesme)
    import bina_uret as bu
    blok_poi = {}
    for p in poi:
        for bi, ring in enumerate(ringler):
            if ring_icinde(p["x_m"], p["y_m"], ring):
                blok_poi.setdefault(bi, []).append(p)
                break
    # 2) halkasiz kalanlar: 60 m icindeki en yakin kapiya
    for k in kapilar["kapilar"]:
        k["isletmeler"] = []
        if k["blok"] in blok_poi:
            for p in sorted(blok_poi[k["blok"]], key=lambda q: math.hypot(q["x_m"] - k["x_m"], q["y_m"] - k["y_m"])):
                k["isletmeler"].append(p["ad"])
        else:
            yakin = []
            for p in poi:
                d = math.hypot(p["x_m"] - k["x_m"], p["y_m"] - k["y_m"])
                if d <= 60:
                    yakin.append((d, p))
            for _, p in sorted(yakin):
                k["isletmeler"].append(p["ad"])
        if k["isletmeler"]:
            ana_ad = k["isletmeler"][0]
            k["baslik"] = ana_ad if len(k["isletmeler"]) == 1 else f"{ana_ad} +{len(k['isletmeler']) - 1}"

    json.dump(kapilar, open(kapi_yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK ->", kapi_yol)

    json.dump({"meta": {"kaynak": "Overpass/OSM", "birim": "m"}, "poi": poi},
              open(os.path.join(URETIM, "poi.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OK ->", os.path.join(URETIM, "poi.json"))

    for k in kapilar["kapilar"][:10]:
        print("  blok", k["blok"], "->", k["baslik"], "(x", k["x_m"], "y", k["y_m"], ")")


if __name__ == "__main__":
    ana()
