"""
site_posters.py  --  handbills on the alley walls and the poles
===============================================================
Lot 0.84.0. The walker, 2026-09-29, choosing where posters go: strip club
interiors, bar interiors, "exterior alley walls and poles", store windows and
walls. Deli Counter 0.163.0 hangs the interior three; this is the outdoor one.
Zoo builds the art: `poster_wall` in its `alley` form -- day-glo handbills, a
collage of two courses on a wall, torn and taped (Zoo 1.30.0, from the lewd
poster guide's "Alley / telephone pole" row: layered, torn handbills).

WHAT THIS WRITES IS NOT COVER. Everything in `site_spec["cover"]` is read as
something a body takes cover behind -- pacing counts it, the cover test points
come from it, the audit and the layout lint read it. A poster is paper on a
wall, so these records go to `site_spec["hung"]`, which only the slot writer,
the module resolver and the scene writer read (`lot.write_site_slots`,
`lot.cover_module_refs(key="hung")`, `lot._outdoor_nodes`). A hung record
carries its own mount height ``z`` (the centre, above the plate) and has no
collision.

AN ALLEY WALL, which Lot had no word for (the survey of 2026-09-30: nothing
classified a facade as street-facing or rear). Derived, not declared, and
read as a building's BACK-OF-HOUSE wall because no layout here has a true
alley yet (measured; see `plan_alley_walls`): a true alley first -- a side
facing another building across a gap a body walks, `ALLEY_MIN` to
`ALLEY_MAX`, with no road in it -- then the rear, opposite the side the sign
faces (the street, `lot.sign_placement`'s rule), then a side wall. Never the
street facade, and clear of the wall's storey-0 openings, read through
`site_enterability.wall_of` (a build writes `ext_0_S`, preview `S`).

A POLE is a streetlight or a sign post already standing (`site_furniture`).
One handbill -- a single alley sheet -- on the face AWAY from the road, where
the sidewalk is; every other pole by a hash of its name, so a street is not
papered on every pole and the choice does not move when a pole is added
elsewhere.

Heights are the gameplay camera's eye (Deli Counter's
`agent_contract.eye_height`, 1.6), duplicated here as the body-fit numbers in
`site_enterability` are: Lot is a standalone repo with no Deli Counter import.
Keep the two in step.
"""

from __future__ import annotations

import math
import zlib

