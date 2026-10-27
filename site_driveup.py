"""
site_driveup.py  --  a bank's drive-up lane beside its wall
==========================================================
The walker's bank list, outside (the factory's docs/reference/BANK_INTERIOR_COMPS.md, researched): "a drive-up lane
with a pneumatic tube (the canister to the teller and back) was common from the 1960s and dwindled only with the
ATM." The walker, 2026-10-27: "do the drive-up lane next".

WHAT IT IS. Against one side wall of a bank, from the back of its frontage's sidewalk to its rear face, a paved
block across which run, from the wall out:

    the served lane (`LANE`, 4.0 m) | the island (`ISLAND`, 1.2 m) | the passing lane (`LANE`)

entered and left by one `driveway` through the kerb (`site_streets.kerb_crossings`, kind ``driveway``: the kerb
dropped, nothing a crossing gets), as a parking field's aisle is (`site_fields`). Over the served lane, off the wall,
Zoo's `drive_up_canopy` (1.138.0) in the bank's variant; on the island under it, Zoo's `drive_up_tube`, its
receptacle toward the served lane and its tube risen to the canopy's run (`TUBE_H`).

WHICH WAY IT RUNS. A US driver's window is on the left, so a car is served with the island on its LEFT. Along the
served lane the island lies one way, and whichever way of travel puts it on the driver's left is the way the lane
runs (`served_travel`); the passing lane runs the other. Which side of the building the block is on decides it, so
it is computed and recorded, never assumed.

WHY 4.0 M LANES. 12 ft is a drive-up lane's usual width, but the canopy reaches from the wall to the island's
centre, `LANE + ISLAND / 2`, and Zoo's genome starts at 4.76 m wide (its column line `FOOTING / 2 + SHY` inside its
+X): at 3.7 m the canopy would be 4.55 m and refused. 4.0 m is 13 ft.

WHERE. The bank is read from its door sign (`lot.bank_fronts`), its frontage road the nearest on-axis road with a
sidewalk. Its two ends along that road are tried, the end with more room first; a block takes one when it is
inside the plate by `site_fields.EDGE`, clear of every other building by `site_fields.SIDE_CLEAR` (it touches its
own), of every surface Lot draws (a door's landing on that wall refuses it, rightly), of what already stands, and
its driveway `site_fields.CORNER_CLEAR` from a junction. A bank with no end that fits gets none, and says so.

NOT YET. The island is the station's own curb and the canopy's footings, not a curb the lane's length; the lanes
carry no arrows; the canopy has no light anchor (Lux would light it). Each is the next step, not a refusal.

Frame: spec/Blender Z-up plan coordinates, metres. A piece's yaw is a counterclockwise plan rotation
(`site_parking.nose`): local -Y faces (sin yaw, -cos yaw), local -X faces (-cos yaw, -sin yaw). Pure.
"""
from __future__ import annotations

import math

#: A drive-up lane, metres: 13 ft (see WHY 4.0 M LANES).
LANE = 4.0
#: The island between the lanes, metres: a curb wide enough for the station's 0.9 m and the canopy's footings.
ISLAND = 1.2
BLOCK = 2 * LANE + ISLAND
#: The canopy over the served lane: its depth along the lane and its height (Zoo's genome default; 3.8 m under the
#: soffit, over a box truck's 3.5).
CANOPY_D = 6.0
CANOPY_H = 4.3
CANOPY_SPECIES = "drive_up_canopy"
STATION_SPECIES = "drive_up_tube"
STATION = (0.9, 0.8)
#: Zoo's canopy (1.138.0): its deck's depth and the run's drop under the soffit (`recipes/drive_up_canopy.py`'s
#: `DECK`, `TUBE_DROP`), and its column line inside its +X (`FOOTING[0] / 2 + SHY`). Copied because Lot does not
#: read Zoo; `tests/test_site_driveup.py` holds them to the recipe when Zoo is beside this repo.
CANOPY_DECK = 0.50
CANOPY_RUN_DROP = 0.18
CANOPY_COLUMN_IN = 0.253
#: A column's footing, its side, and its centre's inset from the canopy's end along the lane (the recipe's
#: `FOOTING[0]` and `column_y`)
CANOPY_FOOTING = 0.50
CANOPY_COLUMN_END_IN = 0.253
#: The station's height: its tube's top 6 cm into the run's centre line.
TUBE_H = round(CANOPY_H - CANOPY_DECK - CANOPY_RUN_DROP + 0.06, 3)
#: The canopy's width: the wall to the island's centre, plus the column line's inset.
CANOPY_W = round(LANE + ISLAND / 2.0 + CANOPY_COLUMN_IN, 3)
#: How far the canopy's -X face runs into the wall, so its end face sits inside the wall's solid
#: (`site_paths.DOOR_BURY`'s reason).
WALL_BURY = 0.05


