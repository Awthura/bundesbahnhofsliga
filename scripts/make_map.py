"""Build the Germany map (16 states) for the map page: simplified SVG paths in docs/assets/map/states.json.

Source: Natural Earth 1:10m admin-1 boundaries (public domain), https://www.naturalearthdata.com/
  python scripts/make_map.py [path/to/ne_10m_admin_1_states_provinces.geojson]
Without a path, the file is downloaded to data/raw/ (gitignored) and deleted afterwards.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "map" / "states.json"
URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
       "ne_10m_admin_1_states_provinces.geojson")
WIDTH = 600                     # SVG units; the page scales it
TOLERANCE = 0.008               # degrees, Douglas-Peucker simplification (about 0.6 to 0.9 km)
LAT0 = 51.0                     # reference latitude for the equirectangular projection
# Brandenburg's centroid falls inside the Berlin hole: put its label east of Berlin
LABEL_AT = {"Brandenburg": (13.9, 52.05)}
SHORT = {"Berlin": "B", "Hamburg": "HH", "Bremen": "HB"}   # city-states are too small for full names


def simplify(points, tol):
    """Douglas-Peucker on a ring of (lon, lat)."""
    if len(points) < 4:
        return points

    def dp(pts):
        a, b = pts[0], pts[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = math.hypot(dx, dy) or 1e-12
        best, idx = -1.0, 0
        for i in range(1, len(pts) - 1):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + b[0] * a[1] - b[1] * a[0]) / norm
            if d > best:
                best, idx = d, i
        if best <= tol:
            return [a, b]
        return dp(pts[: idx + 1])[:-1] + dp(pts[idx:])

    # a ring starts and ends at the same point: split it at the point farthest from the start
    far = max(range(len(points)), key=lambda i: math.hypot(points[i][0] - points[0][0], points[i][1] - points[0][1]))
    out = dp(points[: far + 1])[:-1] + dp(points[far:])
    return out if len(out) >= 4 else points


def ring_area(r):
    return 0.5 * sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1))


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    tmp = None
    if src is None:
        tmp = src = ROOT / "data" / "raw" / "ne_admin1.geojson"
        src.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["curl", "-sSL", "--fail", "-o", str(src), URL], check=True)
    feats = [f for f in json.loads(src.read_text())["features"] if f["properties"].get("iso_a2") == "DE"]
    polys = {}
    for f in feats:
        g = f["geometry"]
        polys[f["properties"]["name"]] = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    lons = [p[0] for ps in polys.values() for poly in ps for ring in poly for p in ring]
    lats = [p[1] for ps in polys.values() for poly in ps for ring in poly for p in ring]
    kx = math.cos(math.radians(LAT0))
    lon0, lat1 = min(lons), max(lats)
    scale = WIDTH / ((max(lons) - lon0) * kx)
    height = (lat1 - min(lats)) * scale
    proj = lambda lon, lat: ((lon - lon0) * kx * scale, (lat1 - lat) * scale)   # noqa: E731

    states, points = [], 0
    for name, ps in sorted(polys.items()):
        d, best = [], (0, None)
        for poly in ps:
            for k, ring in enumerate(poly):
                r = simplify([tuple(p) for p in ring], TOLERANCE)
                points += len(r)
                xy = [proj(*p) for p in r]
                d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in xy) + "Z")
                if k == 0 and abs(ring_area(r)) > best[0]:
                    best = (abs(ring_area(r)), r)
        r = best[1]   # label at the centroid of the largest outer ring
        a = ring_area(r) or 1e-12
        cx = sum((r[i][0] + r[i + 1][0]) * (r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]) for i in range(len(r) - 1)) / (6 * a)
        cy = sum((r[i][1] + r[i + 1][1]) * (r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]) for i in range(len(r) - 1)) / (6 * a)
        lon_l, lat_l = LABEL_AT.get(name, (cx, cy))
        lx, ly = proj(lon_l, lat_l)
        states.append({"name": name, "short": SHORT.get(name), "d": "".join(d), "label": [round(lx, 1), round(ly, 1)]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "Natural Earth 1:10m admin-1 (public domain)",
        "width": WIDTH, "height": round(height, 1),
        "projection": {"lon0": lon0, "lat1": lat1, "kx": kx, "scale": scale},
        "states": states}, ensure_ascii=False, separators=(",", ":")))
    if tmp:
        tmp.unlink()
    print(f"{len(states)} states, {points} points, {OUT.stat().st_size // 1024} KB -> {OUT}")


if __name__ == "__main__":
    main()