#: Deli Counter's `agent_contract.eye_height()` (`review.gameplay_camera_eye_m`).
EYE = 1.6
#: Deli Counter builds an exterior wall centred on its footprint's edge at this
#: thickness (its `LevelSpec.wall_thick` default); a building's gameplay.json
#: does not carry it, so the outer face is the footprint edge plus half.
WALL_THICK = 0.3
#: Air between a poster's back and the face it is pasted on.
AIR = 0.004
#: Zoo's `poster_wall` genome: the depth a run is built at.
DEPTH = 0.01
#: The band a wall slot asks Zoo to fill: `poster_wall_forms.band_height
#: ("alley", 2)`, a two-course collage whose sheets wander down it. Pinned
#: against Zoo in tests/test_site_posters.py.
#:
#: (0.84.0-0.85.0 also hung ONE flat alley sheet on a pole -- first at a band
#: one sheet cannot fill, which Zoo refused in cold run 9116, then at the
#: sheet's own 0.42. Cold run 9118 showed a 0.30 m sheet standing proud of a
#: 0.12 m pole reads as a small sign; the walker sent photographs of real
#: poles, and Zoo 1.34.0 drew them. 0.86.0 hangs `pole_flyers` instead.)
BAND_WALL = 0.814
#: A gap a body walks and a wall faces across: under ALLEY_MIN two buildings
#: are a party wall, over ALLEY_MAX a lot. 6.7 m is the night strip's alleys
#: (tools/walk_night_strip.gd).
ALLEY_MIN = 1.5
ALLEY_MAX = 12.0
#: How much of the wall a neighbour must face before it is an alley at all.
FACING_MIN = 2.0
#: Kept off a wall's corners and off each opening, metres.
CORNER_KEEP = 1.0
OPENING_KEEP = 0.4
#: A run: at least three sheets, at most ten.
RUN_MIN = 0.9
RUN_MAX = 3.0
#: Runs on one true alley wall, and on one building in all.
RUNS_PER_WALL = 2
RUNS_PER_BUILDING = 2
#: Zoo's `poster_wall` genome `module_variants` for the alley form... and why
#: four: as in Deli Counter's pieces, two runs of one width and one variant
#: are the same sheets in the same order.
VARIANTS = 4
#: THE POLES (0.86.0): the species flyers go on, and the radius a sleeve
#: round each must clear. Zoo's streetlight pole is a 0.06 m cylinder at the
#: slot's centre; the sign post a 0.10 m square u-channel, whose CORNERS are
#: its half-diagonal out (0.0707), not its half-width -- a sleeve at the
#: half-width would pass through them.
POLES = {"streetlight": 0.06, "sign_post": 0.0707}
#: Zoo `pole_flyers_forms`: a sleeve is `LAYERS` papers `LAYER` apart, the
#: innermost `AIR` off the pole, so its outer radius is pole + AIR + 3 LAYER.
#: Pinned against Zoo in tests/test_site_posters.py.
FLYER_LAYERS = 4
FLYER_LAYER = 0.004
#: The tiers a pole can carry, from the walker's photographs: bare, two
#: sheets, a column, wrapped. Their bands (height of paper, metres) and where
#: the paper starts above the sidewalk -- different per tier, so no two tiers
#: share a centreline (the placement guide's "repeated perfect centerline"
#: tell): a pair at the head, a column at the chest, a wrap from the knee.
#: Each start moves by up to `START_JITTER`, pole to pole.
TIERS = ("bare", "pair", "stack", "wrap")
TIER_BAND = {"pair": 0.78, "stack": 1.12, "wrap": 1.72}
TIER_START = {"pair": 1.22, "stack": 0.86, "wrap": 0.36}
START_JITTER = 0.1
#: Paper stops where a standing person can still paste it (the guide:
#: "Posters placed far above reach need a reason"), and on a sign post under
#: its blade (Lot's MUTCD blades are 0.3048 m tall at the top of a 2.4384 m
#: post), a hand clear of it.
REACH = 2.1
BLADE_CLEAR = round(2.4384 - 0.3048 - 0.05, 4)
#: How papered a pole is, by a hash of its name: the share of poles at each
#: tier; and one tier denser near a junction -- the corner poles are where a
#: street's flyers go ("a known place for flyers", the placement guide).
TIER_SHARE = (0.30, 0.35, 0.22, 0.13)
JUNCTION_M = 10.0
#: THE NIGHT'S KEY LIGHT, as Lux's `delco_night` preset sets it (0.85.0): the
#: moon at elevation 38, azimuth 300 degrees. Cold run 9117 measured what it
#: means for paper: of 21 hung posters, every one facing south or west read
#: 43-101 luma at its centre and every one facing north read 0.0 -- the moon
#: reaches the faces turned toward it and the night has little else. Pinned
#: against the preset file in tests/test_site_posters.py when Lux is beside
#: this repo; `light_from` is Lux's own convention.
NIGHT_ELEVATION_DEG = 38.0
NIGHT_AZIMUTH_DEG = 300.0
#: How squarely a face must turn to the key light to count as lit: a dot
#: product in plan. 9117's least-lit measured faces (south, 0.50 to the moon)
#: read 43-68; its dark ones faced away (-0.50 and below). A quarter keeps a
#: face that grazes the light from counting.
LIT_MIN = 0.25

CODE_ALLEY_POSTERS = "LOT_ALLEY_POSTERS"


def _h(*k):
    return zlib.crc32("|".join(str(v) for v in k).encode("utf-8")) & 0xFFFFFFFF


