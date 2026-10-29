"""The street's utility cuts: a patch of newer asphalt where a building's service was trenched in (0.138.0,
the factory's roadmap 324).

The walker, 2026-10-29, of the game's vertical slice: "Things still look simple, and computer made" -- and
of what the target generation called out, "detail and placement of hard surfaces". The avenue is the
largest surface in every street frame and it was one even field of the road pack: nothing on it said a
street had been dug up, repaved and lived on.

A STREET IS PATCHED WHERE SOMETHING WAS CONNECTED. Every building on a street takes its water and its
sewer from mains under the carriageway, and each service lateral was laid in an open trench from the main
to the kerb; the trench was backfilled and capped with a rectangle of new asphalt, saw-cut wider than the
trench so the cap bears on undisturbed pavement (the "T-cut"). So a patch is not scattered: there is one in front of every building, across the lanes on that
building's side, and a building with a wide frontage has two -- its water and its sewer -- side by side.

THE NUMBERS. `TRENCH_W` is a 24 in trench and a 6 in T-cut each side, 36 in. The main lies under the road's centre line, so the trench runs from `PAST_MAIN`
beyond it to the kerb face on the building's side. A station is the building's frontage centre moved by a
seeded fraction of it (`STATION_SPREAD`), so two buildings the same width are not cut at the same place.

WHAT A PATCH KEEPS CLEAR OF. It cuts the lines along the road, as a real one does -- the edge line and the
centre line run across it un-repainted. It keeps `PATCH_CLEAR` from every other marking (a crosswalk's
bars, a stop bar, a bay's tick) and from every drain, and stays on the road's own slab, out of every
junction's box and every gap another road owns: a station that meets one is stepped past it along the
road, toward whichever side is nearer.

DRAWN AS THE PAINT IS. A patch is a flat quad of the road's own pack, tinted `PATCH_TINT` and turned a
quarter and offset (`lot.paint_offset`) so its cracks do not run on from the road's: one mesh a
`PATCH_CELL_M` cell, an OBJ beside the scene, lightmapped by Level Factory's bake as the paint is, casting
no shadow, double-sided, without collision, `PROUD` over the paint (the floater numbers, Zoo's README), so
nothing fights in the depth buffer.

THE PATCH READS BY ITS BODY, NOT ITS JOINTS. RETRACTED, KEPT: the first build (the factory's
docs/findings/slice_look/, slice 9) drew each patch at a 0.62 tint with a 4 in band of black sealant round it.
From the street's stations the body was within a few levels of the road and could not be told from it, and
the sealant -- 0.1 m wide, seen at a grazing angle from 20 m and more -- was under a pixel tall and broke
into dashes: two dashed black lines across the lane, read as skid marks or a fault, not as a patch. So no
sealant line, and the body carries the contrast a fresh cap really has against weathered asphalt.

WITH THE ART ONLY, as the drains are: a candidate's greybox lot, which Laser Tag and the walk test grade,
carries none (factory roadmap 242).

Frame: plan coordinates (x, y, z up) in, Godot's (x, z, -y) out. Pure.
"""
from __future__ import annotations

import hashlib
import math

import site_drains
import site_streets

IN = 0.0254
#: a 24 in service trench and a 6 in T-cut each side
TRENCH_W = 36 * IN                          # 0.9144 m
#: the trench starts this far past the main under the centre line
PAST_MAIN = 0.3
#: a frontage at least this wide carries two laterals, its water and its sewer
TWO_LATERALS_M = 12.0
#: the two laterals' spacing along the road, centre to centre
LATERAL_GAP = 2.4
#: a station moves up to this fraction of the frontage either side of its centre
STATION_SPREAD = 0.3
#: from a patch to a marking it does not cut, and to a drain
PATCH_CLEAR = 0.3
CLEAR_EPS = site_drains.CLEAR_EPS
#: the marks a patch runs across
LINES_ALONG = site_drains.LINES_ALONG
#: newer asphalt over the road's pack: much darker, a little cooler -- a fresh cap is near black against
#: weathered grey (0.62, the first build's, could not be told from the road at the street's stations)
PATCH_TINT = (0.42, 0.42, 0.44)
PROUD = site_drains.PROUD
PATCH_CELL_M = 32.0
#: how far a station is stepped, and how many times, before it is given up
STEP = 0.5
MAX_STEPS = 40


