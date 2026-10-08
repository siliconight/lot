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
  (`site_streets.KEEP_RIGHT`), the vehicle's width to its mirrors and
  `LANE_MARGIN` either side. Where something stands in it, the lane steers
  toward and across the centre line to pass, as a driver does, tapered by
  `SHIFT_RATE`, and is back in its own half by the stop (0.100.0). It is
  `STATION_STEP` slices, written as the boxes they make. No cover may stand
  in it.
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

#: The responders' cruiser's slot: Zoo 1.86.0's `cruiser` genome defaults --
#: width to the mirror heads, length from the push bar to the rear bumper,
#: height to the light bar's top. Pinned, because Lot does not import Zoo;
#: `tests/test_site_responders.py` reads the genome when Zoo stands beside
#: this repo and fails when the two disagree.
#: 0.99.0 STATED 2.0 x 5.4 x 1.5 before Zoo had a cruiser, and called the
#: 2.0 m a width "to the mirrors": the published 1.99-2.0 m it cited is a
#: Crown Victoria's body, without them.
VEHICLE = ("cruiser", 2.196, 5.545, 1.578)
#: How far a mirror head stands outside the body (Zoo `car_forms.CRUISER`'s
#: `mirror_out`). A door opens from the body, so the stop's door room is
#: measured from it (`VEHICLE`'s width less two of these); the lane, which
#: the mirrors pass along, from the mirror heads.
MIRROR_OUT = 0.105
#: Room for a door to open, each side. A 1990s sedan's front door is about
#: 1.1 m long; opened to 60 degrees it stands 0.95 m out.
DOOR_ROOM = 1.0
#: Clear road either side of the vehicle in its lane, from entry to stop.
LANE_MARGIN = 0.5
#: THE LANE STEERS (0.100.0). A driver meeting a van parked out of its bay
#: moves over toward the centre line, and across it, rather than stopping.
#: 0.99.0's lane was a rigid box at the lane's centre. On cold run 9204 the
#: getaway van's mirrors stood 0.45 m into it and closed road 0's east end
#: (`docs/findings/responder_entry_no_stop/` at the factory root).
#: A shift is tapered, as a driver's is: MUTCD (2009) section 6C.08 puts a
#: shifting taper at L/2, with L = W * S^2 / 60 for speeds of 40 mph or
#: less (W the shift, S the speed in mph, L in W's units). A shift of W so
#: takes W * S^2 / 120 along the road: a rate of 120 / S^2 across per metre
#: along. `SHIFT_SPEED_MPH` is STATED, a residential street's posted speed.
SHIFT_SPEED_MPH = 25.0
SHIFT_RATE = 120.0 / SHIFT_SPEED_MPH ** 2
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


def _interval(rect, road, axis) -> tuple:
    """(lo, hi): plan ``rect``'s extent along ``axis`` (the road's `along`
    or `perp`), measured from `road.a` -- its four corners projected, exact."""
    vals = [(x - road.a[0]) * axis[0] + (y - road.a[1]) * axis[1]
            for x in (rect[0], rect[2]) for y in (rect[1], rect[3])]
    return min(vals), max(vals)


def shift_limit(road, off: float, width: float) -> float:
    """How far a lane of ``width`` centred at ``off`` may shift toward and
    across the centre line: until its far edge meets the oncoming driving
    half's outer edge. The parking lane beyond is the far kerb's, where cars
    stand."""
    parking = site_streets.LANE_DEPTH if site_streets.has_parking(road) else 0.0
    return abs(off) + (road.width / 2.0 - parking) - width / 2.0


def _needs(road, travel, off, width, slices, blocking, limit) -> list:
    """For each slice ``(t0, t1)``: the least shift toward the centre line at
    which a box ``width`` across, centred ``off`` less that shift, overlaps
    no rect in ``blocking`` -- or None where no shift up to ``limit`` does.

    Each rect beside the slice forbids an open interval of shifts, the ones
    at which the box's across extent overlaps the rect's; the least allowed
    shift is 0, or the top of the chain of intervals that holds it."""
    sign = 1.0 if off > 0 else -1.0
    near = [(_interval(r, road, road.along), _interval(r, road, road.perp)) for r in blocking]
    out = []
    for t0, t1 in slices:
        a0, a1 = min(t0, t1), max(t0, t1)
        banned = []
        for (b0, b1), (p0, p1) in near:
            if b1 <= a0 or b0 >= a1:
                continue
            if sign > 0:
                banned.append((off - p1 - width / 2.0, off - p0 + width / 2.0))
            else:
                banned.append((p0 - width / 2.0 - off, p1 + width / 2.0 - off))
        s = 0.0
        moved = True
        while moved:
            moved = False
            for lo, hi in banned:
                if lo < s < hi:
                    s = hi + 1e-6
                    moved = True
        out.append(s if s <= limit else None)
    return out