def light_from(elevation_deg=NIGHT_ELEVATION_DEG, azimuth_deg=NIGHT_AZIMUTH_DEG):
    """The plan direction (unit) from a surface TOWARD the key light, by
    Lux's convention (`lux_root._preset_key_dir`: rotate about up by the
    azimuth, then about the rotated x by minus the elevation; the light lies
    along +Z of that basis), with plan = Godot (x, -z), normalised in plan.
    For `delco_night`, (-0.866, -0.500): west-south-west, which is what 9117
    measured lit. (The 3-D vector is (-0.682, 0.616, 0.394) in Godot.)"""
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    # +Z of R_x'(-e) * R_y(a), worked out: the basis's z column
    gx = math.sin(a) * math.cos(e)
    gz = math.cos(a) * math.cos(e)
    # (Godot +Z after the yaw is (sin a, 0, cos a); the pitch about the
    # rotated x keeps its plan direction and scales it by cos e.)
    n = math.hypot(gx, gz) or 1.0
    return (gx / n, -gz / n)


def facing_yaw(nx, ny):
    """The slot yaw that turns a module's front -- local -y, as Zoo builds a
    poster run and a sign blade -- to face plan direction ``(nx, ny)``: Lot
    turns a plate to face ``(sin yaw, -cos yaw)`` (`site_furniture.plate_facing`)."""
    return round(math.degrees(math.atan2(nx, -ny)) % 360.0, 4)


def _sides(rect):
    """``(side, nx, ny, line, lo, hi)`` for a rect's four sides: the outward
    normal, the coordinate the side lies on, and its span along it."""
    x0, y0, x1, y1 = rect
    return (("S", 0.0, -1.0, y0, x0, x1), ("N", 0.0, 1.0, y1, x0, x1),
            ("W", -1.0, 0.0, x0, y0, y1), ("E", 1.0, 0.0, x1, y0, y1))


def _street_side(bdef, roads):
    """The side `lot.sign_placement` hangs the sign on: the street."""
    import lot
    got = lot.sign_placement(bdef, roads)
    if got is None:
        return None
    x, y, yaw, _f = got
    return {270.0: "S", 90.0: "N", 180.0: "W", 0.0: "E"}.get(float(yaw))


def _road_in(roads, rect):
    """Does any road's carriageway cross the plan rect?"""
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for road in roads or []:
        dx, dy = cx - road.a[0], cy - road.a[1]
        t = max(0.0, min(road.length, dx * road.along[0] + dy * road.along[1]))
        px, py = road.point(t)
        # distance from the rect to the road's centre line, against its half width
        ex = max(x0 - px, 0.0, px - x1)
        ey = max(y0 - py, 0.0, py - y1)
        if math.hypot(ex, ey) <= road.width / 2.0 + getattr(road, "sidewalk", 0.0):
            return True
    return False


def _openings_on(merged, bdef, rect, side):
    """``[(u, half_width)]``: the storey-0 exterior openings on this world
    side of the building, ``u`` along the side."""
    import site_enterability as SE
    at, rot = bdef["at"], float(bdef.get("rot", 0) or 0)
    out = []
    x0, y0, x1, y1 = rect
    for op in merged.get("openings", []) or []:
        if op.get("building") != bdef["id"]:
            continue
        where = SE.wall_of(op.get("wall"), op.get("story"))
        if where is None or not where[0] or where[1] != 0:
            continue
        ex, ey = SE._rot(float(op.get("x", 0.0)), float(op.get("y", 0.0)), rot)
        ex, ey = ex + at[0], ey + at[1]
        # the world side it is on: the nearest edge of the world rect
        d = {"S": abs(ey - y0), "N": abs(ey - y1), "W": abs(ex - x0), "E": abs(ex - x1)}
        if min(d, key=d.get) != side:
            continue
        u = ex if side in ("S", "N") else ey
        out.append((u, float(op.get("width") or 1.0) / 2.0))
    return out


