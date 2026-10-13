# harita_uret.py v2 — Akincilar mahalle haritasi uretici
# Kaynaklar (ikisi de UTM 35N, kendi aralarinda hizali):
#   1000_PLAN_TASLAK_AKINCILAR.dxf — blok kenarlari (B_ADAKENARI), imar bolgeleri (PL_*),
#                                    kaldirim (KALDIRIM), parsel (TESCILLI_PARSEL)
#   5000_PLAN_AKINCILAR.dxf — yollar (PL_YOL)
# Cikti (uretim/): harita_zemin.png, harita_maske.png, carpisma.json
# NOT: atlk_k_son_temizlenmi_2.dxf kullanilmiyor — kapali poligonlari parsel siniri cikti
#      (haritayi %99,6 kapliyor), bina verisi degil.

import argparse
import collections
import json
import math
import os

import ezdxf
from ezdxf.path import make_path
from PIL import Image, ImageDraw

MAX_PX = 2048          # PNG en uzun kenari
# GERCEK KONUM KAYDIRMASI (12.10.2026 dogrulandi):
# DXF'in y koordinatinda sahte northing vardi (~+1832 m); plan merkezi gercekte
# 39.64867, 27.88786 civarinda (Balikesir Gar bolgesi). Kaydirma: dx=-26, dy=-1832.
DX_KAY = -26.0
DY_KAY = -1832.0
GAP_KAPAT_M = 5.0      # acik uclar arasindaki bu mesafeye kadar kapilar sayilir, kapatilir
FLATTEN_M = 0.25       # yay duzlestirme adimi
SNAP_M = 0.2           # uç nokta yapistirma toleransi
MIN_ALAN_M2 = 2.0
MAX_ALAN_M2 = 60000.0

BG = (228, 224, 208)
IMAR_RENK = {
    "PL_YOL": (196, 190, 178),
    "PL_PARK": (168, 196, 150),
    "PL_PASIF_YESIL": (188, 206, 168),
    "PL_SU_YUZEYI": (150, 180, 200),
    "PL_KONUT": (232, 214, 178),
    "PL_KONUT_TICARET": (232, 198, 168),
    "PL_TICARET": (230, 182, 160),
    "PL_TICARET_T1": (230, 182, 160),
    "PL_RESMI_KURUM": (206, 192, 214),
    "PL_ILKOKUL_ALANI": (198, 208, 226),
    "PL_ORTAOKUL_ALANI": (198, 208, 226),
    "PL_SAGLIK_TESISI": (222, 180, 180),
    "PL_CAMI": (206, 214, 190),
    "PL_KULTUREL_TESIS": (210, 196, 206),
    "PL_OTOPARK": (214, 208, 196),
    "PL_TEKNIK_ALTYAPI": (208, 200, 190),
    "PL_MIA": (224, 196, 172),
    "PL_TRAFO_ALANI": (210, 204, 196),
}
KALDIRIM = (214, 208, 196)
PARSEL_CIZGI = (172, 164, 150)
BINA_DOLGU = (150, 138, 124)
BINA_CERCEVE = (56, 52, 44)


def segmentler(dxf, katman):
    """Katmandaki LINE/ARC/POLYLINE'lari duz parcalara donusturur."""
    doc = ezdxf.readfile(dxf)
    out = []
    for e in doc.modelspace():
        if e.dxf.layer != katman:
            continue
        t = e.dxftype()
        if t == "LINE":
            out.append((e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y))
        elif t in ("ARC", "LWPOLYLINE", "POLYLINE"):
            pts = [(p.x, p.y) for p in make_path(e).flattening(FLATTEN_M)]
            for i in range(len(pts) - 1):
                out.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
    return out


