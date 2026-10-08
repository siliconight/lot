"""0.98.0 -- the getaway van at the kerb, where the crew starts and ends.

The walker, 2026-10-07: "location of the getaway vehicle should be the same as
the missions spawn point. you spawn, do the job, then return to the car";
2026-10-08: "go ahead, place it at the spawn". `site_getaway.plan` parks Zoo's
`step_van` in two bays at the kerb the spawn building's street door faces, and
puts ONE point on the sidewalk outside its kerb-side door that is both the
site's crew spawn and its extraction. These hold it to that, to the street's
rules, and to what every later planner, the audit and the enemies make of it.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_audit     # noqa: E402
import site_getaway   # noqa: E402
import site_parking   # noqa: E402
import site_spawns    # noqa: E402
import site_streets   # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")
PROBE = os.path.join(SPECS, "coldrun_kerb_probe.json")


def _probe():
    return json.load(open(PROBE, encoding="utf-8"))


def _plan(spec=None, findings=None):
    spec = spec or _probe()
    merged = lot.merge_gameplay(spec, SPECS)
    return site_getaway.plan(spec, merged, findings)


def _rect(rec):
    sx, _h, sy = rec["size"]
    x, y = rec["at"]
    return (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)


def test_the_van_parks_at_the_kerb_the_spawn_building_faces():
    """The garage stands north of the probe's one road (y 42), its street
    door at (-53.8, 28.0) facing south: the van parks on the north kerb,
    along the road, wholly on the carriageway, in Zoo's genome dims."""
    g = _plan()
    van = g["van"]
    (road,) = site_streets.roads(_probe())
    assert van["species"] == "step_van" and van["source"] == "getaway_van"
    assert van["dims"] == [2.6, 6.8, 3.05] and van["yaw"] in (90.0, 270.0)
    assert van["size"] == [6.8, 3.05, 2.6]                 # length along the X road
    x0, y0, x1, y1 = _rect(van)
    assert 0.0 < y0 and y1 <= road.width / 2.0             # north half, off the kerb
    assert g["door"] == [-53.8, 28.0]


def test_it_takes_two_adjacent_free_bays():
    """Longer than one 6.0 m bay, it lies inside a pair of adjacent bays the
    street rules allow -- clear of every crossing's setback and every cut."""
    g = _plan()
    (road,) = site_streets.roads(_probe())
    x0, _y0, x1, _y1 = _rect(g["van"])
    t0, t1 = x0 - road.a[0], x1 - road.a[0]
    side = [b for b in site_streets.bays(road) if b["offset"] > 0]
    spans = [(a["t0"], b["t1"]) for a, b in zip(side, side[1:]) if b["index"] == a["index"] + 1]
    assert any(lo - 1e-9 <= t0 and t1 <= hi + 1e-9 for lo, hi in spans), (t0, t1, spans)


def test_the_crew_spawns_and_leaves_at_its_door():
    """One point, the crew spawn AND the extraction, on the sidewalk outside
    the kerb-side door: DOOR_AHEAD toward the nose, SPAWN_OFF_KERB in from
    the kerb, and clear of the van's slot by more than a wall margin."""
    g = _plan()
    van = g["van"]
    spawn, extr = g["markers"]
    assert spawn["type"] == "crew_spawn" and extr["type"] == "extraction"
    assert spawn["at"] == extr["at"] and extr["getaway"] == "step_van"
    (road,) = site_streets.roads(_probe())
    x, y = spawn["at"]
    assert road.width / 2.0 < y < road.width / 2.0 + road.sidewalk
    assert abs(y - (road.width / 2.0 + site_getaway.SPAWN_OFF_KERB)) < 1e-9
    nx, ny = site_parking.nose(van["yaw"])
    along = (x - van["at"][0]) * nx + (y - van["at"][1]) * ny
    assert abs(along - site_getaway.DOOR_AHEAD) < 1e-6
    x0, y0, x1, y1 = _rect(van)
    gap = math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))
    assert gap > site_spawns.WALL_MARGIN + 0.2, gap


def test_no_enemy_can_stand_in_the_van():
    """By arithmetic: every corner of the van lies inside the standoff
    `place_enemies` keeps from the crew's spawn."""
    g = _plan()
    x0, y0, x1, y1 = _rect(g["van"])
    sx, sy = g["markers"][0]["at"]
    for cx in (x0, x1):
        for cy in (y0, y1):
            assert math.hypot(cx - sx, cy - sy) < site_spawns.MIN_STANDOFF


