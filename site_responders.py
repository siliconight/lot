"""Where responders arrive, and the room they need to (roadmap 212).

The walker, 2026-10-08: "have responders show up after the job, on the way
back (and this would be on the gameplay layer, but we can make thee assets
and ensure there is clearance and routes for their arrival)".

WHAT THIS DOES NOT DO. It spawns nobody, times nothing and decides nothing
about how a wave plays: that is the gameplay layer's, which lives outside
the factory. What it does is make sure a level can receive responders, and
say where.

AN ARRIVAL has four parts, in plan coordinates (x, y north, metres):
- **The entry:** an open end of a road, one that does not end on another
  road. The plate is walled on four sides with no opening (`lot.py`'s
  `perimeter`), so a vehicle can only appear inside it, and a road's open
  end is where one can.
- **The lane:** the inbound driving lane from the entry to the stop -- the
  half of the carriageway a driver arriving from that end keeps to
  (`site_streets.KEEP_RIGHT`), the vehicle's width and `LANE_MARGIN` either
  side. No cover may stand in it.
- **The stop:** where a cruiser pulls up in that lane, with `DOOR_ROOM` to
  open its doors on both sides. Nothing may stand in it: not a parked car,
  not cover.
- **The route:** from the stop to the crew's way back. Lot cannot walk a
  navmesh, so the stop is written as a `responder_spawn` site marker, which
  Lot's nav QA already takes as a bot spawn and paths to the crew's points
  (`lot._navqa_anchors`). The route is checked where a route can be.

WHERE THE STOP GOES. Along the lane, where it comes nearest the crew's way
back -- the segment from the objective to the extraction, which with the
getaway van is the walk back to it. Three things are refused:
- a stop within `CAMP_RADIUS` of the crew's spawn or extraction -- the
  audit's own number (`site_audit.CAMP_RADIUS`), so the planner and the
  rule that judges it cannot drift apart;
- a stop that leaves the vehicle less than `ENTRY_RUN` of lane behind it,
  so it drives in rather than appearing at its stop;
- a stop in a junction.

HOW MANY. One arrival an entry, up to `MAX_ARRIVALS`. When there are more
entries, they are taken spread by bearing from the objective. The audit's
`S_RESPONDER_ARC` wants no gap between responders wider than 150 degrees,
which a site's roads may not allow; that finding is then about the roads.

Pure: dicts in, records and findings out. No Godot, no Blender.
"""
from __future__ import annotations

import math

import site_audit
import site_parking
import site_spawns
import site_streets

#: A 1990s police cruiser's slot: width to the mirrors, length bumper to
#: bumper, height. The Ford Crown Victoria Police Interceptor and the
#: Chevrolet Caprice 9C1 were 1.99-2.0 m wide and 5.39-5.44 m long. STATED,
#: not derived: Zoo has no cruiser species yet (roadmap 212).
VEHICLE = ("cruiser", 2.0, 5.4, 1.5)
#: Room for a door to open, each side. A 1990s sedan's front door is about
#: 1.1 m long; opened to 60 degrees it stands 0.95 m out.
DOOR_ROOM = 1.0
#: Clear road either side of the vehicle in its lane, from entry to stop.
LANE_MARGIN = 0.5
#: Lane a stop must leave behind the vehicle: twice its length, so it is
#: seen to drive in. Chosen, not derived.
ENTRY_RUN = 2.0 * VEHICLE[2]
#: The audit's `S_RESPONDER_ARC` wants three or more; more than three is a
#: wave plan, which is the gameplay layer's.
MAX_ARRIVALS = 3
#: Where along the lane stops are tried.
STATION_STEP = 1.0


def lane_offset(road, travel: int) -> float:
    """Across-offset of the inbound driving lane's centre for a driver
    travelling ``travel`` (+1: +t): the half of the carriageway it keeps to,
    less any parking lane, halved. A driver travelling +t keeps to the R half
    (negative offset) on a keep-right street."""
    parking = site_streets.LANE_DEPTH if site_streets.has_parking(road) else 0.0
    half = road.width / 2.0 - parking
    side = -1.0 if site_streets.KEEP_RIGHT else 1.0
    return side * travel * half / 2.0


