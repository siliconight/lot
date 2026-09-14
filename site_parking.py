"""Parking bays along the kerb, and the cars parked in them.

Roadmap 153, the third layer: the cars themselves, in order. A parking lane
runs along each kerb of a road that has sidewalks, divided into bays; a
seeded share of the bays holds a `simple_car`, parked along the road. Each
car is the same prop-slot record the cover planner writes -- a collision
piece the site kit builds and the themed site stands -- which is the point:
a parked car IS cover, and the street's own furniture breaks sightlines
before a truck has to be stood in the road for it.

Rules, each derived or cited:
  * bay length 6.0 m, lane depth 2.2 m -- the low end of parallel-parking
    practice (20-22 ft bays, 7-8 ft lanes), so a 10 m road keeps two 2.8 m
    driving lanes;
  * no bay within `CROSSING_SETBACK` of a crossing on either side (the 20 ft
    no-parking rule at a crosswalk), and none over a kerb cut;
  * a car stands clear of every mission marker by `site_cover.MARKER_CLEARANCE`
    from its edge, and clear of every piece the cover planner already placed
    -- the same two rules cover keeps, applied by the same functions;
  * occupancy is a deterministic hash of (road, side, bay), `OCCUPANCY` of
    them, so the same spec parks the same cars every run;
  * a parked car faces the way the lane beside it travels: traffic keeps
    right (`site_streets.KEEP_RIGHT`), so the kerb on a driver's right is
    `site_streets.right_side(travel)` and a car at that kerb points along
    ``travel``;
  * which car, and in which of `STYLES` builds, is a SHA-1 of the bay and
    its road (`car_for_bay`), so a street parks a mix and the mix is the
    same in every process.

Frame: spec/Blender Z-up plan coordinates, like `site_streets`. Pure.
"""
from __future__ import annotations

import hashlib
import math

import site_cover
import site_streets
from site_streets import BAY_LENGTH, LANE_DEPTH, CROSSING_SETBACK, bays  # noqa: F401

OCCUPANCY = 0.6
CAR = ("simple_car", 1.75, 4.3, 1.45)          # the Zoo genome's defaults

#: THE CARS A KERB HOLDS: (name, width, length, height, weight), metres.
#: Until 0.70.0 every bay parked `CAR`, every slot said style 1, and a
#: street of 42 cars (cold run 9050's bank block) was 42 copies of one
#: module. Zoo builds one module per (dims, style) and seeds everything it
#: varies -- body style under `auto`, proportions, wheels, paint -- from that
#: module's stem (Zoo 0.79.0, `build.py`: `root_key(stem, ...)`), so a
#: different car needs a different stem, and the stem is made of dims and
#: style and nothing else Lot writes.
#:
#: Each row is chosen against four limits, the first two tested here:
#:   * the bay: length under `BAY_LENGTH` (6.0) and width under `LANE_DEPTH`
#:     (2.2), so the footprint stays inside the painted bay;
#:   * `site_cover.MIN_COVER_HEIGHT` (1.3): a parked car is cover;
#:   * the `simple_car` genome's ranges (Zoo 0.79.0: width 1.55-2.0, depth
#:     3.6-5.2, height 1.3-1.75), or the kit refuses the slot;
#:   * Zoo's body-style windows (`car_forms.FORMS[*]["natural"]`, read
#:     2026-09-13): 3.80 x 1.40 lies only in the hatchback's (depth
#:     3.6-4.35), 4.80 x 1.42 only in the sedan's (4.2-5.2, height to 1.56),
#:     4.70 x 1.73 only in the SUV's (height 1.58-1.76); the default 4.30 x
#:     1.45 lies in the sedan's and the hatchback's both and Zoo's seed picks.
#: The sizes are the ones Zoo 0.79.0's changelog proposed for this, near a
#: Geo Metro three-door, a Taurus-class sedan and a first Explorer; they are
#: not measurements of those cars. Weights put sedans first, as a 1990s
#: street did.
CARS = (
    ("hatchback", 1.60, 3.80, 1.40, 2),
    ("compact", 1.75, 4.30, 1.45, 3),        # `CAR`: sedan or hatchback, by seed
    ("sedan", 1.75, 4.80, 1.42, 3),
    ("suv", 1.80, 4.70, 1.73, 2),
)

#: Builds per shape. The style number is the only field besides dims in the
#: stem, so it is the one lever that buys a second paint and trim for one
#: shape. `len(CARS) * STYLES` bounds the parked-car modules a site can ask
#: the kit for: 8. Each is a Blender kit build and about 3,000 tris of
#: unique mesh (Zoo 0.79.0 measured 2,884-3,328 per style), so the bound is
#: kept to what a 20-40 car street needs to stop reading as copies -- on
#: cold run 9050's 42 cars, each module about five times -- and not more.
STYLES = 2


