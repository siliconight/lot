"""The getaway van at the kerb, where the crew starts and ends (roadmap 206).

The walker, 2026-10-07: "the default is they have to leave the building and
return to the 'getaway' car or vehicle to leave the scene"; the vehicle "a Box
Truck. Like a Chevrolet P30 ... Matte Black" (Zoo's `step_van`); and "location
of the getaway vehicle should be the same as the missions spawn point. you
spawn, do the job, then return to the car". 2026-10-08: "go ahead, place it at
the spawn".

WHERE IT STANDS. In the parking lane, against the kerb nearest the spawn
building's street door: of the pairs of adjacent bays (`site_streets.bays`) on
a kerb that door faces, the pair that puts the van's own door nearest it. A
van is longer than one 6.0 m bay, so it takes two. It faces the way its lane
travels, as `site_parking`'s cars do, which puts its kerb side -- Zoo's -X,
the side with the crew's door -- against the kerb; its body stands `KERB_GAP`
off the kerb line, so the slot, which runs out to the mirror heads, stops
just short of it.

WHERE THE CREW STANDS. On the sidewalk outside the van's kerb-side door,
`SPAWN_OFF_KERB` in from the kerb line: ONE point that is both the site's
`crew_spawn` marker and its `extraction` marker (carrying ``getaway``, which
`site_audit` reads). `lot._walk_positions` takes a site-level marker over a
building's own, so the crew leaves from it and the job ends at it.

WHAT IT REFUSES, and says so in ``findings``: a site that is not a heist, has
no spawn building, already declares where its crew starts or leaves (a
designer's site-level marker is the designer's), or has no pair of free bays
within `MAX_REACH` of the spawn building. Without a van the spawn and the
extraction are what they always were.

NO ENEMY STANDS IN IT, by arithmetic rather than a rule: every point of the van
lies within `site_spawns.MIN_STANDOFF` (8.0) of its door's spawn -- 6.35 m at
the far corner -- and `place_enemies` keeps every enemy that far out.

Frame: spec/Blender Z-up plan coordinates, like `site_streets`. Pure.
"""
from __future__ import annotations

import math

import site_cover
import site_parking
import site_streets

#: The van's slot: Zoo `step_van`'s genome defaults -- width to the mirror
#: heads, depth bumper to bumper, height to the clearance lamps.
VAN = ("step_van", 2.6, 6.8, 3.05)
#: How far a mirror head stands outside the body (Zoo `van_forms.MIRROR_OUT`):
#: the body is the slot's width less two of these.
MIRROR_OUT = 0.15
#: The body's kerb side off the kerb line.
KERB_GAP = 0.20
#: The crew's spawn in from the kerb line, on the sidewalk: 1.25 m from the
#: van's slot, past `site_spawns.WALL_MARGIN` (1.0) should anything ever grow
#: the van by it, with a body's 0.35 m radius to spare.
SPAWN_OFF_KERB = 1.2
#: The crew door's middle, forward of the van's centre toward its nose.
#: Pinned from Zoo `van_forms.layout(2.6, 6.8, 3.05)` -- `y_door0` -2.02,
#: `y_door1` -1.28, the nose at -Y -- because Lot does not import Zoo.
DOOR_AHEAD = 1.65
#: The farthest the van's door may stand from the spawn building's door.
MAX_REACH = 30.0
#: A door faces a road when its outward normal and the way to the road agree
#: by at least this much.
FACING_DOT = 0.5


def _doors(site_spec, merged, bid):
    """The spawn building's ground doors, as (point, outward normal); [] when
    its openings are unknown."""
    if merged is None:
        return []
    import site_paths
    return [(e[0], e[1]) for e in site_paths.doors(site_spec, merged).get(bid, [])]


def _standing(site_spec):
    """The rects already standing when the van is planned: cover records, in
    the `size` convention every planner writes ([plan x, height, plan y]),
    and the buildings' footprints."""
    import site_spawns
    out = []
    for cv in site_spec.get("cover") or []:
        sx, _h, sy = cv.get("size", [1.0, 1.0, 1.0])
        out.append((cv["at"][0] - sx / 2.0, cv["at"][1] - sy / 2.0,
                    cv["at"][0] + sx / 2.0, cv["at"][1] + sy / 2.0))
    return out + site_spawns.footprints(site_spec, margin=0.0)


