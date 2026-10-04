"""
site_fields.py  --  a parking field in a gap between buildings
==============================================================
Step 4 of `docs/proposals/LAND_USE_DESIGN.md`, agreed by the walker
2026-10-03, its second use: open ground beside a building becomes the lot
its customers park in. The land-pressure guide's 5.4 -- every piece of open
land has a role a viewer can read -- and its suburban strip, "detached
businesses oriented toward road access, broad gaps often occupied by
parking or circulation". Before this, a gap between two storefronts was bare
plate, and the census counted it as remainder.

ONE MODULE, FROM PRACTICE. A two-way drive aisle runs in from the road,
square to it, and a row of 90-degree bays lines each side of the aisle:

    aisle 24 ft (`AISLE`, 7.3 m), bays 9 x 18 ft (`BAY_W` 2.7 x `BAY_L` 5.5)

so a field is `FIELD_W` (18.3 m) along the road and `BAY_W` per bay deep.
These are the commonly published figures for a two-way, 90-degree layout,
read as typical, not taken from one code. A parked car lies along the road,
nose in -- its nose away from the aisle.

WHERE. Along each road with a sidewalk, on each side that has buildings
fronting it (`site_landuse.FRONT_REACH`), the gaps between those buildings'
spans along the road, and from the road's drawn ends to the first and the
last, are the candidates. A gap takes a field, centred in it, when it holds
`FIELD_W` plus `SIDE_CLEAR` either side; the field's driveway stays
`CORNER_CLEAR` from any road crossing this one (a driveway near a junction
is the classic access-management fault), sliding along the gap away from
it when it can. Then it is as deep as it can be, from `MAX_BAYS` down to
`MIN_BAYS`, while it stays: clear of every building by `SIDE_CLEAR`, clear of
every surface Lot draws (roads, sidewalks, kerb cuts, frontages, walks,
landings, courtyards, pads), clear of what already stands, inside the plate
by `EDGE`, and no deeper than the farthest back face of the buildings either
side of it -- a field beside a building, not a lot running off behind the
block. A gap with no field that fits is passed over in silence: a gap is
not owed a field, and the census still counts what is left.

THE DRIVEWAY. The aisle crosses the sidewalk to the carriageway as a
`driveway` (`site_streets.kerb_crossings`, kind ``driveway``): the kerb is
dropped across the aisle's width, and nothing a crossing gets is given to
it -- no crosswalk (it never reaches the road's centre line), no stop bar,
no corner furniture -- because a driveway is not a crossing. The kerb lane's
bays already skip every cut, so no car is parked across it.

THE CARS. A seeded share of the bays (`site_parking.OCCUPANCY`, from a
SHA-1 of the bay, the way `site_parking.car_for_bay` keys a kerb bay) holds
one of `site_parking.CARS` -- every row fits a bay -- as the same cover
record a kerb car is: a collision piece, so the field's cars stand in the
cover planner's measurement. A car stays `site_cover.MARKER_CLEARANCE` from
every marker and `APPROACH_CLEAR` from every door's approach point; a bay
that fails is left empty.

AND NOT AT AN ENEMY'S ELBOW. A parked car is a parapet, and whose depends
on where it stands: `site_cover` biases every piece to the crew's end of a
line because one at the other end "hands the enemy the wall to hold". The
first build of this module ignored that, and on gas_block_001 seed 9181 four
field cars stood 4-10 m from `Enemy_0`, every marker unmoved: the crew's
survival fell from 70.6 s to 5.5 s, the enemies fired first (1.9 s against
the crew's 4.0 s), and Laser Tag added INSTANT_CONTACT, OVEREXPOSED and
NO_REACTION_TIME. So a car's edge keeps `ENEMY_CLEAR` from every enemy
spawn: the ground an enemy covers before Laser Tag calls the contact
instant.

Frame: spec/Blender Z-up plan coordinates, metres. Pure.
"""
from __future__ import annotations

import hashlib
import math