def _free(lo, hi, holes):
    """The intervals of ``[lo, hi]`` outside every ``(a, b)`` in ``holes``."""
    out = [(lo, hi)]
    for a, b in sorted(holes):
        nxt = []
        for s, e in out:
            if b <= s or a >= e:
                nxt.append((s, e))
                continue
            if a > s:
                nxt.append((s, a))
            if b < e:
                nxt.append((b, e))
        out = nxt
    return [(s, e) for s, e in out if e - s > 1e-6]


_OPPOSITE = {"S": "N", "N": "S", "W": "E", "E": "W"}


def _facing(side, line, lo, hi, other):
    """``(gap, a, c)``: how far ``other``'s rect stands off this side, and the
    stretch of the side it faces; None when it is not in front of it."""
    ox0, oy0, ox1, oy1 = other
    if side in ("S", "N"):
        gap = (line - oy1) if side == "S" else (oy0 - line)
        a, c = max(lo, ox0), min(hi, ox1)
    else:
        gap = (line - ox1) if side == "W" else (ox0 - line)
        a, c = max(lo, oy0), min(hi, oy1)
    if gap < 0.0 or c <= a:
        return None
    return gap, a, c


def _strip(side, line, a, c, gap):
    """The plan rect between this side and something ``gap`` in front of it."""
    if side == "S":
        return (a, line - gap, c, line)
    if side == "N":
        return (a, line, c, line + gap)
    if side == "W":
        return (line - gap, a, line, c)
    return (line, a, line + gap, c)


def _plate_room(site_spec, side, line):
    """Metres from this side to the plate's edge in front of it, or None
    when the site declares no ground."""
    import site_extent
    try:
        x0, y0, x1, y1 = site_extent.resolve(site_spec).rect
    except Exception:  # noqa: BLE001 -- no ground: nothing in front to measure
        return None
    return {"S": line - y0, "N": y1 - line, "W": line - x0, "E": x1 - line}[side]


