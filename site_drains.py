"""The street's drains: manhole covers and storm inlets (0.120.0, factory roadmap 179).

The walker, 2026-10-04: "in various locations, usually on sidewalks, we should have manhole covers,
sewer drain grates (should be like fire hydrants where there is only so many in shared area)". Five
photographs came with it, read for the format and never the marks: round cast-iron covers flush in the
asphalt and in the sidewalk; a rectangular cast grate in the gutter tight against the kerb, an open
throat in the kerb face above it; a cover in the sidewalk a step behind an inlet; an inlet at a corner
beside the ramp, a round cover out in the crosswalk.

THE RULES, READ AT SOURCE (the factory's docs/reference/STREET_DRAINS.md):
  * A sanitary manhole at every junction -- the sewer is under the street, so at the junction's centre,
    where the mains cross -- and along a street run no farther apart than 400 ft (121.9 m), the Ten
    States figure for sewers of 15 in and under (Illinois 35 IAC 370.330, Virginia 9VAC25-790-350).
    A road's end at the site's edge is not its sewer's end, so none is placed there.
  * A storm inlet upstream of a crosswalk and its ramp, so the water is taken before it crosses where
    people walk (TxDOT Hydraulic Design Manual, ch. 10 s. 5): in the gutter against the kerb, on the
    block side of a junction's cut, ONE A CORNER as the hydrant is (`site_furniture.CORNER_ONE_EACH`) --
    the walker's "only so many". Inlets between corners follow the gutter's spread, which needs the
    street's grade and a design storm a site has not got: not placed.
  * A cover in the sidewalk a step behind an inlet (the walker's photograph), no two nearer than the
    hydrant's site-wide minimum and never under a piece of furniture: the utilities' lids, which no
    standard places, so "only so many" is the hydrant's number, borrowed.
  * Sizes: a 24 in clear opening, the lid 25 5/16 in and the frame 32 3/16 in across (Cal Poly 6610,
    Kirkland CK-S-09, a supplier's 24 in sewer frame); the inlet a 2 x 3 ft grate, the 3 ft along the
    kerb (ADS Nyloplast); the sidewalk lid's 18 in, the photograph's proportion.

FLUSH, AND NO COLLISION: a body walks over a cover. Every piece is a floater (Zoo's README, factory
roadmap 234): it rests with a `SKIRT` into the surface it lies on and stands `PROUD` of whatever is
already drawn there -- the road's paint is 3 mm proud of the asphalt, so a cover in a crosswalk stands
6 mm -- and its relief stands `PROUD` off the lid, so no two faces fight in the depth buffer nearer
than 50 m. Drawn with the art only, as the wires are (`lot._outdoor_nodes`): a candidate's greybox lot,
which Laser Tag and the walk test grade, carries none (factory roadmap 242).

ONE MESH A MATERIAL A CELL, as the paint and the wires are: the iron, and the dark of an open grate and
a kerb's throat, each a `DRAIN_CELL_M` square by the piece's centre, in an OBJ beside the scene,
lightmapped by Level Factory's bake as the paint is, casting no shadow (flush). Every face winds
counter-clockwise about its outward normal (OBJ's front). Frame: plan coordinates (x, y, z up) in,
Godot's (x, z, -y) out -- a rotation, so a face's winding survives it. Pure.
"""
from __future__ import annotations

import math

import site_furniture

IN = 0.0254
#: Ten States: a manhole no farther than 400 ft from the next, on sewers of 15 in and under
MANHOLE_SPACING_MAX = 400 * 0.3048          # 121.92 m
#: a 24 in sewer frame and cover: the lid and the frame across
COVER_R = 25.3125 * IN / 2.0                # 0.3215 m
FRAME_R = 32.1875 * IN / 2.0                # 0.4088 m
#: a 2 x 3 ft curb inlet grate, its 3 ft along the kerb
INLET_L = 3 * 0.3048                        # 0.9144 m
INLET_D = 2 * 0.3048                        # 0.6096 m
#: from the edge of a junction's cut to the grate's near end: a hand, clear of the ramp
INLET_CLEAR = 0.3
#: the sidewalk cover: 18 in square, its centre a step (0.75 m) in from the kerb face
WALK_COVER = 18 * IN                        # 0.4572 m
STEP_BEHIND = 0.75
#: the walker's "only so many" for the sidewalk lids: the hydrant's site-wide minimum
WALK_COVER_MIN_SPACING = site_furniture.HYDRANT_MIN_SPACING
#: a sidewalk lid keeps this clear of a piece of furniture's footprint
FURNITURE_CLEAR = 0.2
#: the floater numbers (Zoo's README): proud of whatever is drawn beneath, a skirt into the host
PROUD = 0.003
SKIRT = 0.004
#: a relief's height off the lid: a flat floater's minimum
RELIEF = PROUD
#: the throat in the kerb face: its sill above the road and its head below the band's top
THROAT_SILL = 0.015
THROAT_HEAD = 0.025
DRAIN_CELL_M = 32.0
#: a mid-run cover keeps this far inside a road's drawn slab
END_MARGIN = 2.0
SEGMENTS = 24
IRON = (0.17, 0.155, 0.14)
VOID = (0.02, 0.02, 0.02)