def _unit(key):
    """A fixed fraction in [0, 1) from ``key`` (SHA-1, not the salted `hash()`)."""
    return int.from_bytes(hashlib.sha1(key.encode("utf-8")).digest()[:4], "big") / 4294967296.0


def _served_by(rect, roads_list):
    """``(road, t, sign, facade)`` for the street a footprint ``rect`` fronts -- the street (a road with a
    sidewalk) whose kerb face is nearest its side, however far back it stands: a gas station across its
    forecourt is still served from the street -- or None when the site has no street beside it.
    ``t`` is the footprint's centre projected on the road, ``sign`` the side of the centre line it
    lies on (+1 left), ``facade`` the footprint's length along the road."""
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    best = None
    for road in roads_list:
        if not road.sidewalk:
            continue
        dx, dy = cx - road.a[0], cy - road.a[1]
        t = dx * road.along[0] + dy * road.along[1]
        if not (road.slab[0] <= t <= road.slab[1]):
            continue
        across = dx * road.perp[0] + dy * road.perp[1]
        sign = 1 if across > 0 else -1
        # the footprint's near side, across the road: the corner nearest the centre line
        near = min(abs((x - road.a[0]) * road.perp[0] + (y - road.a[1]) * road.perp[1])
                   for x in (x0, x1) for y in (y0, y1))
        gap = near - road.width / 2.0
        facade = abs((x1 - x0) * road.along[0]) + abs((y1 - y0) * road.along[1])
        if best is None or gap < best[0]:
            best = (gap, road, t, sign, facade)
    return None if best is None else best[1:]


def _rect(road, t, o0, o1):
    """The patch's plan polygon: `TRENCH_W` along the road at ``t``, ``o0`` to ``o1`` across."""
    h = TRENCH_W / 2.0
    return [road.point(t - h, o0), road.point(t + h, o0), road.point(t + h, o1), road.point(t - h, o1)]


def _blocked_spans(road):
    """``[(t0, t1)]`` along ``road`` no patch may enter: every crossing's box and every gap."""
    out = [site_streets.crossing_box(c) for c in road.crossings]
    out += [(g[0], g[1]) for g in road.gaps]
    return out


def _station_ok(road, t, o0, o1, obstacles, blocked):
    h = TRENCH_W / 2.0
    if t - h < road.slab[0] or t + h > road.slab[1]:
        return False
    if any(not (t + h <= b0 or t - h >= b1) for b0, b1 in blocked):
        return False
    poly = _rect(road, t, o0, o1)
    cx, cy = road.point(t, (o0 + o1) / 2.0)
    reach = math.hypot(TRENCH_W, o1 - o0) / 2.0 + PATCH_CLEAR
    return not any(math.hypot(px - cx, py - cy) < r + reach
                   and site_drains._gap(poly, q) < PATCH_CLEAR - CLEAR_EPS
                   for q, (px, py), r in obstacles)


def _clear_station(road, t, o0, o1, obstacles, blocked):
    """The station nearest ``t``, stepping `STEP` either way, where the patch is clear; None when none
    is within `MAX_STEPS`."""
    for k in range(MAX_STEPS + 1):
        for s in ((0,) if k == 0 else (1, -1)):
            tt = t + s * k * STEP
            if _station_ok(road, tt, o0, o1, obstacles, blocked):
                return tt
    return None


def _drain_poly(d):
    """A drain's plan footprint as a square that holds it, its centre and radius."""
    cx, cy = d["at"]
    h = site_drains.FRAME_R if d["kind"] == "manhole" else (
        max(site_drains.INLET_L, site_drains.INLET_D) / 2.0 if d["kind"] == "inlet"
        else site_drains.WALK_COVER / 2.0)
    poly = [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]
    return poly, (cx, cy), h * math.sqrt(2.0)