def test_what_has_no_van_says_why():
    f = []
    spec = dict(_probe(), mode="pvp_heist")
    assert _plan(spec, f) is None and "not a heist" in f[-1]
    spec = dict(_probe(), spawn="nowhere")
    assert _plan(spec, f) is None and "not placed" in f[-1]
    spec = dict(_probe(), site_markers=[{"type": "extraction", "at": [0, 60]}])
    assert _plan(spec, f) is None and "already declares extraction" in f[-1]
    spec = _probe()
    spec["roads"] = [dict(spec["roads"][0], width=6)]       # too narrow to park
    assert _plan(spec, f) is None and "no pair of free bays" in f[-1]
    assert all(m.startswith("LOT_GETAWAY_NONE:") for m in f)


def test_the_van_is_the_same_van_every_time():
    assert _plan() == _plan()


def test_assemble_parks_the_van_and_spawns_the_crew_at_it(tmp_path):
    lot.assemble(PROBE, str(tmp_path))
    g = json.loads((tmp_path / "coldrun_kerb_probe.site.gameplay.json").read_text(encoding="utf-8"))
    placed = g["getaway_plan"]["placed"]
    assert placed and placed["van"]["species"] == "step_van"
    doc = json.loads((tmp_path / "coldrun_kerb_probe.slots.json").read_text(encoding="utf-8"))
    vans = [s for s in doc["slots"] if s["species"] == "step_van"]
    assert len(vans) == 1
    assert vans[0]["material"] == "paint_matte" and vans[0]["fit"]["dims"] == [2.6, 6.8, 3.05]
    drawn = json.loads((tmp_path / "coldrun_kerb_probe.site.drawn.json").read_text(encoding="utf-8"))
    getaway = [m for m in drawn["site_markers"] if m.get("source") == "getaway_van"]
    assert {m["type"] for m in getaway} == {"crew_spawn", "extraction"}
    # every parked car keeps out of it
    van = _rect(placed["van"])
    for cv in drawn["cover"]:
        if cv.get("source") == "site_parking":
            r = _rect(cv)
            assert r[2] <= van[0] or r[0] >= van[2] or r[3] <= van[1] or r[1] >= van[3], cv["at"]


def test_the_audit_says_getaway_not_backtrack():
    """The exit IS the way in, by the walker's design: INFO, not a MED on
    every level; and a responder by the van is reported once, not twice."""
    site = {"name": "t", "mode": "heist",
            "buildings": [{"id": "b", "at": [0, 30]}, {"id": "o", "at": [60, 30]}],
            "spawn": "b", "objective": "o", "extraction": "b",
            "site_markers": [
                {"type": "crew_spawn", "at": [0, -30], "source": "getaway_van"},
                {"type": "extraction", "at": [0, -30], "source": "getaway_van",
                 "getaway": "step_van"},
                {"type": "responder_spawn", "at": [2, -30]},
            ],
            "cover": [], "roads": [], "blockers": []}
    rows = site_audit.audit(site)["findings"]
    codes = [c for _, c, _ in rows]
    assert "S_GETAWAY_AT_SPAWN" in codes and "S_BACKTRACK" not in codes
    camp = [m for _, c, m in rows if c == "S_RESPONDER_CAMP"]
    assert len(camp) == 1 and "crew spawn and extraction" in camp[0]
    # without the van's mark the same geometry is still a rewound exit
    plain = dict(site, site_markers=[dict(m) for m in site["site_markers"]])
    plain["site_markers"][1].pop("getaway")
    assert "S_BACKTRACK" in [c for _, c, _ in site_audit.audit(plain)["findings"]]


def test_enemies_spread_along_one_leg_of_a_there_and_back_route():
    """Spawn and extraction one point: the enemies stand along spawn ->
    objective, none past the objective, none closer to the spawn than the
    standoff, and none shoved off the route. MEASURED on this field with
    the three-point sample (`THERE_AND_BACK` 0): two enemies mirrored at
    one x (25.7) and one pushed 43.5 m off the route, because the return
    leg is the outbound one backwards; along one leg, all six within
    6.5 m of it."""
    spec = {"name": "t", "ground": {"size_x": 200, "size_y": 120},
            "buildings": [], "roads": [], "blockers": []}
    pos = {"spawn": (-60.0, 0.0, 0.0), "objective": (40.0, 0.0, 0.0), "extraction": (-60.0, 0.0, 0.0)}
    plan = site_spawns.place_enemies(spec, pos)
    assert plan.positions, plan.findings
    for ex, ey, _ez in plan.positions:
        assert -60.0 + site_spawns.MIN_STANDOFF - 1e-6 <= ex <= 40.0 + 1e-6, (ex, ey)
        assert math.hypot(ex + 60.0, ey) >= site_spawns.MIN_STANDOFF - 1e-6
        assert abs(ey) <= 10.0, ("shoved off the route", ex, ey)
