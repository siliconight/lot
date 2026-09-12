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
    them, so the same spec parks the same cars every run.

Frame: spec/Blender Z-up plan coordinates, like `site_streets`. Pure.
"""
from __future__ import annotations

import site_cover
import site_streets
from site_streets import BAY_LENGTH, LANE_DEPTH, CROSSING_SETBACK, bays  # noqa: F401

OCCUPANCY = 0.6
CAR = ("simple_car", 1.75, 4.3, 1.45)          # the Zoo genome's defaults


def _hash(*parts) -> float:
    """A stable number in [0, 1) from small integers, no RNG state."""
    h = 2166136261
    for p in parts:
        h = ((h ^ (int(p) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return (h % 10007) / 10007.0


def plan_parking(roads_list, placed_rects, markers) -> list:
    """Cars in a share of the bays, as site-cover records (base: the plate).
    ``placed_rects`` are the rects already standing (cover pieces, buildings
    grown by their clearance); ``markers`` the mission points."""
    out = []
    name, w, d, h = CAR
    for road in roads_list:
        for bay in bays(road):
            if _hash(road.index, 1 if bay["side"] == "L" else 2, bay["index"]) >= OCCUPANCY:
                continue
            t = (bay["t0"] + bay["t1"]) / 2.0
            x, y = road.point(t, bay["offset"])
            yaw = (road.angle_deg + 90.0) % 360.0      # length along the road
            sx, sy = site_cover.footprint(w, d, yaw)
            rect = (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)
            if any(site_cover._overlaps(rect, r) for r in placed_rects):
                continue
            clear = site_cover._grow(rect, site_cover.MARKER_CLEARANCE)
            if any(site_cover._inside(m, clear) for m in markers):
                continue
            placed_rects = placed_rects + [rect]
            out.append({"at": [round(x, 3), round(y, 3)], "size": [sx, h, sy],
                        "source": "site_parking", "species": name,
                        "yaw": round(yaw, 3), "dims": [w, d, h],
                        "breaks": f"bay {bay['side']}{bay['index']} on road {road.index}"})
    return out