def steer(needs, rate: float, steps) -> list:
    """The shift each slice takes: at least what it needs, and at least what
    any other slice needs less the taper between them, so a shift ramps up
    before what it passes and back down after it, at ``rate`` across per
    metre along. ``steps`` is each slice's length. Then back to 0 at the
    lane's end, where the stop stands in its own half: None when a slice
    must stand further over than the taper from there allows."""
    s = list(needs)
    for i in range(1, len(s)):
        s[i] = max(s[i], s[i - 1] - rate * steps[i - 1])
    for i in range(len(s) - 2, -1, -1):
        s[i] = max(s[i], s[i + 1] - rate * steps[i])
    room = 0.0
    for i in range(len(s) - 1, -1, -1):
        if s[i] > room + 1e-9:
            return None
        room += rate * steps[i]
    return s


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
    body = w - 2.0 * MIRROR_OUT
    lane_w = w + 2.0 * LANE_MARGIN
    off = lane_offset(road, travel)
    sign = 1.0 if off > 0 else -1.0
    lo, hi = road.slab
    junctions = _junctions(road)
    blocking = list(standing) + list(taken_stops)
    limit = shift_limit(road, off, lane_w)
    # the lane's slices, entry outward, and what each needs -- once for every
    # stop this entry is tried at, each lane being the first of them
    end = hi if travel > 0 else lo
    count = int(math.ceil(abs(end - t_entry) / STATION_STEP - 1e-9))
    grid = [(t_entry + travel * k * STATION_STEP,
             t_entry + travel * min((k + 1) * STATION_STEP, abs(end - t_entry)))
            for k in range(count)]
    needs = _needs(road, travel, off, lane_w, grid, blocking, limit)
    best = None
    t = t_entry + travel * (ENTRY_RUN + d / 2.0)
    while lo + d / 2.0 - 1e-9 <= t <= hi - d / 2.0 + 1e-9:
        rear, front = t - d / 2.0, t + d / 2.0
        stop = _box(road, t, off, d, body + 2.0 * DOOR_ROOM)
        centre = road.point(t, off)
        ok = (not any(not (front <= j0 or rear >= j1) for j0, j1 in junctions)
              and all(math.dist(centre, a) >= site_audit.CAMP_RADIUS for a in anchors)
              and not any(_overlaps(stop, r)
                          for r in list(standing) + list(taken_stops) + list(taken_lanes)))
        lane = _lane(road, t_entry, travel, off, sign, lane_w, t - travel * d / 2.0,
                     grid, needs, blocking) if ok else None
        if lane is not None:
            dist, toward = _to_segment(centre, *way_back)
            key = (round(dist, 6), abs(t - t_entry))
            if best is None or key < best[0]:
                best = (key, t, centre, stop, lane, dist, toward)
        t += travel * STATION_STEP
    return best


def _lane(road, t_entry, travel, off, sign, lane_w, t_lane, grid, needs, blocking):
    """The lane from ``t_entry`` to ``t_lane`` (the stop's rear): ``(boxes,
    the largest shift)``, each box a run of slices at one shift -- or None
    when a slice can clear what stands in it at no shift the taper and the
    carriageway allow. Every box is read back against ``blocking``."""
    run = abs(t_lane - t_entry)
    slices, need = [], []
    for (t0, t1), n in zip(grid, needs):
        if abs(t0 - t_entry) >= run - 1e-9:
            break
        if n is None:
            return None
        t1 = t_entry + travel * min(abs(t1 - t_entry), run)
        slices.append((t0, t1))
        need.append(n)
    if not slices:
        return None
    shifts = steer(need, SHIFT_RATE, [abs(t1 - t0) for t0, t1 in slices])
    if shifts is None:
        return None
    boxes = []
    i = 0
    while i < len(slices):
        j = i
        while j + 1 < len(slices) and abs(shifts[j + 1] - shifts[i]) < 1e-9:
            j += 1
        a, b = slices[i][0], slices[j][1]
        boxes.append(_box(road, (a + b) / 2.0, off - sign * shifts[i], abs(b - a), lane_w))
        i = j + 1
    if any(_overlaps(box, r) for box in boxes for r in blocking):
        return None
    return boxes, max(shifts)


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
        _key, t, centre, stop, (lane, shift), dist, toward = best
        stops.append(stop)
        lanes.extend(lane)
        found.append({
            "road": road.index, "travel": travel,
            "entry": [round(entry[0], 3), round(entry[1], 3)],
            "stop": [round(centre[0], 3), round(centre[1], 3)],
            "yaw": site_parking.yaw_facing(travel * road.along[0], travel * road.along[1]),
            "vehicle": [w, d, h],
            "stop_box": [round(v, 3) for v in stop],
            "lane_boxes": [[round(v, 3) for v in box] for box in lane],
            "lane_shift": round(shift, 3),
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
    return ([tuple(a["stop_box"]) for a in arrivals]
            + [tuple(box) for a in arrivals for box in a["lane_boxes"]])


def blocked(arrivals, cover) -> list:
    """Findings for every cover piece standing in an arrival's stop or lane,
    read after every planner has run. Empty when the reservation held."""
    out = []
    pieces = site_spawns.cover_rects({"cover": cover}, margin=0.0)
    named = [cv for cv in cover if isinstance(cv, dict) and cv.get("at") and len(cv["at"]) >= 2]
    for i, a in enumerate(arrivals):
        parts = [("stop", a["stop_box"])] + [("lane", box) for box in a["lane_boxes"]]
        for cv, rect in zip(named, pieces):
            for part in ("stop", "lane"):
                if any(_overlaps(rect, tuple(box)) for name, box in parts if name == part):
                    what = cv.get("species") or cv.get("source") or cv.get("name") or "a piece"
                    out.append({
                        "code": "LOT_RESPONDER_BLOCKED", "severity": "major", "category": "spawn",
                        "message": (f"{what} at ({cv['at'][0]:.1f}, {cv['at'][1]:.1f}) stands in "
                                    f"responder arrival {i}'s {part} on road "
                                    f"{a['road']}: the lane and the stop were reserved before it "
                                    f"was planned, and a vehicle arriving there would meet it")})
    return out