def alan(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def blok_halkalari(segs):
    """Segment agindan kapali halkalari cikarir. Kapili zincirler <= GAP_KAPAT_M ise
    uclari birlestirilir; daha buyuk bosluklu zincirler halkaya girmez."""
    def snap(p):
        return (round(p[0] / SNAP_M) * SNAP_M, round(p[1] / SNAP_M) * SNAP_M)

    nodes = {}
    def nid(p):
        p = snap(p)
        if p not in nodes:
            nodes[p] = len(nodes)
        return nodes[p]

    adj = collections.defaultdict(set)
    for x1, y1, x2, y2 in segs:
        a, b = nid((x1, y1)), nid((x2, y2))
        if a != b:
            adj[a].add(b)
            adj[b].add(a)
    pos = {i: p for p, i in nodes.items()}

    # bilesenlere ayir; 2 acik uclu + kucuk bosluk → uclari bagla
    seen = set()
    bilesenler = []
    for start in list(adj):
        if start in seen:
            continue
        st = [start]
        seen.add(start)
        comp = []
        while st:
            u = st.pop()
            comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
        bilesenler.append(comp)

    bagli = []
    for comp in bilesenler:
        acik = [u for u in comp if len(adj[u]) == 1]
        if len(acik) == 2:
            d = math.hypot(pos[acik[0]][0] - pos[acik[1]][0], pos[acik[0]][1] - pos[acik[1]][1])
            if d <= GAP_KAPAT_M:
                adj[acik[0]].add(acik[1])
                adj[acik[1]].add(acik[0])
                bagli.append(comp)

    # her bileseni ayri ayri tara
    halkalar = []
    for comp in bilesenler:
        dereceler = {u: len(adj[u]) for u in comp}
        if any(d != 2 for d in dereceler.values()):
            # kavsakli bilesen: yarim-kenar yuruyusu (aci kurali)
            kalan = {(i, j) for i in comp for j in adj[i] if i < j}
            while kalan:
                u, v = kalan.pop()
                path = [u]
                cur_a, cur_b = u, v
                while cur_b != u and len(path) <= len(comp) + 1:
                    path.append(cur_b)
                    in_a = math.atan2(pos[cur_a][1] - pos[cur_b][1], pos[cur_a][0] - pos[cur_b][0])
                    aday = [w for w in adj[cur_b] if w != cur_a and (min(cur_b, w), max(cur_b, w)) in kalan]
                    if not aday:
                        break
                    def donus(w):
                        aw = math.atan2(pos[w][1] - pos[cur_b][1], pos[w][0] - pos[cur_b][0])
                        return (aw - in_a) % (2 * math.pi)
                    nxt = min(aday, key=donus)
                    kalan.discard((min(cur_b, nxt), max(cur_b, nxt)))
                    cur_a, cur_b = cur_b, nxt
                if cur_b == u and len(path) >= 3:
                    halkalar.append([pos[i] for i in path])
        else:
            # saf dongu: kenarlari sirala, basit turla
            kalan = {(min(i, j), max(i, j)) for i in comp for j in adj[i]}
            start = comp[0]
            path = [start]
            cur = start
            onceki = None
            while kalan:
                nxt = None
                for w in adj[cur]:
                    k = (min(cur, w), max(cur, w))
                    if k in kalan and w != onceki:
                        nxt = w
                        break
                if nxt is None:
                    break
                kalan.discard((min(cur, nxt), max(cur, nxt)))
                onceki, cur = cur, nxt
                path.append(cur)
                if cur == start:
                    break
            if len(path) >= 4 and path[-1] == start:
                halkalar.append([pos[i] for i in path[:-1]])
    # alan filtresi
    return [pts for pts in halkalar if MIN_ALAN_M2 <= alan(pts) <= MAX_ALAN_M2]


def imar_alanlari(dxf, katmanlar):
    """PL_* POLYLINE'larindan imar bolge poligonlari (kapali degilse kapatir)."""
    doc = ezdxf.readfile(dxf)
    alanlar = []
    for e in doc.modelspace():
        if e.dxf.layer not in katmanlar:
            continue
        if e.dxftype() != "POLYLINE" and e.dxftype() != "LWPOLYLINE":
            continue
        pts = [(p.x, p.y) for p in make_path(e).flattening(FLATTEN_M)]
        if len(pts) < 3:
            continue
        if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) > SNAP_M:
            pts.append(pts[0])
        alanlar.append((e.dxf.layer, pts))
    return alanlar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="uretim")
    ap.add_argument("--max-px", type=int, default=MAX_PX)
    args = ap.parse_args()

    print("B_ADAKENARI segmentleri okunuyor...")
    segs = segmentler("1000_PLAN_TASLAK_AKINCILAR.dxf", "B_ADAKENARI")
    halkalar = blok_halkalari(segs)
    a_list = sorted(alan(p) for p in halkalar)
    n = len(a_list)
    print(f"blok halkasi: {n} | alan: min {a_list[0]:.0f} medyan {a_list[n//2]:.0f} max {a_list[-1]:.0f} m2")

    print("gorsel katmanlar okunuyor...")
    kaldirim = segmentler("1000_PLAN_TASLAK_AKINCILAR.dxf", "KALDIRIM")
    parsel = segmentler("1000_PLAN_TASLAK_AKINCILAR.dxf", "TESCILLI_PARSEL")
    parsel += segmentler("1000_PLAN_TASLAK_AKINCILAR.dxf", "B_HAT_KADEME")
    imar = imar_alanlari("1000_PLAN_TASLAK_AKINCILAR.dxf", set(IMAR_RENK))
    imar += imar_alanlari("5000_PLAN_AKINCILAR.dxf", {"PL_YOL"})
    print(f"kaldirim segment: {len(kaldirim)} | parsel/hat segment: {len(parsel)} | imar alani: {len(imar)}")

    # pencere: butun malzemenin siniri
    tum = []
    for x1, y1, x2, y2 in segs + kaldirim + parsel:
        tum += [(x1, y1), (x2, y2)]
    for _, pts in imar:
        tum += pts
    minx = min(p[0] for p in tum)
    maxx = max(p[0] for p in tum)
    miny = min(p[1] for p in tum)
    maxy = max(p[1] for p in tum)
    w, h = maxx - minx, maxy - miny
    s = args.max_px / max(w, h)
    pw, ph = int(round(w * s)), int(round(h * s))
    print(f"pencere: {w:.0f} x {h:.0f} m | PNG {pw}x{ph} ({s:.2f} px/m)")

    def T(p):
        return (p[0] - minx) * s, (maxy - p[1]) * s

    os.makedirs(args.out, exist_ok=True)
    zemin = Image.new("RGB", (pw, ph), BG)
    maske = Image.new("1", (pw, ph), 0)
    dz = ImageDraw.Draw(zemin)
    dm = ImageDraw.Draw(maske)

    for katman, pts in imar:
        renk = IMAR_RENK.get(katman, BG)
        dz.polygon([T(p) for p in pts], fill=renk)
    for x1, y1, x2, y2 in kaldirim:
        dz.line([T((x1, y1)), T((x2, y2))], fill=KALDIRIM, width=max(1, round(s * 1.5)))
    for x1, y1, x2, y2 in parsel:
        dz.line([T((x1, y1)), T((x2, y2))], fill=PARSEL_CIZGI, width=1)
    # halkaya donusmeyen blok kenari parcalari (kapi bosluklari, kisa duvarlar) — ince cizgi
    for x1, y1, x2, y2 in segs:
        dz.line([T((x1, y1)), T((x2, y2))], fill=(160, 150, 138), width=1)
    for pts in halkalar:
        px = [T(p) for p in pts]
        dz.polygon(px, fill=BINA_DOLGU)
        dm.polygon(px, fill=1)
    for pts in halkalar:
        px = [T(p) for p in pts]
        dz.line(px + [px[0]], fill=BINA_CERCEVE, width=max(1, round(s * 0.3)))

    zemin.save(os.path.join(args.out, "harita_zemin.png"))
    maske.save(os.path.join(args.out, "harita_maske.png"))

    json_pol = []
    for pts in halkalar:
        json_pol.append({
            "area_m2": round(alan(pts), 2),
            "points": [[round(p[0] - minx, 3), round(p[1] - miny, 3)] for p in pts],
        })
    json_pol.sort(key=lambda d: -d["area_m2"])
    meta = {
        "kaynak": ["1000_PLAN_TASLAK_AKINCILAR.dxf (B_ADAKENARI, PL_*, KALDIRIM, TESCILLI_PARSEL)",
                   "5000_PLAN_AKINCILAR.dxf (PL_YOL)"],
        "birim": "m",
        "orijin_utm": {"x": round(minx + DX_KAY, 2), "y": round(miny + DY_KAY, 2), "bolge": "35N"},
        "kaydirma_m": {"dx": DX_KAY, "dy": DY_KAY,
                       "not": "DXF sahte northing; 12.10.2026'da Google Maps ile dogrulandi"},
        "sinirlar_m": {"genislik": round(w, 2), "yukseklik": round(h, 2)},
        "png": {"dosya": "harita_zemin.png", "genislik_px": pw, "yukseklik_px": ph,
                "m_per_px": round(1 / s, 4)},
        "blok_sayisi": len(halkalar),
        "gap_kapat_m": GAP_KAPAT_M,
    }
    with open(os.path.join(args.out, "carpisma.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "polygons": json_pol}, f, ensure_ascii=False)

    hist = maske.convert("L").histogram()
    dolu = sum(hist[1:])
    print(f"blok kaplamasi: %{100 * dolu / (pw * ph):.1f} | cikti: {args.out}")


if __name__ == "__main__":
    main()
