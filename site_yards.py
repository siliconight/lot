"""
site_yards.py  --  a concrete service pad under each dumpster
=============================================================
Step 4 of `docs/proposals/LAND_USE_DESIGN.md`, agreed by the walker
2026-10-03: open ground gets a role a viewer can read (the land-pressure
guide's 5.4). The first role is the one the site already implies. A
dumpster (`site_dumpsters`, 0.90.0) stood on the bare plate, and a real one
stands on a pad: the container is heavy, the truck's forks drop it on every
lift, and dirt under it turns to ruts. So the ground under and in front of
it is concrete, and that piece of the plate stops being remainder.

THE SIZE, FROM PRACTICE, NOT MEASUREMENT. An enclosure for one front-load
container is about 12 x 10 ft; the pad here is that, `PAD_ALONG` along the
wall by `PAD_OUT` out from it, and in front of it an `APRON` where the
truck's forks reach the container. These are the commonly published figures
for a single-container pad, read as typical, not taken from one code.

HOW IT FITS. The pad runs from the wall's face outward, centred along the
wall on its dumpster, and never past the wall's ends. It is then shrunk --
the apron first, one `STEP` at a time, then the width down to `MIN_SIDE`
beyond the container's sides -- until it is clear of every surface Lot
already draws (`site_surfaces.tops`: roads, sidewalks, kerb cuts,
frontages, walks, landings, courtyards), of other buildings by `GAP`, of
what already stands (other than its own dumpster), of the other pads, and
inside the plate by `EDGE`. Of the sizes that fit, the largest area wins.
A dumpster whose pad cannot even cover its own footprint is said
(`LOT_YARD_NO_ROOM`) and stands on the plate as before.

What it does NOT do: it does not move the dumpster, which stays where
`site_dumpsters` stood it, and it does not raise it -- the pad's top is
`lot.YARD_THICK` (14 mm), and a container's skids that far into a slab do
not read.

Site space: plan (x, y), metres. Walls are on the right angles: a dumpster
is only stood against a building whose yaw is a multiple of 90.
"""
from __future__ import annotations
import math

#: Along the wall, metres: a 12 ft enclosure.
PAD_ALONG = 3.7
#: Out from the wall's face, metres: a 10 ft enclosure. A container stands
#: `site_dumpsters.WALL_GAP` + its depth (1.35 m) out, so this leaves 1.65 m
#: of pad in front of it before the apron starts.
PAD_OUT = 3.0
#: Beyond the pad, metres: where a front-load truck's forks reach.
APRON = 3.0
#: The least pad a container stands on, beyond its sides and its front.
MIN_SIDE = 0.3
#: The step a pad shrinks by.
STEP = 0.5
#: From other buildings, and in from the plate's edge -- the dumpster's own.
GAP = 0.3
EDGE = 0.5
#: Two rectangles that only share an edge do not overlap.
TOUCH = 1e-6