def _left(ux, uy):
    return (-uy, ux)


def served_travel(away, toward_island):
    """+1 when a car on the served lane travels ``away`` (from the road) with the island on its left, else -1."""
    lx, ly = _left(*away)
    return 1 if lx * toward_island[0] + ly * toward_island[1] > 0 else -1


def _piece(name, species, at, dims, yaw, breaks, variant=0):
    import site_cover
    sx, sy = site_cover.footprint(dims[0], dims[1], yaw)
    rec = {"name": name, "species": species, "at": [round(at[0], 3), round(at[1], 3)], "yaw": round(yaw % 360.0, 3),
           "dims": [round(v, 3) for v in dims], "size": [round(sx, 3), dims[2], round(sy, 3)], "base": "plate",
           "source": "site_driveup", "breaks": breaks}
    if variant:
        rec["variant"] = int(variant)
    return rec


#: The shortest lane worth drawing, metres: the canopy's depth and room to pull in under it.
MIN_DEPTH = CANOPY_D + 2.0
#: The step a lane is shortened by when its far end meets something.
DEPTH_STEP = 0.5


def _depths(o_lo, o_hi, sgn):
    """The block's (o_lo, o_hi) from the full depth down to `MIN_DEPTH` in `DEPTH_STEP`s, the near end (the
    sidewalk's back) fixed: a lane runs from the street to the first thing on its wall -- a door's landing on the
    bank level's both side walls -- and stops short of it."""
    full = o_hi - o_lo
    out, d = [], full
    while d >= MIN_DEPTH - 1e-9:
        out.append((o_lo, o_lo + d) if sgn > 0 else (o_hi - d, o_hi))
        d -= DEPTH_STEP
    return out


def _frontage(roads_list, point):
    import site_fields
    best = None
    for road in roads_list:
        if not road.sidewalk or not site_fields._on_axis(road.angle_deg):
            continue
        t = max(0.0, min(road.length, (point[0] - road.a[0]) * road.along[0] + (point[1] - road.a[1]) * road.along[1]))
        px, py = road.point(t)
        d = math.hypot(point[0] - px, point[1] - py)
        if best is None or d < best[0]:
            best = (d, road)
    return None if best is None else best[1]