def plan(site_spec, roads_list, marks, drains):
    """The site's utility cuts: records with ``kind`` "service", ``building``, ``road``, ``t``, the
    patch's ``at`` (plan centre), ``yaw`` (the road's, degrees), ``size`` [along, across] and
    ``corners`` (plan polygon). ``marks`` is the paint the site draws and ``drains`` its drains
    (`site_drains.plan`), both asked for so no caller leaves either out unnoticed."""
    import site_spawns
    obstacles = [site_drains._paint(m) for m in marks if m.get("kind") not in LINES_ALONG]
    obstacles += [_drain_poly(d) for d in drains]
    out = []
    for b in sorted(site_spec.get("buildings") or [], key=lambda b: str(b.get("id"))):
        rect = site_spawns.footprint_rect(b, 0.0)
        if not rect:
            continue
        served = _served_by(rect, roads_list)
        if served is None:
            continue
        road, t, sign, facade = served
        o0, o1 = -sign * PAST_MAIN, sign * (road.width / 2.0)
        lo, hi = min(o0, o1), max(o0, o1)
        blocked = _blocked_spans(road)
        bid = str(b.get("id"))
        t += (2.0 * _unit(f"{bid}|station") - 1.0) * STATION_SPREAD * facade
        stations = [t - LATERAL_GAP / 2.0, t + LATERAL_GAP / 2.0] if facade >= TWO_LATERALS_M else [t]
        for n, ts in enumerate(stations):
            tt = _clear_station(road, ts, lo, hi, obstacles, blocked)
            if tt is None:
                continue
            poly = _rect(road, tt, lo, hi)
            x, y = road.point(tt, (lo + hi) / 2.0)
            out.append({"kind": "service", "building": bid, "lateral": n, "road": road.index,
                        "t": round(tt, 3), "at": [round(x, 4), round(y, 4)],
                        "yaw": round(road.angle_deg, 4), "size": [round(TRENCH_W, 4), round(hi - lo, 4)],
                        "corners": [[round(px, 4), round(py, 4)] for px, py in poly]})
            # the next lateral keeps clear of this one
            obstacles.append((poly, (x, y), math.hypot(TRENCH_W, hi - lo) / 2.0))
    return out


def _obj(name, quads, comment, uv):
    lines = [f"# Lot: {comment}", f"o {name}"]
    vs, vt, fs = [], [], []
    for quad, y in quads:
        k = len(vs)
        for px, py in quad:
            gx, gz = px, -py
            vs.append((gx, y, gz))
            vt.append(uv(gx, gz))
        fs.append((k + 1, k + 2, k + 3))
        fs.append((k + 1, k + 3, k + 4))
    lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in vs]
    lines += [f"vt {u:.6f} {v:.6f}" for u, v in vt]
    lines.append("vn 0 1 0")
    lines += [f"f {a}/{a}/1 {b}/{b}/1 {c}/{c}/1" for a, b, c in fs]
    return "\n".join(lines) + "\n"


def meshes(patches, paint_top, road_skin, paint_offset, mat_sub):
    """``(body_lines, sub_lines, files)``: one mesh a material a `PATCH_CELL_M` cell, an OBJ beside
    the scene. ``paint_top`` is the road paint's top face; ``road_skin`` the road's pack (none: no
    patches -- a patch is the pack, retinted); ``paint_offset`` and ``mat_sub`` are Lot's, passed in
    so this module stays free of the scene writer."""
    if not patches or not road_skin:
        return [], [], {}
    scale = 1.0 / float(road_skin["meters_per_tile"])
    patch_y = paint_top + PROUD
    cells = {}
    for p in patches:
        cell = (int(math.floor(p["at"][0] / PATCH_CELL_M)), int(math.floor(p["at"][1] / PATCH_CELL_M)))
        cells.setdefault(cell, []).append(p)
    body, sub, files = [], [], {}
    for cx, cy in sorted(cells):
        group = cells[(cx, cy)]
        tag = f"c{cx + 500:03d}_{cy + 500:03d}"
        # the patch: the road's pack turned a quarter and offset, so its cracks are its own
        off = paint_offset(f"patches|{tag}")
        name = f"site_patches_asphalt_{tag}"
        files[f"{name}.obj"] = _obj(
            name, [([tuple(c) for c in p["corners"]], patch_y) for p in group],
            f"the site's utility cuts (asphalt), cell ({cx}, {cy}) of {PATCH_CELL_M:g} m, {len(group)} patch(es)",
            lambda gx, gz: (gz * scale + off[0], -gx * scale + off[2]))
        body += [f'[node name="{name}" type="MeshInstance3D" parent="."]',
                 f'mesh = ExtResource("{name}")',
                 'material_override = SubResource("Mat_site_patches_asphalt")',
                 "cast_shadow = 0", ""]
    mat = mat_sub("site_patches_asphalt", None, road_skin, tint=PATCH_TINT, triplanar=False)
    mat.insert(len(mat) - 1, "cull_mode = 2")
    sub += mat
    return body, sub, files
