# gps_kalibre.py — resmi capa noktalarindan GPS ofsetini cozer (W1).
# Girdi: mapdata/kalibrasyon_noktalari.json
#   {"noktalar": [{"ad": "parsel_a", "wgs84": "39°38'55.2\"N 27°53'16.1\"E", "map_px": [985.7, 1323.9]}]}
#   "wgs84" alani DMS dizgesi VEYA [enlem, boylam] ondalik dizi olabilir.
# Cikti: uretim/kalibrasyon_cikti.json + config.ts'e yapistirilacak GPS_CAL satiri.
# Girdi yoksa bilinen ofsetle sentetik round-trip self-testi calisir.
import json
import math
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
GIRDI = os.path.join(BASE, "kalibrasyon_noktalari.json")
CIKTI = os.path.join(BASE, "uretim", "kalibrasyon_cikti.json")
META = os.path.join(BASE, "uretim", "carpisma.json")

SCALE = 2.6794  # px/m
MH = 600.0  # metre


def parse_dms(s):
    m = re.match(r"^\s*([\d.]+)\s*°\s*([\d.]+)\s*'\s*([\d.]+)\s*\"\s*([NSEWnsew])", s)
    if m:
        v = float(m.group(1)) + float(m.group(2)) / 60 + float(m.group(3)) / 3600
        return -v if m.group(4).upper() in "SW" else v
    return float(re.findall(r"[\d.]+", s)[0])


def parse_wgs84(w):
    if isinstance(w, (list, tuple)):
        return float(w[0]), float(w[1])
    s = str(w)
    # "39°38'55.2\"N 27°53'16.1\"E" bicimi: iki yarim DMS yan yana
    yarilar = re.findall(r"[\d.]+\s*°\s*[\d.]+\s*'\s*[\d.]+\s*\"\s*[NSEWnsew]", s)
    if len(yarilar) == 2:
        return parse_dms(yarilar[0]), parse_dms(yarilar[1])
    return parse_dms(s), None


def utm(lat, lon):
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:32635", always_xy=True)
    e, n = t.transform(lon, lat)
    return e, n


def coz(noktalar):
    """Her nokta: (e_utm, n_utm, map_px_x, map_px_y). GPS_CAL {dx, dy} doner (metre)."""
    meta = json.load(open(META, encoding="utf-8"))["meta"]
    OX, OY = meta["orijin_utm"]["x"], meta["orijin_utm"]["y"]
    dxs, dys = [], []
    for e, n, px, py in noktalar:
        # su anki cerceve bu GPS noktasini nereye koyar? (px)
        cur_x = (e - OX) * SCALE
        cur_y = (MH - (n - OY)) * SCALE
        # CAL: px_gercek = px_cerceve + CAL*SCALE -> metre cinsinden fark
        dxs.append((cur_x - px) / SCALE)  # metre, dogu+
        dys.append((py - cur_y) / SCALE)  # metre, kuzey+
    dx = sum(dxs) / len(dxs)
    dy = sum(dys) / len(dys)
    return dx, dy, dxs, dys, (OX, OY)


def self_test():
    print("Girdi dosyasi yok — sentetik round-trip self-testi:")
    meta = json.load(open(META, encoding="utf-8"))["meta"]
    OX, OY = meta["orijin_utm"]["x"], meta["orijin_utm"]["y"]
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:32635", "EPSG:4326", always_xy=True)
    GERCEK = (-26.0, -1832.0)  # bilinen ofset
    noktalar = []
    for px, py in [(985.7, 1323.9), (400, 400), (1600, 1200)]:
        xm = px / SCALE
        ym = MH - py / SCALE
        # CAL ile px'e dusen GERCEK UTM: px = (e-OX-CAL.dx)*SCALE, py = (MH-(n-OY-CAL.dy))*SCALE
        e = OX + xm + GERCEK[0]
        n = OY + ym + GERCEK[1]
        lon, lat = t.transform(e, n)
        noktalar.append((e, n, px, py))
    dx, dy, dxs, dys, _ = coz(noktalar)
    hata = math.hypot(dx - GERCEK[0], dy - GERCEK[1])
    print(f"  bilinen: dx={GERCEK[0]} dy={GERCEK[1]} | cozulen: dx={dx:.6f} dy={dy:.6f} | hata={hata:.2e} m")
    print("  SONUC:", "GECTI" if hata < 1e-6 else "BASARISIZ")
    return hata < 1e-6


def main():
    if not os.path.exists(GIRDI):
        sys.exit(0 if self_test() else 1)

    d = json.load(open(GIRDI, encoding="utf-8"))
    noktalar = []
    for p in d["noktalar"]:
        lat, lon = parse_wgs84(p["wgs84"])
        if lon is None:
            print(f"HATA: {p.get('ad')} — wgs84 DMS'ten cozulemedi")
            sys.exit(1)
        e, n = utm(lat, lon)
        noktalar.append((e, n, p["map_px"][0], p["map_px"][1]))

    dx, dy, dxs, dys, (OX, OY) = coz(noktalar)
    rms = math.sqrt(sum(a * a for a in dxs + dys) / len(dxs + dys))
    sonuc = {
        "GPS_CAL": {"dx": round(dx, 2), "dy": round(dy, 2)},
        "rms_m": round(rms, 2),
        "noktalar": [
            {"ad": d["noktalar"][i]["ad"], "artik_dx_m": round(dxs[i] - dx, 2), "artik_dy_m": round(dys[i] - dy, 2)}
            for i in range(len(noktalar))
        ],
    }
    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    json.dump(sonuc, open(CIKTI, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"cozuldu: GPS_CAL = {{ dx: {dx:.1f}, dy: {dy:.1f} }}  (rms {rms:.2f} m)")
    print("config.ts'e yapistir:", f"export const GPS_CAL = {{ dx: {dx:.1f}, dy: {dy:.1f} }};")
    print("cikti ->", CIKTI)
    # aykiri bayragi
    for r in sonuc["noktalar"]:
        a = math.hypot(r["artik_dx_m"], r["artik_dy_m"])
        if a > 2 * rms:
            print(f"UYARI: {r['ad']} aykiri gorunuyor (artik {a:.1f} m > 2x rms) — eslesmeyi kontrol et")


if __name__ == "__main__":
    main()
