# hizala.py — atlk (yerel) ile 1000 (UTM) cizimlerini FFT korelasyonuyla cakistirir.
# Sonuc: (ox, oy) — local = UTM - (ox, oy) donusumu; dogrulama skoruyla birlikte.

import argparse
import math

import ezdxf
import numpy as np
from ezdxf.path import make_path
from PIL import Image, ImageDraw, ImageFilter

M_PER_PX = 1.0  # her iki raster ayni olcekte


def kenar_raster(dxf, katmanlar=None):
    """DXF'in butun cizgi/yay kenarlarini 1-px cizgi olarak rasterize eder (beyaz=kenar)."""
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    xs, ys = [], []
    cizgiler = []
    for e in msp:
        if katmanlar and e.dxf.layer not in katmanlar:
            continue
        t = e.dxftype()
        if t == "LINE":
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
            cizgiler.append(pts)
        elif t in ("ARC", "CIRCLE", "SPLINE", "ELLIPSE", "LWPOLYLINE", "POLYLINE"):
            try:
                pts = [(p.x, p.y) for p in make_path(e).flattening(0.5)]
                if len(pts) >= 2:
                    cizgiler.append(pts)
            except Exception:
                pass
        for q in pts:
            xs.append(q[0]); ys.append(q[1])
    if not xs:
        raise SystemExit("bos cizim")
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w = int(math.ceil((maxx - minx) / M_PER_PX)) + 1
    h = int(math.ceil((maxy - miny) / M_PER_PX)) + 1
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for pts in cizgiler:
        d.line([((p[0] - minx) / M_PER_PX, (maxy - p[1]) / M_PER_PX) for p in pts], fill=255, width=1)
    return im, (minx, miny, maxx, maxy)


def fft_hizala(kucuk, buyuk, patch=200):
    """kucuk rasterin orta patch'ini buyuk rasterde FFT korelasyonuyla arar.
    Doner: (dx, dy) = buyuk icinde patch'in sol-ust kosesi."""
    a = np.asarray(kucuk, dtype=np.float64)
    b = np.asarray(buyuk, dtype=np.float64)
    y0, x0 = a.shape[0] // 2 - patch // 2, a.shape[1] // 2 - patch // 2
    p = a[y0:y0 + patch, x0:x0 + patch]
    # buyuk rasterde ayni boyutta olan yerler icin normalizasyon farki FFT korelasyonun kalitesini
    # cok etkilemez; ham korelasyon yeterli.
    F = np.fft.fft2(b)
    P = np.fft.fft2(np.rot90(p, 2), s=b.shape)
    corr = np.fft.ifft2(F * P).real
    peak = np.unravel_index(np.argmax(corr), corr.shape)
    # korelasyon ciktisinda (0,0) = patch'in (0,0) konumu
    dx, dy = int(peak[1]), int(peak[0])
    return dx - x0, dy - y0  # buyuk rasterde patch sol-ustu


def skor(atlk, bin_utm, ox, oy, bx0=0.0, by0=0.0):
    """Bulunan ofsetle atlk kenarlarinin ne kadari 1000 kenarlarina denk geliyor (0-1).
    ox, oy: atlk'nin sol-alt kosesinin UTM karsiligi (metre). bx0/by0: 1000 rasterin UTM orijini."""
    a = np.asarray(atlk, dtype=np.float64)
    b = np.asarray(bin_utm, dtype=np.float64)
    b_dil = (Image.fromarray((b > 0).astype(np.uint8) * 255)
             .filter(ImageFilter.MaxFilter(3)))  # 3 px tolerans
    bd = np.asarray(b_dil) > 0
    x0, y0 = int(round((ox - bx0) / M_PER_PX)), int(round((oy - by0) / M_PER_PX))
    if x0 < -bd.shape[1] or y0 < -bd.shape[0] or x0 > bd.shape[1] or y0 > bd.shape[0]:
        return 0.0
    # kesisme bolgesini hizala
    ay0, ax0 = max(0, y0), max(0, x0)
    by0i, bx0i = max(0, -y0), max(0, -x0)
    h = min(a.shape[0] - ay0, bd.shape[0] - by0i)
    w = min(a.shape[1] - ax0, bd.shape[1] - bx0i)
    if h <= 0 or w <= 0:
        return 0.0
    kes = a[ay0:ay0 + h, ax0:ax0 + w] > 0
    hedef = bd[by0i:by0i + h, bx0i:bx0i + w]
    pay = np.sum(kes & hedef)
    toplam = np.sum(kes)
    return pay / toplam if toplam else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atl", default="atl_k_son_temizlenmi_2.dxf")
    ap.add_argument("--bin", default="1000_PLAN_TASLAK_AKINCILAR.dxf")
    args = ap.parse_args()

    atlk_im, (ax0, ay0, ax1, ay1) = kenar_raster(args.atl)
    bin_im, (bx0, by0, bx1, by1) = kenar_raster(args.bin)
    print("atl raster:", atlk_im.size, "| 1000 raster:", bin_im.size)

    dx, dy = fft_hizala(atlk_im, bin_im)
    # raster ofsetleri metreye + raster orijinlerine cevir
    ox = bx0 + dx * M_PER_PX - ax0
    oy = by0 + dy * M_PER_PX - ay0
    s = skor(atlk_im, bin_im, ox, oy)
    print(f"ofset: ox={ox:.0f} oy={oy:.0f} | kenar cakisma skoru: {s:.3f}")
    print(f"local = UTM - ({ox:.0f}, {oy:.0f})")


if __name__ == "__main__":
    main()
