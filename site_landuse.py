"""
site_landuse.py  --  what the ground is FOR, measured
====================================================
The walker, 2026-10-03, filing `docs/reference/LAND_PRESSURE_AND_SPATIAL_LOGIC.md`:
"this should directly inform Lot". The guide's governing rule is that every
piece of open land has a role a viewer can see (its 5.4), that a street's
frontage is used for something (5.3), that variation is correlated rather
than independent jitter on every building (5.7), and that a generator states
its measurements and their boundary (7). Nothing in this repo measured any of
that. This module does, and changes nothing.

ONE BOUNDARY: the resolved ground plate (`site_extent.resolve`), on a grid of
`CELL` metres. Each cell takes the first use, in `USES` order, whose
geometry holds its centre:

  * ``building``  -- a building's rotated footprint (`site_extent.
    rotated_footprint`);
  * the drawn ground, from `site_surfaces.tops` -- the same slabs Lot draws,
    by family: ``road``, ``kerbcut``, ``sidewalk``, ``frontage``, ``path``
    (a walk or a landing), ``courtyard``, ``yard`` (a service pad,
    `site_yards`), ``parking`` (a parking field, `site_fields`);
  * ``remainder`` -- plate with none of the above. The guide's "unexplained
    parcel area".

The cover pieces (cars, furniture, dumpsters, trucks) are not land uses and
are counted apart, as pieces on the ground.

What it reports (`census`): the area and share of each use; the largest
connected piece of remainder; coverage (building area / plate); building
separation, exterior to exterior, nearest neighbour each; per road, the
building line (the distance from the road's back of walk to each building
that fronts it, and its spread), frontage occupancy (the fronting buildings'
width along the road over the road's length on the plate), and whether each
fronting building has a ground door facing it. A measurement, not a verdict:
no field here gates.

Site space: plan (x, y), metres.
"""
from __future__ import annotations
import math

#: The grid's cell, metres. 0.5 m resolves a 3 m sidewalk to six cells and a
#: 1.5 m landing to three; the plate of a three-building lot is ~70,000 cells.
CELL = 0.5

#: First use wins, in this order.
USES = ("building", "road", "kerbcut", "sidewalk", "frontage", "path", "courtyard", "yard",
        "parking", "remainder")

#: A building FRONTS a road when its face toward the road is within this of
#: the road's back of walk, in metres: Level Factory stands a face `FRONTAGE`
#: (2 m) from its sidewalk, and a forecourt put one ~15 m back on cold run
#: 9139; 30 m covers both, the same reach `site_dumpsters` uses.
FRONT_REACH = 30.0


def _holds(slab, x, y):
    cx, cy = slab["centre"]
    sx, sy = slab["size"]
    a = math.radians(slab.get("yaw_deg") or 0.0)
    dx, dy = x - cx, y - cy
    u = dx * math.cos(a) + dy * math.sin(a)
    v = dx * math.sin(a) - dy * math.cos(a)
    return abs(u) <= sx / 2.0 and abs(v) <= sy / 2.0


def _slab_box(slab):
    cx, cy = slab["centre"]
    sx, sy = slab["size"]
    a = math.radians(slab.get("yaw_deg") or 0.0)
    ex = abs(sx / 2.0 * math.cos(a)) + abs(sy / 2.0 * math.sin(a))
    ey = abs(sx / 2.0 * math.sin(a)) + abs(sy / 2.0 * math.cos(a))
    return (cx - ex, cy - ey, cx + ex, cy + ey)