def _hash(*parts) -> float:
    """A stable number in [0, 1) from small integers, no RNG state."""
    h = 2166136261
    for p in parts:
        h = ((h ^ (int(p) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return (h % 10007) / 10007.0


def car_for_bay(road, side: str, index: int) -> tuple:
    """(row of `CARS`, style) for bay ``side``/``index`` of ``road``.

    A SHA-1 over a FORMATTED key -- road index, its end points to the
    centimetre, side, bay -- and not Python's `hash()`, which is salted per
    process for strings, and not `_hash`, whose value for the same bay
    already decided the bay is occupied: reusing it would draw the car only
    from the occupied share of its range. The end points are in the key so
    two sites whose first road has the same index do not park the same row
    of cars; they are formatted, not `repr`'d, so the key is not a float
    representation."""
    key = "parked|%d|%.2f,%.2f|%.2f,%.2f|%s|%d" % (
        road.index, road.a[0], road.a[1], road.b[0], road.b[1], side, index)
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    pick = int.from_bytes(digest[:4], "big")
    style = 1 + int.from_bytes(digest[4:8], "big") % STYLES
    total = sum(row[4] for row in CARS)
    r = pick % total
    for row in CARS:
        if r < row[4]:
            return row, style
        r -= row[4]
    return CARS[-1], style                     # unreachable: r < total


def nose(yaw: float) -> tuple:
    """The plan direction a `simple_car` at slot ``yaw`` points.

    Zoo builds the car nose at local -Y (0.79.0, `recipes/simple_car.py`; a
    built 1.80 x 4.70 x 1.73 module puts its windshield at glTF +Z and its
    tail lamps and plate at -Z, which is Blender -Y forward). A slot yaw is a
    counterclockwise plan rotation, the frame 0.69.4 measured in Godot 4.7
    for the stop sign's blade, which faces Blender -Y too: -Y turned by yaw
    is (sin yaw, -cos yaw)."""
    r = math.radians(yaw)
    return (math.sin(r), -math.cos(r))


def yaw_facing(dx: float, dy: float) -> float:
    """The slot yaw whose `nose` points along plan (dx, dy), in [0, 360)."""
    return round(math.degrees(math.atan2(dx, -dy)) % 360.0, 3) % 360.0


def lane_travel(side: str) -> int:
    """+1 when the lane beside kerb ``side`` travels +t, else -1: the kerb
    on the right of a driver travelling +t is `right_side(+1)`."""
    return 1 if side == site_streets.right_side(1) else -1


def plan_parking(roads_list, placed_rects, markers) -> list:
    """Cars in a share of the bays, as site-cover records (base: the plate).
    ``placed_rects`` are the rects already standing (cover pieces, buildings
    grown by their clearance); ``markers`` the mission points.

    A bay whose chosen car does not fit (it would overlap what stands, or
    come inside a marker's clearance) takes the largest smaller row that
    does, and the record says which was asked (``car_asked``). Every row
    smaller in both axes than `CAR` is inside `CAR`'s rect, so every bay
    0.69.4 filled is still filled."""
    out = []
    name = CAR[0]
    for road in roads_list:
        for bay in bays(road):
            if _hash(road.index, 1 if bay["side"] == "L" else 2, bay["index"]) >= OCCUPANCY:
                continue
            t = (bay["t0"] + bay["t1"]) / 2.0
            x, y = road.point(t, bay["offset"])
            travel = lane_travel(bay["side"])
            yaw = yaw_facing(travel * road.along[0], travel * road.along[1])
            asked, style = car_for_bay(road, bay["side"], bay["index"])
            # the asked row, then every row no larger in either axis,
            # longest first
            tries = [asked] + sorted(
                (row for row in CARS if row is not asked
                 and row[1] <= asked[1] and row[2] <= asked[2]),
                key=lambda row: (-row[2], -row[1]))
            for row in tries:
                _car, w, d, h, _wt = row
                sx, sy = site_cover.footprint(w, d, yaw)
                rect = (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)
                if any(site_cover._overlaps(rect, r) for r in placed_rects):
                    continue
                clear = site_cover._grow(rect, site_cover.MARKER_CLEARANCE)
                if any(site_cover._inside(m, clear) for m in markers):
                    continue
                break
            else:
                continue
            placed_rects = placed_rects + [rect]
            rec = {"at": [round(x, 3), round(y, 3)], "size": [sx, h, sy],
                   "source": "site_parking", "species": name,
                   "yaw": yaw, "dims": [w, d, h], "style": style,
                   "car": row[0],
                   "breaks": f"bay {bay['side']}{bay['index']} on road {road.index}"}
            if row is not asked:
                rec["car_asked"] = asked[0]
            out.append(rec)
    return out