def _face_offset(road, kerb):
    """The kerb face's offset across ``road``: the band's road-side edge."""
    return kerb.offset - kerb.sign * road.sidewalk / 2.0


def _cut_span(kerb, cut):
    """``(t0, t1)`` of the stretch a cut drops in ``kerb``: the kerb's own span round the cut's
    station (`site_streets.split_span` adds `CUT_MARGIN` each side of the crossing), or the
    crossing's span when the kerb has none."""
    for t0, t1, is_cut in kerb.spans:
        if is_cut and t0 <= cut.t <= t1:
            return t0, t1
    return cut.t - cut.span / 2.0, cut.t + cut.span / 2.0


def _junctions(roads_list):
    """{rounded plan point: (x, y)} of every road-road crossing's centre, once a junction."""
    out = {}
    for road in roads_list:
        for c in road.crossings:
            if c.kind != "road":
                continue
            x, y = road.point(c.t, 0.0)
            key = (round(x, site_furniture.CORNER_TOL), round(y, site_furniture.CORNER_TOL))
            out.setdefault(key, (x, y))
    return out


def _run_covers(road):
    """Stations along a street (a road with a sidewalk) where a cover keeps the run under
    `MANHOLE_SPACING_MAX`: between two junctions as many as divide the gap, and from the last
    junction toward the site's edge one every `MANHOLE_SPACING_MAX` while the slab lasts. A street
    with no junction anchors at its slab's middle."""
    lo, hi = road.slab
    anchors = sorted(c.t for c in road.crossings if c.kind == "road" and lo <= c.t <= hi)
    out = []
    if not anchors:
        mid = (lo + hi) / 2.0
        out.append(mid)
        anchors = [mid]
    for a, b in zip(anchors, anchors[1:]):
        n = int(math.ceil((b - a) / MANHOLE_SPACING_MAX - 1e-9))
        out += [a + (b - a) * k / n for k in range(1, n)]
    t = anchors[0] - MANHOLE_SPACING_MAX
    while t >= lo + END_MARGIN:
        out.append(t)
        t -= MANHOLE_SPACING_MAX
    t = anchors[-1] + MANHOLE_SPACING_MAX
    while t <= hi - END_MARGIN:
        out.append(t)
        t += MANHOLE_SPACING_MAX
    return sorted(out)


def _rect_hits(at, half, cover, clear):
    """Whether a square of half-size ``half`` at plan ``at`` meets any cover piece's footprint
    (``size`` = [x, h, y] in plan) inflated by ``clear``."""
    for p in cover:
        size, pat = p.get("size"), p.get("at")
        if not size or not pat:
            continue
        hx, hy = float(size[0]) / 2.0 + clear + half, float(size[2]) / 2.0 + clear + half
        if abs(at[0] - pat[0]) < hx and abs(at[1] - pat[1]) < hy:
            return True
    return False