def _rect_gap(a, b):
    """Shortest distance between two axis-aligned rects; 0 when they touch."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy)


def _grid(rect):
    x0, y0, x1, y1 = rect
    nx = max(1, int(math.ceil((x1 - x0) / CELL)))
    ny = max(1, int(math.ceil((y1 - y0) / CELL)))
    return nx, ny


def _paint(grid, rect, box, test, use):
    """Give every unassigned cell in `box` whose centre `test` holds `use`."""
    x0, y0, x1, y1 = rect
    nx, ny = len(grid[0]), len(grid)
    i0 = max(0, int((box[0] - x0) / CELL))
    i1 = min(nx - 1, int((box[2] - x0) / CELL))
    j0 = max(0, int((box[1] - y0) / CELL))
    j1 = min(ny - 1, int((box[3] - y0) / CELL))
    for j in range(j0, j1 + 1):
        y = y0 + (j + 0.5) * CELL
        row = grid[j]
        for i in range(i0, i1 + 1):
            if row[i] is not None:
                continue
            x = x0 + (i + 0.5) * CELL
            if test(x, y):
                row[i] = use


def _largest_blob(grid, use):
    """Cells in the largest 4-connected piece of `use`."""
    ny, nx = len(grid), len(grid[0])
    seen = [[False] * nx for _ in range(ny)]
    best = 0
    for j in range(ny):
        for i in range(nx):
            if seen[j][i] or grid[j][i] != use:
                continue
            stack, n = [(j, i)], 0
            seen[j][i] = True
            while stack:
                cj, ci = stack.pop()
                n += 1
                for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    a, b = cj + dj, ci + di
                    if 0 <= a < ny and 0 <= b < nx and not seen[a][b] and grid[a][b] == use:
                        seen[a][b] = True
                        stack.append((a, b))
            best = max(best, n)
    return best


def _road_frame(road):
    return road.a, road.along, road.perp, road.length


def census(site_spec, merged=None):
    """The land-use measurement of one site; see the module docstring. With
    `merged` (the merged gameplay), ground doors are read for the
    door-to-street count; without it that field is None."""
    import site_extent
    import site_streets
    import site_surfaces
    ext = site_extent.resolve(site_spec)
    if ext.rect is None:
        return {"ok": False, "reason": "no ground plate"}
    rect = ext.rect
    nx, ny = _grid(rect)
    grid = [[None] * nx for _ in range(ny)]
    buildings = {}
    for b in site_spec.get("buildings", []) or []:
        r = site_extent.rotated_footprint(b)
        if r is not None:
            buildings[b["id"]] = r
            _paint(grid, rect, r, lambda x, y: True, "building")
    slabs = [s for s in site_surfaces.tops(site_spec, ground=ext) if s["family"] != "ground"]
    for use in USES[1:-1]:
        for s in slabs:
            if s["family"] == use:
                _paint(grid, rect, _slab_box(s), lambda x, y, s=s: _holds(s, x, y), use)
    for row in grid:
        for i, v in enumerate(row):
            if v is None:
                row[i] = "remainder"
    cell_a = CELL * CELL
    counts = {u: 0 for u in USES}
    for row in grid:
        for v in row:
            counts[v] += 1
    unknown = sorted({s["family"] for s in slabs} - set(USES))
    total = nx * ny
    areas = {u: round(counts[u] * cell_a, 1) for u in USES}
    shares = {u: round(counts[u] / total, 4) for u in USES}
    # separation: each building's nearest neighbour, exterior to exterior
    ids = sorted(buildings)
    nearest = {}
    for a in ids:
        gaps = [_rect_gap(buildings[a], buildings[b]) for b in ids if b != a]
        nearest[a] = round(min(gaps), 2) if gaps else None
    # per road: which buildings front it, their setback from its back of
    # walk, the frontage they occupy, and whether a ground door faces it
    doors = None
    if merged is not None:
        import site_paths
        doors = site_paths.doors(site_spec, merged)
    roads_out = []
    for road in site_streets.roads(site_spec):
        (ax, ay), (ux, uy), (px, py), length = _road_frame(road)
        back = road.width / 2.0 + float(road.sidewalk or 0.0)
        fronting = []
        for bid, r in buildings.items():
            cx, cy = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
            t = (cx - ax) * ux + (cy - ay) * uy
            off = (cx - ax) * px + (cy - ay) * py
            hx, hy = (r[2] - r[0]) / 2.0, (r[3] - r[1]) / 2.0
            half_across = abs(hx * px) + abs(hy * py)
            half_along = abs(hx * ux) + abs(hy * uy)
            if t + half_along < 0 or t - half_along > length:
                continue
            setback = abs(off) - half_across - back
            if setback < -0.5 or setback > FRONT_REACH:
                continue
            side = 1 if off > 0 else -1
            facing = None
            if doors is not None:
                to_road = (-px * side, -py * side)
                facing = any(n[0] * to_road[0] + n[1] * to_road[1] > 0.7 for _p, n, _hw, _w in doors.get(bid, []))
            fronting.append({"building": bid, "side": side, "setback": round(setback, 2),
                             "along": [round(t - half_along, 2), round(t + half_along, 2)],
                             "door_faces_road": facing})
        on_plate = length
        occ = {}
        for side in (-1, 1):
            spans = sorted((f["along"][0], f["along"][1]) for f in fronting if f["side"] == side)
            covered, end = 0.0, -1e9
            for a0, a1 in spans:
                a0, a1 = max(a0, 0.0), min(a1, on_plate)
                if a1 <= end:
                    continue
                covered += a1 - max(a0, end)
                end = a1
            occ["left" if side > 0 else "right"] = round(covered / on_plate, 3) if on_plate > 0 else None
        sb = [f["setback"] for f in fronting]
        roads_out.append({"road": road.index, "length": round(on_plate, 1), "fronting": fronting,
                          "setback_min": min(sb) if sb else None, "setback_max": max(sb) if sb else None,
                          "setback_spread": round(max(sb) - min(sb), 2) if len(sb) > 1 else 0.0,
                          "frontage_occupancy": occ})
    plate_a = total * cell_a
    return {"ok": True, "cell_m": CELL, "plate": [round(v, 2) for v in rect],
            "plate_area": round(plate_a, 1), "areas": areas, "shares": shares,
            "remainder_largest_blob": round(_largest_blob(grid, "remainder") * cell_a, 1),
            "coverage": shares["building"], "nearest_building_gap": nearest,
            "roads": roads_out, "unknown_families": unknown,
            "pieces": len(site_spec.get("cover", []) or [])}