_NORMAL = {"S": (0.0, -1.0), "N": (0.0, 1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def _corners(cx, cy, sx, sy, yaw_deg):
    """Plan corners of a slab by `site_surfaces.TOPS_RULE`'s axes."""
    r = math.radians(yaw_deg or 0.0)
    u = (math.cos(r), math.sin(r))
    v = (math.sin(r), -math.cos(r))
    hx, hy = sx / 2.0, sy / 2.0
    return [(cx + a * hx * u[0] + b * hy * v[0], cy + a * hx * u[1] + b * hy * v[1])
            for a in (-1, 1) for b in (-1, 1)]


def _box_corners(r):
    return [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]


def _axes(poly):
    """Edge normals of a convex quad given as its four corners, any order."""
    cx = sum(p[0] for p in poly) / 4.0
    cy = sum(p[1] for p in poly) / 4.0
    ring = sorted(poly, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    out = []
    for i in range(4):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % 4]
        ex, ey = x1 - x0, y1 - y0
        n = math.hypot(ex, ey)
        if n > 0:
            out.append((-ey / n, ex / n))
    return out


def _overlap(a, b):
    """Separating axes: do two convex quads share interior? Touching is not."""
    for ax in _axes(a) + _axes(b):
        pa = [p[0] * ax[0] + p[1] * ax[1] for p in a]
        pb = [p[0] * ax[0] + p[1] * ax[1] for p in b]
        if max(pa) <= min(pb) + TOUCH or max(pb) <= min(pa) + TOUCH:
            return False
    return True


def _grow(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def _rect(start, u, n, a0, a1, out):
    """The plan rect spanning [a0, a1] along a wall and [0, out] off it."""
    xs, ys = [], []
    for a in (a0, a1):
        for o in (0.0, out):
            xs.append(start[0] + u[0] * a + n[0] * o)
            ys.append(start[1] + u[1] * a + n[1] * o)
    return (min(xs), min(ys), max(xs), max(ys))


def _wall_line(rect, side):
    import site_dumpsters
    return site_dumpsters._wall_line(rect, side)


def plan_yards(site_spec, dumpsters, slabs, standing=(), ground=None, findings=None):
    """One pad per dumpster, as `yards` records ({at, size_x, size_y, ...},
    a courtyard's shape). ``slabs`` are `site_surfaces.tops` (the plate is
    skipped), ``standing`` the plan rects of what already stands, ``ground``
    the plate's rect."""
    import site_extent
    rects = {}
    for b in site_spec.get("buildings", []) or []:
        r = site_extent.rotated_footprint(b)
        if r is not None:
            rects[b["id"]] = r
    drawn = [_corners(s["centre"][0], s["centre"][1], s["size"][0], s["size"][1], s["yaw_deg"])
             for s in slabs if s["family"] != "ground"]
    yards, taken = [], []
    for p in dumpsters:
        bid, side = p.get("building"), p.get("wall")
        rect = rects.get(bid)
        if rect is None or side not in _NORMAL:
            _say(findings, f"LOT_YARD_NO_ROOM: {p.get('name')} names no wall this can read; no pad")
            continue
        n = _NORMAL[side]
        start, u, length = _wall_line(rect, side)
        w, d, _h = p["dims"]
        px, _ph, py = p["size"]
        own = (p["at"][0] - px / 2.0, p["at"][1] - py / 2.0,
               p["at"][0] + px / 2.0, p["at"][1] + py / 2.0)
        s = (p["at"][0] - start[0]) * u[0] + (p["at"][1] - start[1]) * u[1]
        # the container's front, measured from the wall's face
        front = (p["at"][0] - start[0]) * n[0] + (p["at"][1] - start[1]) * n[1] + d / 2.0
        least_half, least_out = w / 2.0 + MIN_SIDE, front + MIN_SIDE
        halves, half = [], PAD_ALONG / 2.0
        while half >= least_half - 1e-9:
            halves.append(half)
            half -= STEP
        outs, out = [], PAD_OUT + APRON
        while out >= least_out - 1e-9:
            outs.append(out)
            out -= STEP
        if not halves or halves[-1] > least_half + 1e-9:
            halves.append(least_half)
        if not outs or outs[-1] > least_out + 1e-9:
            outs.append(least_out)
        best = None
        for half in halves:
            for out in outs:
                a0, a1 = max(s - half, 0.0), min(s + half, length)
                if a1 - a0 < w + 2 * MIN_SIDE - 1e-9:
                    continue
                r = _rect(start, u, n, a0, a1, out)
                area = (r[2] - r[0]) * (r[3] - r[1])
                if best is not None and (area, out) <= (best[0], best[1]):
                    continue
                if ground is not None and not (ground[0] + EDGE <= r[0] and r[2] <= ground[2] - EDGE
                                               and ground[1] + EDGE <= r[1] and r[3] <= ground[3] - EDGE):
                    continue
                box = _box_corners(r)
                if any(_overlap(box, _box_corners(_grow(o, GAP))) for oid, o in rects.items() if oid != bid):
                    continue
                if any(_overlap(box, sl) for sl in drawn):
                    continue
                if any(_overlap(box, _box_corners(t)) for t in standing if not _same(t, own)):
                    continue
                if any(_overlap(box, _box_corners(t)) for t in taken):
                    continue
                best = (area, out, r)
        if best is None:
            _say(findings, f"LOT_YARD_NO_ROOM: no pad clears the walks, streets and neighbours "
                           f"around {p.get('name')}; it stands on the plate")
            continue
        _area, out, r = best
        taken.append(r)
        yards.append({"at": [round((r[0] + r[2]) / 2.0, 3), round((r[1] + r[3]) / 2.0, 3)],
                      "size_x": round(r[2] - r[0], 3), "size_y": round(r[3] - r[1], 3),
                      "building": bid, "wall": side, "dumpster": p.get("name"),
                      "out": round(out, 3), "apron": round(max(out - PAD_OUT, 0.0), 3),
                      "source": "site_yards"})
    return yards


def _same(a, b, tol=1e-3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _say(findings, text):
    if findings is not None:
        findings.append(text)