def plan(roads_list, cover=()):
    """The site's drains: a list of records, each ``kind`` "manhole", "inlet" or "walk_cover", with
    ``at`` (plan), ``yaw`` (degrees, the road's) and ``road``; an inlet also carries ``face`` -- the
    point on the kerb face behind its centre -- and ``toward``, the unit plan vector from the kerb face
    to the road. ``cover`` is the site's furniture and cover, which a sidewalk lid keeps clear of."""
    out = []
    junctions = _junctions(roads_list)
    for key in sorted(junctions):
        x, y = junctions[key]
        road = next(r for r in roads_list if any(
            c.kind == "road" and math.hypot(r.point(c.t, 0.0)[0] - x, r.point(c.t, 0.0)[1] - y) < 0.2
            for c in r.crossings))
        out.append({"kind": "manhole", "at": [round(x, 3), round(y, 3)],
                    "yaw": round(road.angle_deg, 3), "road": road.index, "why": "junction"})
    for road in roads_list:
        if not road.sidewalk:
            continue
        for t in _run_covers(road):
            x, y = road.point(t, 0.0)
            if any(math.hypot(x - p["at"][0], y - p["at"][1]) < 1.0 for p in out):
                continue
            out.append({"kind": "manhole", "at": [round(x, 3), round(y, 3)],
                        "yaw": round(road.angle_deg, 3), "road": road.index, "why": "run",
                        "t": round(t, 3)})
    corners, walks = set(), []
    for road in roads_list:
        if not road.sidewalk:
            continue
        for kerb in road.kerbs:
            face = _face_offset(road, kerb)
            toward = (-kerb.sign * road.perp[0], -kerb.sign * road.perp[1])
            for c in sorted(kerb.cuts, key=lambda c: c.t):
                if c.kind != "road":
                    continue
                # the kerb's own dropped stretch: the crossing's span and `CUT_MARGIN` each side
                lo, hi = _cut_span(kerb, c)
                for side in (-1, 1):
                    edge = hi if side > 0 else lo
                    t = edge + side * (INLET_CLEAR + INLET_L / 2.0)
                    if not (0.0 < t - INLET_L / 2.0 and t + INLET_L / 2.0 < road.length):
                        continue
                    if not site_furniture._clear_of_cuts(t, INLET_L / 2.0, kerb, 0.0):
                        continue
                    x, y = road.point(t, face - kerb.sign * INLET_D / 2.0)
                    key = site_furniture.corner_key(road, c.t, (x, y))
                    if key in corners:
                        continue
                    corners.add(key)
                    fx, fy = road.point(t, face)
                    out.append({"kind": "inlet", "at": [round(x, 3), round(y, 3)],
                                "yaw": round(road.angle_deg, 3), "road": road.index,
                                "kerb": kerb.side, "t": round(t, 3),
                                "face": [round(fx, 3), round(fy, 3)],
                                "toward": [round(toward[0], 6), round(toward[1], 6)]})
                    # the lid a step behind it, if the band is wide enough, nothing stands
                    # there, and no other lid is near
                    if STEP_BEHIND + WALK_COVER / 2.0 > road.sidewalk - 0.1:
                        continue
                    wx, wy = road.point(t, face + kerb.sign * STEP_BEHIND)
                    if any(math.hypot(wx - w[0], wy - w[1]) < WALK_COVER_MIN_SPACING for w in walks):
                        continue
                    if _rect_hits((wx, wy), WALK_COVER / 2.0, cover, FURNITURE_CLEAR):
                        continue
                    walks.append((wx, wy))
                    out.append({"kind": "walk_cover", "at": [round(wx, 3), round(wy, 3)],
                                "yaw": round(road.angle_deg, 3), "road": road.index,
                                "kerb": kerb.side, "t": round(t, 3)})
    return out


class _Mesh:
    """Triangles in the plan frame, each counter-clockwise about its outward normal."""

    def __init__(self):
        self.tris = []

    def tri(self, a, b, c):
        self.tris.append((a, b, c))

    def quad(self, a, b, c, d):
        """``a b c d`` counter-clockwise about the outward normal."""
        self.tri(a, b, c)
        self.tri(a, c, d)


def _rot(cx, cy, yaw):
    ca, sa = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return lambda lx, ly: (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)


def _frustum(m, cx, cy, r_top, r_bot, z_top, z_bot, yaw=0.0, n=SEGMENTS):
    """A lid: a disc on top, its side splayed from ``r_top`` to ``r_bot``; no bottom."""
    at = _rot(cx, cy, yaw)
    top = [at(r_top * math.cos(2 * math.pi * i / n), r_top * math.sin(2 * math.pi * i / n)) for i in range(n)]
    bot = [at(r_bot * math.cos(2 * math.pi * i / n), r_bot * math.sin(2 * math.pi * i / n)) for i in range(n)]
    c = (cx, cy, z_top)
    for i in range(n):
        j = (i + 1) % n
        m.tri(c, top[i] + (z_top,), top[j] + (z_top,))
        m.quad(bot[i] + (z_bot,), bot[j] + (z_bot,), top[j] + (z_top,), top[i] + (z_top,))


