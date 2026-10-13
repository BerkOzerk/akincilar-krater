# osm_dogrula.py — UTM penceresini lat/lon'a cevirir, kullanici koordinatiyla karsilastirir,
# Overpass'ten OSM bina ayak izlerini ceker ve bizim bloklarla ortusmesini olcer.

import json
import math
import urllib.parse
import urllib.request

# ---- UTM 35N -> WGS84 (standart Snyder serisi) ----
A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)
E1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
K0 = 0.9996
LAM0 = math.radians(27.0)  # zone 35N meridyeni


def utm_to_latlon(easting, northing):
    m = northing / K0
    mu = m / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    phi1 = (mu
            + (3 * E1 / 2 - 27 * E1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * E1 ** 2 / 16 - 55 * E1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * E1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * E1 ** 4 / 512) * math.sin(8 * mu))
    ep2 = E2 / (1 - E2)
    c1 = ep2 * math.cos(phi1) ** 2
    t1 = math.tan(phi1) ** 2
    n1 = A / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    r1 = A * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = (easting - 500000) / (n1 * K0)
    phi = phi1 - (n1 * math.tan(phi1) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lam = LAM0 + (
        d
        - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(phi1)
    return math.degrees(phi), math.degrees(lam)


def nokta_icinde(q, pts):
    x, y = q
    ic = False
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        if (y1 > y) != (y2 > y):
            xk = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xk > x:
                ic = not ic
    return ic


def main():
    d = json.load(open("uretim/carpisma.json", encoding="utf-8"))
    ox, oy = d["meta"]["orijin_utm"]["x"], d["meta"]["orijin_utm"]["y"]
    w, h = d["meta"]["sinirlar_m"]["genislik"], d["meta"]["sinirlar_m"]["yukseklik"]
    lat_min, lon_min = utm_to_latlon(ox, oy)
    lat_max, lon_max = utm_to_latlon(ox + w, oy + h)
    print(f"pencere: lat {lat_min:.5f}-{lat_max:.5f}, lon {lon_min:.5f}-{lon_max:.5f}")

    k_lat, k_lon = 39.64871337953862, 27.887697713059158
    icinde = lat_min <= k_lat <= lat_max and lon_min <= k_lon <= lon_max
    print(f"kullanici noktasi: {k_lat}, {k_lon} | pencerede mi: {icinde}")

    # Overpass: bina ayak izleri
    sorgu = f"""
    [out:json][timeout:90];
    way["building"]({lat_min},{lon_min},{lat_max},{lon_max});
    out geom;
    """
    try:
        req = urllib.request.Request(
            "https://overpass-api.de/api/interpreter",
            data=urllib.parse.urlencode({"data": sorgu}).encode(),
            headers={"User-Agent": "akincilar-harita-dogrulama/1.0"})
        with urllib.request.urlopen(req, timeout=100) as r:
            osm = json.load(r)
        binalar = []
        for el in osm["elements"]:
            if el["type"] == "way" and "geometry" in el:
                pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
                if len(pts) >= 4:
                    binalar.append(pts)
        print(f"OSM bina: {len(binalar)}")

        # bizim bloklar: lokal -> UTM (x=ox+px, y=oy+py)
        bloklar = [[(ox + p[0], oy + p[1]) for p in pol["points"]] for pol in d["polygons"]]

        # OSM bina merkezlerinin kaci blok icinde
        ic = 0
        alan_ic = 0.0
        alan_top = 0.0
        for pts in binalar:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            # merkezi UTM'ye cevir: basit yerel yaklasik — lon/lat farkindan metre
            # (penceremiz kucuk; duz yaklasim yeterli)
            cx_m = (cx - lon_min) / (lon_max - lon_min) * w
            cy_m = (cy - lat_min) / (lat_max - lat_min) * h
            s = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                s += x1 * y2 - x2 * y1
            alan_abs = abs(s) / 2 * 1e8  # derece kare -> yaklasik m2 (cok kaba, sadece istatistik)
            alan_top += alan_abs
            if any(nokta_icinde((cx_m, cy_m), [(p[0] - ox, p[1] - oy) for p in b]) for b in bloklar):
                ic += 1
                alan_ic += alan_abs
        print(f"OSM bina merkezi blok icinde: {ic}/{len(binalar)}")
        print(f"kaba alan agirligi: %{100 * alan_ic / max(alan_top, 1e-9):.0f}")
    except Exception as e:
        print("Overpass HATA:", e)


if __name__ == "__main__":
    main()