#: Two-way drive aisle, metres (24 ft).
AISLE = 7.3
#: A 90-degree bay, metres (9 x 18 ft).
BAY_W = 2.7
BAY_L = 5.5
#: The field along the road: a bay row, the aisle, a bay row.
FIELD_W = 2 * BAY_L + AISLE
#: Bays per side of the aisle. Two is the least that reads as a lot rather
#: than a driveway; six (16.2 m) is as deep as the buildings it sits between
#: usually run on the lots on disk (`patches/lot_fields/gap_survey.py`).
MIN_BAYS = 2
MAX_BAYS = 6
#: From a building's wall to the field's side, metres: a body's width (0.7,
#: `agent_contract.json`) with room to pass. Chosen, not derived.
SIDE_CLEAR = 1.0
#: From the near edge of a road crossing this one (its band) to the
#: driveway's near edge, metres: 50 ft, the commonly cited least corner
#: clearance for a driveway on a collector.
CORNER_CLEAR = 15.0
#: In from the plate's edge.
EDGE = 0.5
#: A car's footprint from a door's approach point (`site_enterability`):
#: the dumpster's own clearance (`site_dumpsters.APPROACH_CLEAR`).
APPROACH_CLEAR = 1.5
#: A car's edge from an enemy spawn, metres: Laser Tag's enemy walks 4.0 m/s
#: (`LT_EnemyMovement.move_speed`) and the scenario calls a first enemy shot
#: inside 3.0 s instant (`LT_TestScenario.first_contact_min_seconds`), so
#: 12 m is all the ground an enemy can reach before that verdict. Derived
#: from those two; when either moves, this does.
ENEMY_SPEED = 4.0
CONTACT_MIN_S = 3.0
ENEMY_CLEAR = ENEMY_SPEED * CONTACT_MIN_S
#: The bay lines: the road's own line width and paint.
STRIPE = 0.12
WHITE = (0.90, 0.90, 0.88)
#: Two rectangles that only share an edge do not overlap.
TOUCH = 1e-6


def _on_axis(deg):
    return abs((deg % 90.0)) < 0.01 or abs((deg % 90.0) - 90.0) < 0.01