def _ring(m, cx, cy, r_in, r_out_top, r_out_bot, z_top, z_bot, yaw=0.0, n=SEGMENTS):
    """A frame: an annulus on top from ``r_in`` out, and its outer side; no inner wall, no bottom
    (what fills the ring covers both)."""
    at = _rot(cx, cy, yaw)
    for i in range(n):
        j = (i + 1) % n
        ai, aj = 2 * math.pi * i / n, 2 * math.pi * j / n
        ii, ij = at(r_in * math.cos(ai), r_in * math.sin(ai)), at(r_in * math.cos(aj), r_in * math.sin(aj))
        oi, oj = (at(r_out_top * math.cos(ai), r_out_top * math.sin(ai)),
                  at(r_out_top * math.cos(aj), r_out_top * math.sin(aj)))
        bi, bj = (at(r_out_bot * math.cos(ai), r_out_bot * math.sin(ai)),
                  at(r_out_bot * math.cos(aj), r_out_bot * math.sin(aj)))
        m.quad(ii + (z_top,), oi + (z_top,), oj + (z_top,), ij + (z_top,))
        m.quad(bi + (z_bot,), bj + (z_bot,), oj + (z_top,), oi + (z_top,))


def _box(m, cx, cy, lx0, ly0, lx1, ly1, z_top, z_bot, yaw=0.0):
    """A block from local (lx0, ly0) to (lx1, ly1) about (cx, cy) turned by ``yaw``: its top and
    four sides; no bottom."""
    at = _rot(cx, cy, yaw)
    p = [at(lx0, ly0), at(lx1, ly0), at(lx1, ly1), at(lx0, ly1)]
    m.quad(*(q + (z_top,) for q in p))
    for i in range(4):
        a, b = p[i], p[(i + 1) % 4]
        m.quad(a + (z_bot,), b + (z_bot,), b + (z_top,), a + (z_top,))