def plan_alley_walls(site_spec, merged, roads, findings=None):
    """Hung records for the walls behind the street: at most
    `RUNS_PER_BUILDING` runs a building.

    WHICH WALLS, and why not only true alleys. Measured 2026-09-30 before this
    was written: over Lot's 28 site specs and Level Factory's `club_block_014`
    lot, NO two buildings face each other across `ALLEY_MIN`..`ALLEY_MAX` --
    generated lots stand their buildings in a row 25-45 m apart or offset on
    both axes, and the "commercial -> alley -> rowhomes" seam is still
    unimplemented (docs/LEVEL_RECIPE.md). A rule for true alleys only would
    never fire. So a building's back-of-house walls are read as its alley
    walls, in this order:

      1. a TRUE ALLEY -- a side facing another building across a walkable
         gap with no road in it -- up to `RUNS_PER_WALL` runs, on the stretch
         the neighbour faces;
      2. the REAR, the side opposite the street (`lot.sign_placement`);
      3. the side facing the NEAREST neighbour, then the other one.

    Never the street facade, never a side with less than `ALLEY_MIN` in
    front of it (a neighbour or the plate's edge: nobody stands there to read
    it), never over a storey-0 opening.
    """
    import site_spawns
    blds = [b for b in site_spec.get("buildings", []) or []
            if site_spawns.footprint_rect(b) is not None]
    rects = {b["id"]: site_spawns.footprint_rect(b) for b in blds}
    out = []
    alleys = 0
    for b in blds:
        rect = rects[b["id"]]
        street = _street_side(b, roads)
        cx, cy = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
        sides = {s[0]: s for s in _sides(rect)}
        # (priority, side, spans, why): spans of the side to paper
        plans = []
        for side, nx, ny, line, lo, hi in sides.values():
            if side == street:
                continue
            room = _plate_room(site_spec, side, line)
            if room is not None and room < ALLEY_MIN:
                continue
            close, alley_spans = [], []
            for o in blds:
                if o["id"] == b["id"]:
                    continue
                got = _facing(side, line, lo, hi, rects[o["id"]])
                if got is None:
                    continue
                gap, a, c = got
                if gap < ALLEY_MIN:
                    close.append((a, c))
                elif (gap <= ALLEY_MAX and c - a >= FACING_MIN
                      and not _road_in(roads, _strip(side, line, a, c, gap))):
                    alley_spans.append((a, c, o["id"], gap))
            whole = [(lo, hi, None, None)]
            if alley_spans:
                plans.append((0, side, alley_spans, close, "alley"))
            elif street is not None and side == _OPPOSITE[street]:
                plans.append((1, side, whole, close, "rear"))
            else:
                near = min((math.hypot((r[0] + r[2]) / 2.0 - cx, (r[1] + r[3]) / 2.0 - cy)
                            for oid, r in rects.items() if oid != b["id"]
                            and (r[0] + r[2] - 2 * cx) * nx + (r[1] + r[3] - 2 * cy) * ny > 0),
                           default=1e9)
                plans.append((2 + near / 1e6, side, whole, close, "side"))
        placed_b = 0
        for _pri, side, spans, close, why in sorted(plans, key=lambda t: t[0]):
            if placed_b >= RUNS_PER_BUILDING:
                break
            _s, nx, ny, line, lo, hi = sides[side]
            holes = [(u - w - OPENING_KEEP, u + w + OPENING_KEEP)
                     for u, w in _openings_on(merged, b, rect, side)] + list(close)
            per_wall = RUNS_PER_WALL if why == "alley" else 1
            placed = 0
            for a, c, oid, gap in sorted(spans, key=lambda s_: -(s_[1] - s_[0])):
                free = _free(max(a, lo + CORNER_KEEP), min(c, hi - CORNER_KEEP), holes)
                for s_, e in sorted(free, key=lambda iv: -(iv[1] - iv[0])):
                    if placed >= per_wall or placed_b >= RUNS_PER_BUILDING:
                        break
                    w = math.floor(min(RUN_MAX, e - s_) * 10.0) / 10.0   # whole decimetres, inside
                    if w < RUN_MIN:
                        continue
                    u = (s_ + e) / 2.0
                    off = WALL_THICK / 2.0 + AIR + DEPTH / 2.0
                    x, y = ((u, line + ny * off) if side in ("S", "N")
                            else (line + nx * off, u))
                    name = f"alley_poster_{b['id']}_{side}_{placed}"
                    extra = {"wall": why}
                    if oid is not None:
                        extra.update(faces=oid, gap=round(gap, 3))
                        alleys += 1
                    out.append(_record(name, (x, y), facing_yaw(nx, ny),
                                       (w, DEPTH, BAND_WALL), EYE,
                                       host=f"wall:{b['id']}:{side}", **extra))
                    placed += 1
                    placed_b += 1
    if findings is not None:
        findings.append(f"{CODE_ALLEY_POSTERS}: {len(out)} run(s) on back-of-house walls, "
                        f"{alleys} of them facing a neighbour across an alley")
    return out


def _nearest(roads, px, py):
    """``(distance, point, road)`` for the road nearest (px, py), or None."""
    best = None
    for road in roads or []:
        dx, dy = px - road.a[0], py - road.a[1]
        t = max(0.0, min(road.length, dx * road.along[0] + dy * road.along[1]))
        q = road.point(t)
        d = math.hypot(px - q[0], py - q[1])
        if best is None or d < best[0]:
            best = (d, q, road)
    return best


def _near_junction(roads, px, py, own):
    """Is a road other than the pole's own within `JUNCTION_M` of its edge?"""
    for road in roads or []:
        if road is own:
            continue
        dx, dy = px - road.a[0], py - road.a[1]
        t = max(0.0, min(road.length, dx * road.along[0] + dy * road.along[1]))
        q = road.point(t)
        if math.hypot(px - q[0], py - q[1]) <= road.width / 2.0 + JUNCTION_M:
            return True
    return False