def _box(road, t0, t1, o0, o1):
    """Plan AABB of the road-frame box [t0, t1] along x [o0, o1] across, on
    an axis-aligned road."""
    pts = [road.point(t, o) for t in (t0, t1) for o in (o0, o1)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _overlap(a, b):
    return not (a[2] <= b[0] + TOUCH or b[2] <= a[0] + TOUCH
                or a[3] <= b[1] + TOUCH or b[3] <= a[1] + TOUCH)


def _grow(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def _slab_poly(s):
    import site_yards
    return site_yards._corners(s["centre"][0], s["centre"][1], s["size"][0], s["size"][1], s["yaw_deg"])


def _hits_slab(rect, polys):
    import site_yards
    box = site_yards._box_corners(rect)
    return any(site_yards._overlap(box, p) for p in polys)


def _project(road, rect):
    """(t0, t1, o0, o1) of a plan rect in ``road``'s frame."""
    ts, os_ = [], []
    for x, y in ((rect[0], rect[1]), (rect[2], rect[1]), (rect[0], rect[3]), (rect[2], rect[3])):
        dx, dy = x - road.a[0], y - road.a[1]
        ts.append(dx * road.along[0] + dy * road.along[1])
        os_.append(dx * road.perp[0] + dy * road.perp[1])
    return min(ts), max(ts), min(os_), max(os_)


def _key(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).digest()


def plan_fields(site_spec, roads_list, slabs, rects, standing=(), ground=None):
    """The fields, as records: road, side, t (along), depth, bays, the plan
    rect, its centre and yaw, and the driveway (a, b, width). ``slabs`` are
    `site_surfaces.tops` (the plate is skipped), ``rects`` {building id:
    plan rect}, ``standing`` the plan rects of what already stands."""
    import site_landuse
    polys = [_slab_poly(s) for s in slabs if s["family"] != "ground"]
    out, taken = [], []
    for road in roads_list:
        if not road.sidewalk or not _on_axis(road.angle_deg):
            continue
        back = road.width / 2.0 + road.sidewalk
        junctions = []
        for c in road.crossings:
            if c.kind == "road":
                half = c.width / 2.0 + c.sidewalk
                junctions.append((c.t - half, c.t + half))
        lo, hi = max(road.slab[0], 0.0), min(road.slab[1], road.length)
        for sgn, side in ((1, "L"), (-1, "R")):
            fronting = []
            for bid, r in rects.items():
                t0, t1, o0, o1 = _project(road, r)
                near = o0 if sgn > 0 else -o1
                far = o1 if sgn > 0 else -o0
                if t1 < lo or t0 > hi:
                    continue
                setback = near - back
                if -0.5 <= setback <= site_landuse.FRONT_REACH:
                    fronting.append((t0, t1, far, bid))
            if not fronting:
                continue
            fronting.sort()
            gaps, prev, prev_far = [], lo, None
            for t0, t1, far, bid in fronting:
                gaps.append((prev, t0, prev_far, far))
                prev, prev_far = max(prev, t1), far
            gaps.append((prev, hi, prev_far, None))
            for g0, g1, far_a, far_b in gaps:
                room = g1 - g0 - 2 * SIDE_CLEAR
                if room < FIELD_W - 1e-9:
                    continue
                fars = [f for f in (far_a, far_b) if f is not None]
                limit = max(fars) - back if fars else MAX_BAYS * BAY_W
                # stations: centred, then slid toward each end in 0.5 m
                # steps, nearest the centre first
                mid = (g0 + g1) / 2.0
                free = (room - FIELD_W) / 2.0
                steps = [0.0]
                k = 1
                while k * 0.5 <= free + 1e-9:
                    steps += [k * 0.5, -k * 0.5]
                    k += 1
                placed = None
                for dt in steps:
                    tc = mid + dt
                    f0, f1 = tc - FIELD_W / 2.0, tc + FIELD_W / 2.0
                    d0, d1 = tc - AISLE / 2.0, tc + AISLE / 2.0
                    if any(not (d1 <= j0 - CORNER_CLEAR or d0 >= j1 + CORNER_CLEAR) for j0, j1 in junctions):
                        continue
                    for n in range(MAX_BAYS, MIN_BAYS - 1, -1):
                        depth = n * BAY_W
                        if depth > limit + 1e-9:
                            continue
                        o0, o1 = (back, back + depth) if sgn > 0 else (-back - depth, -back)
                        rect = _box(road, f0, f1, o0, o1)
                        if ground is not None and not (ground[0] + EDGE <= rect[0] and rect[2] <= ground[2] - EDGE
                                                       and ground[1] + EDGE <= rect[1] and rect[3] <= ground[3] - EDGE):
                            continue
                        if any(_overlap(rect, _grow(b, SIDE_CLEAR)) for b in rects.values()):
                            continue
                        if _hits_slab(rect, polys):
                            continue
                        if any(_overlap(rect, t) for t in list(standing) + taken):
                            continue
                        placed = (tc, n, depth, rect, o0, o1)
                        break
                    if placed:
                        break
                if placed is None:
                    continue
                tc, n, depth, rect, o0, o1 = placed
                taken.append(rect)
                a = road.point(tc, sgn * road.width / 2.0)
                b = road.point(tc, sgn * back)
                cx, cy = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
                out.append({"name": f"field_{len(out)}", "road": road.index, "side": side,
                            "t": [round(tc - FIELD_W / 2.0, 3), round(tc + FIELD_W / 2.0, 3)],
                            "bays": n, "depth": round(depth, 3),
                            "rect": [round(v, 3) for v in rect],
                            "at": [round(cx, 3), round(cy, 3)],
                            "size": [round(FIELD_W, 3), round(depth, 3)],
                            "yaw_deg": round(road.angle_deg, 4),
                            "driveway": {"a": [round(a[0], 3), round(a[1], 3)],
                                         "b": [round(b[0], 3), round(b[1], 3)],
                                         "width": AISLE},
                            "source": "site_fields"})
    return out


def bays_of(field, road):
    """Every bay of ``field``: (row, k, centre (x, y), the plan direction its
    car's nose points). Row ``-1`` lies before the aisle along the road,
    ``+1`` after it; ``k`` counts out from the back of walk."""
    sgn = 1 if field["side"] == "L" else -1
    back = road.width / 2.0 + road.sidewalk
    tc = (field["t"][0] + field["t"][1]) / 2.0
    out = []
    for row in (-1, 1):
        t = tc + row * (AISLE / 2.0 + BAY_L / 2.0)
        nose = (row * road.along[0], row * road.along[1])
        for k in range(int(field["bays"])):
            o = sgn * (back + (k + 0.5) * BAY_W)
            out.append((row, k, road.point(t, o), nose))
    return out


def plan_cars(fields, roads_list, markers=(), approaches=(), standing=(), enemies=()):
    """Cars in a share of the fields' bays, as cover records (base: the plate).
    ``enemies`` are the enemy spawns, kept `ENEMY_CLEAR` from a car's edge."""
    import site_cover
    import site_parking
    by_index = {r.index: r for r in roads_list}
    out, placed = [], list(standing)
    total = sum(row[4] for row in site_parking.CARS)
    for f in fields:
        road = by_index[f["road"]]
        for row, k, (x, y), nose in bays_of(f, road):
            key = ("field", f["road"], f["side"], "%.2f" % f["t"][0], row, k)
            d = _key(*key)
            if int.from_bytes(d[:4], "big") / 2.0 ** 32 >= site_parking.OCCUPANCY:
                continue
            pick = int.from_bytes(d[4:8], "big") % total
            for car in site_parking.CARS:
                if pick < car[4]:
                    break
                pick -= car[4]
            style = 1 + int.from_bytes(d[8:12], "big") % site_parking.STYLES
            name, w, l, h, _wt = car
            yaw = site_parking.yaw_facing(nose[0], nose[1])
            sx, sy = site_cover.footprint(w, l, yaw)
            rect = (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)
            if any(site_cover._overlaps(rect, r) for r in placed):
                continue
            clear = site_cover._grow(rect, site_cover.MARKER_CLEARANCE)
            if any(site_cover._inside(m, clear) for m in markers):
                continue
            near = site_cover._grow(rect, APPROACH_CLEAR)
            if any(site_cover._inside(ap, near) for ap in approaches):
                continue
            if any(math.hypot(max(rect[0] - ex, 0.0, ex - rect[2]), max(rect[1] - ey, 0.0, ey - rect[3]))
                   < ENEMY_CLEAR for ex, ey in enemies):
                continue
            placed.append(rect)
            out.append({"at": [round(x, 3), round(y, 3)], "size": [sx, h, sy],
                        "source": "site_fields", "species": site_parking.CAR[0],
                        "yaw": yaw, "dims": [w, l, h], "style": style, "car": name,
                        "field": f["name"],
                        "breaks": f"bay {'AB'[row > 0]}{k} of {f['name']}"})
    return out


def markings(fields, roads_list):
    """The bay lines, in `site_streets._marking`'s record: a line between
    each pair of bays and at each row's ends, `BAY_L` long, along the road."""
    import site_streets
    by_index = {r.index: r for r in roads_list}
    out = []
    for f in fields:
        road = by_index[f["road"]]
        sgn = 1 if f["side"] == "L" else -1
        back = road.width / 2.0 + road.sidewalk
        tc = (f["t"][0] + f["t"][1]) / 2.0
        for row in (-1, 1):
            t = tc + row * (AISLE / 2.0 + BAY_L / 2.0)
            for k in range(int(f["bays"]) + 1):
                o = sgn * (back + k * BAY_W)
                # the outermost line sits half a stripe inside the field
                o -= sgn * (STRIPE / 2.0) * (1 if k == int(f["bays"]) else (-1 if k == 0 else 0))
                out.append(site_streets._marking("bay_line", road, t, o, BAY_L, STRIPE, WHITE,
                                                 field=f["name"]))
    return out