def _manhole(m, piece, top, base):
    """The frame a ring at ``top``, the lid a bevelled disc 2 mm above it -- ring and lid never
    overlap in plan, so the step is an edge and not a fight -- and on the lid a band across the
    middle, where a cover carries its one cast word, and a field of studs."""
    cx, cy = piece["at"]
    yaw = piece["yaw"]
    _ring(m, cx, cy, COVER_R, FRAME_R - 0.006, FRAME_R, top, base, yaw)
    lid_top = top + 0.002
    _frustum(m, cx, cy, COVER_R - 0.004, COVER_R, lid_top, top - 0.004, yaw)
    relief = lid_top + RELIEF
    _box(m, cx, cy, -0.20, -0.03, 0.20, 0.03, relief, lid_top - 0.001, yaw)
    pitch, half = 0.06, 0.014
    k = int((COVER_R - 0.04) // pitch)
    for i in range(-k, k + 1):
        for j in range(-k, k + 1):
            lx, ly = i * pitch, j * pitch
            if math.hypot(lx, ly) > COVER_R - 0.045 or abs(ly) < 0.05:
                continue
            _box(m, cx, cy, lx - half, ly - half, lx + half, ly + half, relief, lid_top - 0.001, yaw)


def _inlet(iron, void, piece, top, base, road_top, band_top):
    """The grate in the gutter -- a frame round an open dark well, bars across it -- and the throat:
    a dark opening in the kerb face behind it."""
    cx, cy = piece["at"]
    yaw = piece["yaw"]
    hl, hd, w = INLET_L / 2.0, INLET_D / 2.0, 0.05
    at = _rot(cx, cy, yaw)
    well = [at(-hl + w, -hd + w), at(hl - w, -hd + w), at(hl - w, hd - w), at(-hl + w, hd - w)]
    void.quad(*(q + (top,) for q in well))
    bars = top + RELIEF
    _box(iron, cx, cy, -hl, -hd, hl, -hd + w, bars, base, yaw)
    _box(iron, cx, cy, -hl, hd - w, hl, hd, bars, base, yaw)
    _box(iron, cx, cy, -hl, -hd + w, -hl + w, hd - w, bars, base, yaw)
    _box(iron, cx, cy, hl - w, -hd + w, hl, hd - w, bars, base, yaw)
    n = 9
    for i in range(1, n):
        lx = -hl + w + (2 * (hl - w)) * i / n
        _box(iron, cx, cy, lx - 0.015, -hd + w, lx + 0.015, hd - w, bars, top - 0.001, yaw)
    # the throat: in the kerb face behind the grate, PROUD of it toward the road
    fx, fy = piece["face"]
    tx, ty = piece["toward"]
    ux, uy = -ty, tx                       # along the kerb
    px, py = fx + tx * PROUD, fy + ty * PROUD
    a = (px - ux * hl, py - uy * hl)
    b = (px + ux * hl, py + uy * hl)
    z0, z1 = road_top + THROAT_SILL, band_top - THROAT_HEAD
    # counter-clockwise seen from the road (from +toward): a, b along u, then up
    if (b[0] - a[0]) * ty - (b[1] - a[1]) * tx > 0:
        a, b = b, a
    void.quad(a + (z0,), b + (z0,), b + (z1,), a + (z1,))


def _walk_cover(m, piece, top, base):
    """A square lid in the sidewalk: a frame, and the plate inside it a relief above."""
    cx, cy = piece["at"]
    yaw = piece["yaw"]
    h = WALK_COVER / 2.0
    _box(m, cx, cy, -h, -h, h, h, top, base, yaw)
    _box(m, cx, cy, -h + 0.025, -h + 0.025, h - 0.025, h - 0.025, top + RELIEF, top - 0.001, yaw)


def _obj(name, tris, comment):
    """An OBJ of ``tris``: Godot's frame, a normal a face, planar UVs in metres."""
    lines = [f"# Lot: {comment}", f"o {name}"]
    vs, vn, vt, fs = [], [], [], []
    for a, b, c in tris:
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        wx, wy, wz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        vn.append((nx / ln, nz / ln, -ny / ln))
        k = len(vs)
        for p in (a, b, c):
            vs.append((p[0], p[2], -p[1]))
            vt.append((p[0], p[1]))
        fs.append((k + 1, k + 2, k + 3, len(vn)))
    lines += [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in vs]
    lines += [f"vt {u:.4f} {v:.4f}" for u, v in vt]
    lines += [f"vn {x:.5f} {y:.5f} {z:.5f}" for x, y, z in vn]
    lines += [f"f {a}/{a}/{n} {b}/{b}/{n} {c}/{c}/{n}" for a, b, c, n in fs]
    return "\n".join(lines) + "\n"


def meshes(pieces, road_top, paint_top, band_top):
    """``(body_lines, sub_lines, files)`` for the drains: one mesh a material a `DRAIN_CELL_M` cell,
    an OBJ beside the scene, each stood by a MeshInstance3D that casts no shadow. ``road_top`` is the
    asphalt's top, ``paint_top`` the road paint's, ``band_top`` the sidewalk's."""
    cells = {}
    for p in pieces:
        cell = (int(math.floor(p["at"][0] / DRAIN_CELL_M)), int(math.floor(p["at"][1] / DRAIN_CELL_M)))
        iron, void = cells.setdefault(cell, (_Mesh(), _Mesh()))
        if p["kind"] == "manhole":
            _manhole(iron, p, paint_top + PROUD, road_top - SKIRT)
        elif p["kind"] == "inlet":
            _inlet(iron, void, p, paint_top + PROUD, road_top - SKIRT, road_top, band_top)
        elif p["kind"] == "walk_cover":
            _walk_cover(iron, p, band_top + PROUD, band_top - SKIRT)
    body, sub, files = [], [], {}
    used = set()
    for cx, cy in sorted(cells):
        for mat, mesh in zip(("iron", "void"), cells[(cx, cy)]):
            if not mesh.tris:
                continue
            name = f"site_drains_{mat}_c{cx + 500:03d}_{cy + 500:03d}"
            files[f"{name}.obj"] = _obj(name, mesh.tris,
                                        f"the site's drains ({mat}), cell ({cx}, {cy}) of {DRAIN_CELL_M:g} m")
            body += [f'[node name="{name}" type="MeshInstance3D" parent="."]',
                     f'mesh = ExtResource("{name}")',
                     f'material_override = SubResource("Mat_site_drains_{mat}")',
                     "cast_shadow = 0", ""]
            used.add(mat)
    for mat, colour, rough in (("iron", IRON, 0.8), ("void", VOID, 1.0)):
        if mat in used:
            r, g, b = colour
            sub += [f'[sub_resource type="StandardMaterial3D" id="Mat_site_drains_{mat}"]',
                    f"albedo_color = Color({r:g}, {g:g}, {b:g}, 1)", f"roughness = {rough:g}", ""]
    return body, sub, files
