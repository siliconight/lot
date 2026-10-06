"""Spawns are kept out of the Empties and the ground behind their row (0.97.3).

Laser Tag refused four candidates in cold runs 9170 to 9186 on
UNREACHABLE_SPAWN: seed_9061 in 9170 and 9174, seed_9205 in 9179 and 9186.
In every one, Enemy_5 stood inside an Empty.
- `place_enemies` had pushed it off the route onto ground `outdoors()`
  called open, because `footprints` reads `buildings` and an Empty is a
  blocker.
- 9186's Enemy_5 was pushed 24.0 m into e9.

The fixture is that candidate's site as Lot drew it, with each building's
footprint as `merge_gameplay` annotates it. POSITIONS are the walk positions
its scene was written from (`LT_PlayerRoutePoints`, level frame: x, y north,
metres).

THE INSTRUMENTS HERE ARE THE TEST'S OWN. A blocker's rect and the row's front
line are read from the fixture directly, not through the functions this
release adds, so on 0.97.2 these fail on where the enemies stand rather than
on a missing name.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import site_spawns                    # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "restaurant_row_001_seed_9205.site.json")
POSITIONS = {"spawn": (-8.0, 13.5, 0.0), "objective": (62.75, 0.5, 3.2),
             "extraction": (-47.0, -15.47, 0.0)}
#: Where 9186's scene put Enemy_5 (`level.tscn`, Godot (x, z) -> level (x, -z)).
SHIPPED_ENEMY_5 = (-17.6963, -35.4587)


def _spec():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _blocker_rects(spec):
    """``{id: rect}``: a blocker's size_x/size_y are world extents."""
    out = {}
    for bk in spec["blockers"]:
        x, y = float(bk["at"][0]), float(bk["at"][1])
        sx = float(bk.get("size_x", 12.0) or 12.0) / 2.0
        sy = float(bk.get("size_y", 12.0) or 12.0) / 2.0
        out[bk["id"]] = (x - sx, y - sy, x + sx, y + sy)
    return out


def _inside(p, r):
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]


def _row_front(spec):
    """The fixture's one row of Empties faces +y, the road: its front line is
    the houses' common north edge."""
    rects = list(_blocker_rects(spec).values())
    fronts = {round(r[3], 3) for r in rects}
    assert len(fronts) == 1, fronts
    return fronts.pop()


def test_the_fixture_is_the_refused_site():
    """Before trusting a fix against it: the fixture holds the Empty that
    9186's Enemy_5 stood in, and the row it stands in."""
    spec = _spec()
    assert _inside(SHIPPED_ENEMY_5, _blocker_rects(spec)["e9"])
    assert len(spec["blockers"]) == 24
    assert abs(_row_front(spec) - (-33.65)) < 1e-6


def test_no_enemy_stands_inside_a_blocker():
    spec = _spec()
    plan = site_spawns.place_enemies(spec, POSITIONS)
    assert len(plan.positions) == 6, plan.dropped
    rects = _blocker_rects(spec)
    for i, p in enumerate(plan.positions):
        hits = [bid for bid, r in rects.items() if _inside(p, r)]
        assert not hits, ("Enemy_%d" % i, p, hits)


def test_no_enemy_stands_behind_the_rows_front_line():
    """Behind the front line is the ground the row's fences shut off from the
    street.

    This runs on the declared-footprint occluders `place_enemies` falls back
    to when no collision reading is passed. On them, keeping the Empties out
    alone pushed Enemy_4 on through its house into the strip behind the row,
    39.5 m off the route. Lot's own reading shows the same on 9174's
    seed_9061 (`docs/findings/enemy_inside_an_empty/` at the factory root)."""
    spec = _spec()
    front = _row_front(spec)
    plan = site_spawns.place_enemies(spec, POSITIONS)
    for i, p in enumerate(plan.positions):
        assert p[1] > front + site_spawns.WALL_MARGIN, ("Enemy_%d" % i, p, front)


def test_the_crew_keeps_out_of_a_blocker_too():
    """The crew's spawns ask `outdoors()` of the same rects. A spawn put
    inside e9 is moved out of it, past the wall margin."""
    spec = _spec()
    e9 = _blocker_rects(spec)["e9"]
    inside = {"spawn": (SHIPPED_ENEMY_5[0], SHIPPED_ENEMY_5[1], 0.0),
              "objective": POSITIONS["objective"], "extraction": POSITIONS["extraction"]}
    moved, findings = site_spawns.clear_crew_spawn(spec, inside)
    p = moved["spawn"]
    assert not _inside(p, (e9[0] - site_spawns.WALL_MARGIN, e9[1] - site_spawns.WALL_MARGIN,
                           e9[2] + site_spawns.WALL_MARGIN, e9[3] + site_spawns.WALL_MARGIN)), p
    assert [f["code"] for f in findings] == ["LOT_CREW_SPAWN_PUSHED"], findings
    crew = site_spawns.crew_spawns(spec, p, 4)
    rects = _blocker_rects(spec)
    for c in crew:
        assert not [bid for bid, r in rects.items() if _inside(c, r)], c


def test_the_fences_and_the_enemies_ask_one_band():
    """`plan_fences` leaves a row open rather than strand a marker in the band
    behind it, and `place_enemies` keeps out of that band. One function
    answers both (read as source)."""
    here = os.path.dirname(HERE)
    fences = open(os.path.join(here, "site_fences.py"), encoding="utf-8").read()
    spawns = open(os.path.join(here, "site_spawns.py"), encoding="utf-8").read()
    plan = fences[fences.index("def plan_fences"):]
    assert "shut_band(axis, front, sign, ground)" in plan
    assert "band[lo_i + 2] = front" not in plan
    assert "site_fences.shut_bands(" in spawns