def _box(road, t: float, offset: float, length: float, width: float) -> tuple:
    """Plan rect of a box ``length`` along ``road`` and ``width`` across,
    centred at station ``t`` and ``offset`` -- exact for a road on an axis,
    its bounding box otherwise."""
    cx, cy = road.point(t, offset)
    ux, uy = road.along
    px, py = road.perp
    hx = abs(ux) * length / 2.0 + abs(px) * width / 2.0
    hy = abs(uy) * length / 2.0 + abs(py) * width / 2.0
    return (cx - hx, cy - hy, cx + hx, cy + hy)


def _overlaps(one, other) -> bool:
    return not (one[2] <= other[0] or other[2] <= one[0]
                or one[3] <= other[1] or other[3] <= one[1])


def _to_segment(p, a, b) -> tuple:
    """(distance, nearest point) from ``p`` to segment ``a``-``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    s = 0.0 if n2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2))
    q = (a[0] + s * dx, a[1] + s * dy)
    return math.dist(p, q), q


def entries(roads_list) -> list:
    """Every open road end: ``(road, t, travel)``, where ``t`` is the end's
    station and ``travel`` the direction a vehicle arriving by it drives."""
    out = []
    for road in roads_list:
        for t, travel, end in ((0.0, 1, road.a), (road.length, -1, road.b)):
            if any(site_streets.end_lies_on(end, other)
                   for other in roads_list if other is not road):
                continue
            out.append((road, t, travel))
    return out


def _junctions(road) -> list:
    return [site_streets.crossing_box(c) for c in road.crossings if c.kind == "road"]


def _best_stop(road, t_entry, travel, way_back, anchors, standing,
               taken_stops=(), taken_lanes=()):
    """The stop for one entry, or None: the feasible station nearest the way
    back, nearer the entry on a tie.

    Another arrival is reserved ground too: this stop keeps out of its stop
    and its lane, and this lane out of its stop -- a cruiser standing with
    its doors open across the centre line is in the oncoming lane. Two lanes
    may share a road."""
    _name, w, d, _h = VEHICLE
    off = lane_offset(road, travel)
    lo, hi = road.slab
    junctions = _junctions(road)
    best = None
    t = t_entry + travel * (ENTRY_RUN + d / 2.0)
    while lo + d / 2.0 - 1e-9 <= t <= hi - d / 2.0 + 1e-9:
        rear, front = t - d / 2.0, t + d / 2.0
        stop = _box(road, t, off, d, w + 2.0 * DOOR_ROOM)
        centre = road.point(t, off)
        ok = (not any(not (front <= j0 or rear >= j1) for j0, j1 in junctions)
              and all(math.dist(centre, a) >= site_audit.CAMP_RADIUS for a in anchors)
              and not any(_overlaps(stop, r)
                          for r in list(standing) + list(taken_stops) + list(taken_lanes)))
        if ok:
            t_lane = t - travel * d / 2.0
            lane = _box(road, (t_entry + t_lane) / 2.0, off, abs(t_lane - t_entry),
                        w + 2.0 * LANE_MARGIN)
            if not any(_overlaps(lane, r) for r in list(standing) + list(taken_stops)):
                dist, toward = _to_segment(centre, *way_back)
                key = (round(dist, 6), abs(t - t_entry))
                if best is None or key < best[0]:
                    best = (key, t, centre, stop, lane, dist, toward)
        t += travel * STATION_STEP
    return best


def plan(site_spec, positions, findings=None) -> list:
    """The responders' arrivals for ``site_spec``: a list of records (see
    `marker`), possibly empty. ``positions`` is `lot._walk_positions`' dict,
    seated: ``spawn``, ``objective`` and ``extraction``. ``findings`` (a list)
    hears why an entry has no stop, or the site no arrival."""
    say = findings.append if findings is not None else (lambda _f: None)
    mode = site_spec.get("mode", "heist")
    if mode != "heist":
        return []
    roads_list = site_streets.roads(site_spec)
    ends = entries(roads_list)
    if not ends:
        say({"code": "LOT_RESPONDERS_NONE", "severity": "moderate", "category": "spawn",
             "message": ("no road on this site has an open end -- every end meets another "
                         "road or there are no roads -- so no vehicle can arrive: the plate "
                         "is walled on four sides, and responders have nowhere to come in "
                         "from (roadmap 212)")})
        return []
    spawn = tuple(positions["spawn"][:2])
    extraction = tuple(positions["extraction"][:2])
    objective = tuple(positions["objective"][:2])
    way_back = (objective, extraction)
    anchors = [spawn, extraction]
    standing = (site_spawns.solid_rects(site_spec, margin=0.0)
                + site_spawns.cover_rects(site_spec, margin=0.0))
    # Nearest the way back first, so where two arrivals want one stretch the
    # nearer one keeps it.
    order = []
    for road, t_entry, travel in ends:
        free = _best_stop(road, t_entry, travel, way_back, anchors, standing)
        order.append(((free[5] if free else math.inf), road.index, t_entry, road, travel))
    order.sort(key=lambda o: o[:3])
    _name, w, d, h = VEHICLE
    found, stops, lanes = [], [], []
    for _dist, _index, t_entry, road, travel in order:
        best = _best_stop(road, t_entry, travel, way_back, anchors, standing, stops, lanes)
        entry = road.point(t_entry, lane_offset(road, travel))
        if best is None:
            say({"code": "LOT_RESPONDER_ENTRY_NO_STOP", "severity": "minor", "category": "spawn",
                 "message": (f"road {road.index}'s open end at ({entry[0]:.1f}, {entry[1]:.1f}) "
                             f"has no stop a cruiser fits with its doors open: every station "
                             f"of its lane is within {site_audit.CAMP_RADIUS:g} m of the crew's "
                             f"spawn or extraction, in a junction, or blocked")})
            continue
        _key, t, centre, stop, lane, dist, toward = best
        stops.append(stop)
        lanes.append(lane)
        found.append({
            "road": road.index, "travel": travel,
            "entry": [round(entry[0], 3), round(entry[1], 3)],
            "stop": [round(centre[0], 3), round(centre[1], 3)],
            "yaw": site_parking.yaw_facing(travel * road.along[0], travel * road.along[1]),
            "vehicle": [w, d, h],
            "stop_box": [round(v, 3) for v in stop],
            "lane_box": [round(v, 3) for v in lane],
            "toward": [round(toward[0], 3), round(toward[1], 3)],
            "to_way_back": round(dist, 3),
            "run": round(abs(t - t_entry), 3),
        })
    return _spread(found, objective)


def _bearing(origin, p) -> float:
    return math.degrees(math.atan2(p[1] - origin[1], p[0] - origin[0])) % 360.0


def _arc(a, b) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _spread(found, objective) -> list:
    """At most `MAX_ARRIVALS`, the first kept and each next the one whose
    bearing from the objective stands furthest from those already kept."""
    if len(found) <= MAX_ARRIVALS:
        return found
    kept = [found[0]]
    rest = found[1:]
    while len(kept) < MAX_ARRIVALS:
        nxt = max(rest, key=lambda f: min(_arc(_bearing(objective, f["stop"]),
                                               _bearing(objective, k["stop"])) for k in kept))
        kept.append(nxt)
        rest.remove(nxt)
    return kept


def marker(arrival) -> dict:
    """The site marker an arrival is written as: a `responder_spawn` at its
    stop, which the audit judges and the nav QA spawns a bot at, carrying
    the rest for the gameplay layer."""
    return {"type": "responder_spawn", "at": list(arrival["stop"]),
            "source": "responder_arrival", "arrival": dict(arrival)}


def keep_out(arrivals) -> list:
    """The rects no later planner may stand anything in: every arrival's
    stop and lane."""
    return [tuple(a["stop_box"]) for a in arrivals] + [tuple(a["lane_box"]) for a in arrivals]


def blocked(arrivals, cover) -> list:
    """Findings for every cover piece standing in an arrival's stop or lane,
    read after every planner has run. Empty when the reservation held."""
    out = []
    pieces = site_spawns.cover_rects({"cover": cover}, margin=0.0)
    named = [cv for cv in cover if isinstance(cv, dict) and cv.get("at") and len(cv["at"]) >= 2]
    for i, a in enumerate(arrivals):
        for part in ("stop_box", "lane_box"):
            box = tuple(a[part])
            for cv, rect in zip(named, pieces):
                if _overlaps(rect, box):
                    what = cv.get("species") or cv.get("source") or cv.get("name") or "a piece"
                    out.append({
                        "code": "LOT_RESPONDER_BLOCKED", "severity": "major", "category": "spawn",
                        "message": (f"{what} at ({cv['at'][0]:.1f}, {cv['at'][1]:.1f}) stands in "
                                    f"responder arrival {i}'s {part.split('_')[0]} on road "
                                    f"{a['road']}: the lane and the stop were reserved before it "
                                    f"was planned, and a vehicle arriving there would meet it")})
    return out