def tier_for(name, junction):
    """The pole's tier: `TIER_SHARE` by a hash of its name, one denser at a
    junction."""
    u = (_h(name, "tier") % 10000) / 10000.0
    acc, t = 0.0, 0
    for t, share in enumerate(TIER_SHARE):
        acc += share
        if u < acc:
            break
    if junction:
        t = min(len(TIERS) - 1, t + 1)
    return TIERS[t]


def plan_pole_bills(site_spec, roads, findings=None):
    """Hung `pole_flyers` sleeves round the streetlights and sign posts.

    Each pole gets a tier (`tier_for`); a band that starts where that tier
    starts (jittered) and stops within reach -- and under a sign post's
    blade; and a front that faces the night's key light by 0.85.0's rule: of
    the pole's four faces, sidewalk side first, the first turned to the
    light by `LIT_MIN`. A wrap is paper all round; its front is only where
    its newest sheets begin."""
    out, tiers = [], {t: 0 for t in TIERS}
    for i, cv in enumerate(site_spec.get("cover", []) or []):
        sp = cv.get("species")
        if sp not in POLES or not cv.get("at"):
            continue
        px, py = cv["at"]
        near = _nearest(roads, px, py)
        if near is None or near[0] < 1e-6:
            continue
        name = cv.get("name") or f"cover_{i}"
        tier = tier_for(name, _near_junction(roads, px, py, near[2]))
        tiers[tier] += 1
        if tier == "bare":
            continue
        ax, ay = (px - near[1][0]) / near[0], (py - near[1][1]) / near[0]
        lx, ly = LIGHT
        faces = (("sidewalk", ax, ay), ("along", -ay, ax), ("along", ay, -ax),
                 ("road", -ax, -ay))
        side, nx, ny = next(((f, x, y) for f, x, y in faces if x * lx + y * ly >= LIT_MIN),
                            max(faces, key=lambda f_: f_[1] * lx + f_[2] * ly))
        top_max = min(REACH, BLADE_CLEAR) if sp == "sign_post" else REACH
        band = TIER_BAND[tier]
        start = TIER_START[tier] + ((_h(name, "start") % 2001) / 1000.0 - 1.0) * START_JITTER
        start = max(0.05, min(start, top_max - band))
        diameter = round(2.0 * (POLES[sp] + AIR + (FLYER_LAYERS - 1) * FLYER_LAYER), 3)
        out.append(_record(f"pole_flyers_{i}", (px, py), facing_yaw(nx, ny),
                           (diameter, diameter, band),
                           # rounded DOWN: to the millimetre, a centre
                           # rounded to nearest lifted a top 0.4 mm past the
                           # blade's limit
                           math.floor((start + band / 2.0) * 1e4) / 1e4,
                           host=f"pole:cover_{i}", base=cv.get("base"),
                           species="pole_flyers", form=tier, face=side,
                           lit=round(nx * lx + ny * ly, 3)))
    if findings is not None:
        findings.append(f"{CODE_ALLEY_POSTERS}: {len(out)} pole(s) papered -- "
                        + ", ".join(f"{t} {n}" for t, n in tiers.items()))
    return out


def _record(name, at, yaw, dims, z, host, base=None, species="poster_wall", form="alley",
            **extra):
    w, d, h = dims
    rec = {"name": name, "species": species, "form": form,
           "variant": _h(name) % VARIANTS,
           "at": [round(at[0], 4), round(at[1], 4)], "yaw": yaw,
           "dims": [w, d, h], "z": z, "base": base, "host": host,
           "source": "site_posters"}
    rec.update(extra)
    return rec


LIGHT = light_from()


def plan(site_spec, merged, roads, findings=None):
    """Every hung poster record for the site: alley walls, then poles."""
    return (plan_alley_walls(site_spec, merged, roads, findings)
            + plan_pole_bills(site_spec, roads, findings))