def _pairs(road, sign):
    """Adjacent bay pairs on the kerb ``sign`` of ``road``: (first, second)."""
    mine = sorted((b for b in site_streets.bays(road) if (b["offset"] > 0) == (sign > 0)),
                  key=lambda b: b["index"])
    return [(a, b) for a, b in zip(mine, mine[1:]) if b["index"] == a["index"] + 1]


def _candidate(road, sign, pair):
    """The van and its door's spawn for one bay pair: (record, spawn point)."""
    name, w, d, h = VAN
    first, second = pair
    t_c = (first["t0"] + second["t1"]) / 2.0
    side = first["side"]
    travel = site_parking.lane_travel(side)
    body_half = w / 2.0 - MIRROR_OUT
    x, y = road.point(t_c, sign * (road.width / 2.0 - KERB_GAP - body_half))
    yaw = site_parking.yaw_facing(travel * road.along[0], travel * road.along[1])
    sx, sy = site_cover.footprint(w, d, yaw)
    off = min(SPAWN_OFF_KERB, road.sidewalk / 2.0)
    spawn = road.point(t_c + travel * DOOR_AHEAD, sign * (road.width / 2.0 + off))
    record = {"at": [round(x, 3), round(y, 3)], "size": [sx, h, sy],
              "source": "getaway_van", "species": name, "yaw": yaw,
              "dims": [w, d, h], "style": 1,
              "breaks": f"bays {side}{first['index']}-{second['index']} on road {road.index}"}
    return record, (round(spawn[0], 3), round(spawn[1], 3))


def plan(site_spec, merged=None, findings=None):
    """The getaway van and its markers for ``site_spec``, or None.

    Returns ``{"van": cover record, "markers": [crew_spawn, extraction],
    "door": the spawn building's door it serves, "reach": metres from that
    door to the crew's spawn}``. ``merged`` is `lot.merge_gameplay`'s, for the
    spawn building's doors; without it the van serves the building's centre.
    ``findings`` (a list of strings) hears why there is no van."""
    say = findings.append if findings is not None else (lambda _m: None)
    mode = site_spec.get("mode", "heist")
    if mode != "heist":
        say(f"LOT_GETAWAY_NONE: mode {mode!r} is not a heist; no getaway van")
        return None
    bid = site_spec.get("spawn")
    building = next((b for b in site_spec.get("buildings") or [] if b.get("id") == bid), None)
    if building is None or not building.get("at"):
        say(f"LOT_GETAWAY_NONE: the spawn building {bid!r} is not placed on this site; no getaway van")
        return None
    declared = sorted({m.get("type") for m in site_spec.get("site_markers") or []
                       if m.get("type") in ("crew_spawn", "attacker_spawn", "extraction")})
    if declared:
        say(f"LOT_GETAWAY_NONE: the site already declares {', '.join(declared)} marker(s); "
            f"a designer's start and exit stand, no getaway van")
        return None
    doors = _doors(site_spec, merged, bid) or [(tuple(building["at"][:2]), None)]
    standing = _standing(site_spec)
    best = None
    for road in site_streets.roads(site_spec):
        if not site_streets.has_parking(road):
            continue
        for door, normal in doors:
            off = ((door[0] - road.a[0]) * road.perp[0] + (door[1] - road.a[1]) * road.perp[1])
            sign = 1 if off > 0 else -1
            if normal is not None and (-sign * (normal[0] * road.perp[0] + normal[1] * road.perp[1])
                                       < FACING_DOT):
                continue                        # this door does not face this road
            for pair in _pairs(road, sign):
                record, spawn = _candidate(road, sign, pair)
                reach = math.dist(spawn, door)
                if reach > MAX_REACH or (best is not None and reach >= best[0]):
                    continue
                sx, _h, sy = record["size"]
                x, y = record["at"]
                rect = (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)
                if any(site_cover._overlaps(rect, r) for r in standing):
                    continue
                best = (reach, record, spawn, door)
    if best is None:
        say(f"LOT_GETAWAY_NONE: no pair of free bays within {MAX_REACH:.0f} m of a door of the "
            f"spawn building {bid!r} that faces a road; no getaway van")
        return None
    reach, record, spawn, door = best
    at = [spawn[0], spawn[1]]
    return {"van": record,
            "markers": [{"type": "crew_spawn", "at": list(at), "source": "getaway_van"},
                        {"type": "extraction", "at": list(at), "source": "getaway_van",
                         "getaway": VAN[0]}],
            "door": [round(door[0], 3), round(door[1], 3)], "reach": round(reach, 3)}
