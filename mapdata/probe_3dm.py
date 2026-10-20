# probe_3dm.py — 3dm dosyasının bina geometrisini yoklar (W2.0, salt okunur).
import collections
import sys

sys.stdout.reconfigure(encoding="utf-8")

import rhino3dm

YOL = r"D:\Ahmet_Berk_Ozerk\02_Sosyal\Akıncılar Projesi\Akıncılar Mahallesi.3dm"

model = rhino3dm.File3dm.Read(YOL)
if model is None:
    print("HATA: 3dm okunamadi")
    sys.exit(1)

layer_ad = {l.Index: l.Name for l in model.Layers}

tip_say = collections.Counter()
b_katman = collections.Counter()
bbox_min = [1e18, 1e18, 1e18]
bbox_max = [-1e18, -1e18, -1e18]
z_uzantili = 0
metin_ornekleri = []

for obj in model.Objects:
    g = obj.Geometry
    if g is None:
        continue
    tip = type(g).__name__
    tip_say[tip] += 1
    ad = layer_ad.get(obj.Attributes.LayerIndex, "?")
    if ad.startswith("B_"):
        b_katman[ad] += 1
    try:
        bb = g.GetBoundingBox()
    except TypeError:
        bb = None
    if bb is not None and bb.IsValid:
        for i, (mn, mx) in enumerate([(bb.Min.X, bb.Max.X), (bb.Min.Y, bb.Max.Y), (bb.Min.Z, bb.Max.Z)]):
            bbox_min[i] = min(bbox_min[i], mn)
            bbox_max[i] = max(bbox_max[i], mx)
        if bb.Max.Z - bb.Min.Z > 0.1:
            z_uzantili += 1
    if tip == "TextDot" or tip == "TextEntity":
        try:
            metin_ornekleri.append((g.PlainText, g.Plane.Origin))
        except Exception:
            pass

print("obje tipleri:", dict(tip_say))
print("B_* katmanlari:", dict(b_katman))
print("bbox (min):", [round(v, 1) for v in bbox_min])
print("bbox (max):", [round(v, 1) for v in bbox_max])
print("z-uzantili obje sayisi:", z_uzantili)
print("metin ornekleri (ilk 10):")
for t, o in metin_ornekleri[:10]:
    print("  ", repr(t), "->", [round(v, 1) for v in (o.X, o.Y, o.Z)])