def plan_driveups(banks, roads_list, slabs, rects, standing=(), ground=None, markers=(), variants=None,
                  findings=None):
    """The drive-ups, one a bank at most: ``banks`` is `lot.bank_fronts`' ``[(id, (x, y) of its door sign,
    business)]``, ``slabs`` `site_surfaces.tops`, ``rects`` {building id: plan rect}, ``variants`` {building id:
    the bank's variant}. Returns ``(records, pieces)``: each record the block's rect, its driveway, its lanes and
    which way the served one runs; the pieces the canopy and the station, as cover records."""
    import site_cover
    import site_fields
    import site_parking
    polys = [site_fields._slab_poly(s) for s in slabs if s["family"] != "ground"]
    out, pieces, taken = [], [], []
    for bid, sign, _business in banks:
        r = rects.get(bid)
        road = _frontage(roads_list, sign)
        if r is None or road is None:
            _say(findings, f"LOT_DRIVEUP_NO_FRONTAGE: no on-axis road with a sidewalk for {bid}")
            continue
        t0, t1, o0, o1 = site_fields._project(road, r)
        side = (sign[0] - road.a[0]) * road.perp[0] + (sign[1] - road.a[1]) * road.perp[1]
        sgn = 1 if side >= 0 else -1
        back = road.width / 2.0 + road.sidewalk
        far = o1 if sgn > 0 else -o0
        if far <= back + 1e-9:
            _say(findings, f"LOT_DRIVEUP_NO_ROOM: {bid} does not reach behind its sidewalk")
            continue
        o_lo, o_hi = (back, far) if sgn > 0 else (-far, -back)
        if o_hi - o_lo < MIN_DEPTH:
            _say(findings, f"LOT_DRIVEUP_NO_ROOM: {bid}'s side is {o_hi - o_lo:.1f} m deep, under a lane's "
                           f"{MIN_DEPTH:.1f} m")
            continue
        junctions = []
        for c in road.crossings:
            if c.kind == "road":
                half = c.width / 2.0 + c.sidewalk
                junctions.append((c.t - half, c.t + half))
        # the two ends, the TIGHTER first: a 9.2 m block fits where a 20.3 m parking field cannot, and the end
        # with more room is the one a field can use (on the bank level, field_0 east of the bank)
        ends = [(t0 - BLOCK, t0, -1), (t1, t1 + BLOCK, 1)]
        if ground is not None:
            def room(e):
                pts = [road.point(t, 0.0) for t in (e[0], e[1])]
                return min(min(p[0] - ground[0], ground[2] - p[0]) if abs(road.along[0]) > 0.5
                           else min(p[1] - ground[1], ground[3] - p[1]) for p in pts)
            ends.sort(key=room)
        placed, why = None, []
        for a, b, end, o_lo, o_hi in [(a, b, e, lo2, hi2) for a, b, e in ends for lo2, hi2 in _depths(o_lo, o_hi, sgn)]:
            rect = site_fields._box(road, a, b, o_lo, o_hi)
            name = ("the -t end" if end < 0 else "the +t end") + f" at {abs(o_hi - o_lo):.1f} m deep"
            if ground is not None and not (ground[0] + site_fields.EDGE <= rect[0] and rect[2] <= ground[2] - site_fields.EDGE
                                           and ground[1] + site_fields.EDGE <= rect[1]
                                           and rect[3] <= ground[3] - site_fields.EDGE):
                why.append(f"{name} leaves the plate {tuple(round(v, 2) for v in rect)}")
                continue
            hit = [k for k, v in rects.items() if k != bid and site_fields._overlap(rect, site_fields._grow(v, site_fields.SIDE_CLEAR))]
            if hit:
                why.append(f"{name} is within {site_fields.SIDE_CLEAR} m of {', '.join(hit)}")
                continue
            if site_fields._hits_slab(rect, polys):
                hits = [s["name"] for s, poly in zip([s for s in slabs if s["family"] != "ground"], polys)
                        if site_fields._hits_slab(rect, [poly])]
                why.append(f"{name} crosses drawn surface(s) {', '.join(hits[:4])}")
                continue
            stand = [s for s in list(standing) + taken if site_fields._overlap(rect, s)]
            if stand:
                why.append(f"{name} overlaps {len(stand)} standing piece(s), the first {tuple(round(v, 2) for v in stand[0])}")
                continue
            if any(not (b <= j0 - site_fields.CORNER_CLEAR or a >= j1 + site_fields.CORNER_CLEAR) for j0, j1 in junctions):
                why.append(f"{name}'s driveway is within {site_fields.CORNER_CLEAR} m of a junction")
                continue
            placed = (a, b, end, rect, o_lo, o_hi)
            break
        if placed is None:
            _say(findings, f"LOT_DRIVEUP_NO_ROOM: neither end of {bid} along road {road.index} holds a "
                           f"{BLOCK:.1f} m drive-up: " + "; ".join(why))
            continue
        a, b, end, rect, o_lo, o_hi = placed
        # across the block from the wall: the served lane, the island, the passing lane; `end` -1 puts the wall at b
        wall_t = b if end < 0 else a
        out_t = -1 if end < 0 else 1     # the direction along the road from the wall out across the block
        island_t = wall_t + out_t * (LANE + ISLAND / 2.0)
        served_t = wall_t + out_t * LANE / 2.0
        passing_t = wall_t + out_t * (LANE + ISLAND + LANE / 2.0)
        away = (road.perp[0] * sgn, road.perp[1] * sgn)
        toward_island = (road.along[0] * out_t, road.along[1] * out_t)
        travel = served_travel(away, toward_island)
        o_mid = (o_lo + o_hi) / 2.0
        # the canopy: centred along the served lane's length, its -X at the wall, buried in it
        cw = CANOPY_W + WALL_BURY
        c_t = wall_t + out_t * (cw / 2.0 - WALL_BURY)
        cx, cy = road.point(c_t, o_mid)
        wall_dir = (-toward_island[0], -toward_island[1])
        canopy_yaw = math.degrees(math.atan2(-wall_dir[1], -wall_dir[0]))
        sx, sy = road.point(island_t, o_mid)
        station_yaw = site_parking.yaw_facing(*wall_dir)
        variant = int((variants or {}).get(bid) or 0)
        # THE CANOPY'S RECORD IS A COLUMN (a pole's rule, `site_poles.module_at`, 0.118.0): Lot draws a cover record's
        # greybox box and reads its sightline break from `at` and `size`, and a 4.9 x 6 m box 4.3 m tall would stand
        # a block across the served lane that the canopy -- two columns and a roof -- is not. So `at` is the column
        # on the road side, footing-sized and the canopy's height, and `module_at` the canopy's centre, where its
        # slot stands; the far column and the deck are the module's alone, with the module's own collision.
        col_o = o_mid - sgn * (CANOPY_D / 2.0 - CANOPY_COLUMN_END_IN)
        colx, coly = road.point(island_t, col_o)
        canopy = _piece(f"DriveUpCanopy_{bid}", CANOPY_SPECIES, (colx, coly), (cw, CANOPY_D, CANOPY_H), canopy_yaw,
                        f"drive-up {bid}", variant)
        canopy["size"] = [CANOPY_FOOTING, CANOPY_H, CANOPY_FOOTING]
        canopy["module_at"] = [round(cx, 3), round(cy, 3)]
        station = _piece(f"DriveUpStation_{bid}", STATION_SPECIES, (sx, sy), (STATION[0], STATION[1], TUBE_H),
                         station_yaw, f"drive-up {bid}")
        clear = [site_cover._grow(site_fields._box(road, island_t - ISLAND / 2.0, island_t + ISLAND / 2.0,
                                                   o_mid - CANOPY_D / 2.0, o_mid + CANOPY_D / 2.0),
                                  site_cover.MARKER_CLEARANCE)]
        if any(site_cover._inside(m, c) for m in markers for c in clear):
            _say(findings, f"LOT_DRIVEUP_ON_A_MARKER: {bid}'s island stands within "
                           f"{site_cover.MARKER_CLEARANCE} m of a mission marker")
            continue
        taken.append(rect)
        da = road.point((a + b) / 2.0, sgn * road.width / 2.0)
        db = road.point((a + b) / 2.0, sgn * back)
        out.append({"name": f"driveup_{bid}", "building": bid, "road": road.index, "side": "L" if sgn > 0 else "R",
                    "t": [round(a, 3), round(b, 3)], "rect": [round(v, 3) for v in rect],
                    "at": [round((rect[0] + rect[2]) / 2.0, 3), round((rect[1] + rect[3]) / 2.0, 3)],
                    "size": [round(BLOCK, 3), round(o_hi - o_lo, 3)], "yaw_deg": round(road.angle_deg, 4),
                    "lanes": {"served": round(served_t, 3), "island": round(island_t, 3), "passing": round(passing_t, 3)},
                    "served_travel": "away" if travel > 0 else "toward",
                    "driveway": {"a": [round(da[0], 3), round(da[1], 3)], "b": [round(db[0], 3), round(db[1], 3)],
                                 "width": BLOCK},
                    "source": "site_driveup"})
        pieces += [canopy, station]
    return out, pieces


def _say(findings, msg):
    if findings is not None:
        findings.append(msg)
    print(f"[lot] {msg}")
