"""Cars parked in the kerb lanes' bays (roadmap 153), and a module stood
only when the kit index says it passed.
"""
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_cover     # noqa: E402
import site_parking   # noqa: E402
import site_streets   # noqa: E402
from tests.glb_fixture import write_glb  # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")


def _probe():
    return json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))


def test_bays_keep_clear_of_the_crossings_and_the_cuts():
    (road,) = site_streets.roads(_probe())
    bs = site_streets.bays(road)
    assert bs and {b["side"] for b in bs} == {"L", "R"}
    for b in bs:
        assert b["t1"] - b["t0"] == site_streets.BAY_LENGTH
        assert abs(abs(b["offset"]) - (5.0 - site_streets.LANE_DEPTH / 2)) < 1e-9
        for c in road.crossings:
            lo = c.t - c.width / 2 - site_streets.CROSSING_SETBACK
            hi = c.t + c.width / 2 + site_streets.CROSSING_SETBACK
            assert b["t1"] <= lo + 1e-9 or b["t0"] >= hi - 1e-9, (b, c)
        for t0, t1, is_cut in road.kerb(b["side"]).spans:
            if is_cut:
                assert b["t1"] <= t0 + 1e-9 or b["t0"] >= t1 - 1e-9


def test_the_edge_line_moves_to_the_driving_lanes_edge_and_bays_are_ticked():
    (road,) = site_streets.roads(_probe())
    marks = site_streets.markings([road])
    edges = [m for m in marks if m["kind"] == "edge_line"]
    assert {round(abs(m["at"][1]), 3) for m in edges} == {round(5.0 - site_streets.LANE_DEPTH, 3)}
    ticks = [m for m in marks if m["kind"] == "bay_tick"]
    assert ticks and all(m["size"] == [site_streets.LINE_WIDTH, site_streets.LANE_DEPTH] for m in ticks)
    assert len(ticks) <= 2 * len(site_streets.bays(road))


def test_a_share_of_the_bays_holds_a_car_parked_along_the_road():
    roads = site_streets.roads(_probe())
    cars = site_parking.plan_parking(roads, [], [(-60.0, 0.0)])
    bays = site_streets.bays(roads[0])
    assert 0 < len(cars) < len(bays)
    assert abs(len(cars) / len(bays) - site_parking.OCCUPANCY) < 0.2
    for c in cars:
        assert c["species"] == "simple_car" and c["source"] == "site_parking"
        assert c["yaw"] in (90.0, 270.0)              # length along an X road
        w, d, h = c["dims"]
        assert c["size"] == [d, h, w]                 # plan x, height, plan y
        assert 2.0 <= abs(c["at"][1]) <= 5.0
    # deterministic: the same spec parks the same cars
    assert site_parking.plan_parking(roads, [], [(-60.0, 0.0)]) == cars


def test_a_car_stands_clear_of_markers_and_of_what_already_stands():
    roads = site_streets.roads(_probe())
    free = site_parking.plan_parking(roads, [], [])
    first = free[0]
    x, y = first["at"]
    # a marker on that bay refuses it; a rect over it refuses it
    with_marker = site_parking.plan_parking(roads, [], [(x, y)])
    assert all(c["at"] != first["at"] for c in with_marker)
    rect = (x - 1, y - 1, x + 1, y + 1)
    with_rect = site_parking.plan_parking(roads, [rect], [])
    assert all(c["at"] != first["at"] for c in with_rect)
    # and every kept car is clear of the marker by the cover rule
    for c in with_marker:
        sx, _h, sy = c["size"]
        r = (c["at"][0] - sx / 2, c["at"][1] - sy / 2, c["at"][0] + sx / 2, c["at"][1] + sy / 2)
        assert not site_cover._inside((x, y), site_cover._grow(r, site_cover.MARKER_CLEARANCE))


def test_assemble_parks_cars_and_writes_them_as_slots(tmp_path):
    lot.assemble(os.path.join(SPECS, "coldrun_kerb_probe.json"), str(tmp_path))
    g = json.loads((tmp_path / "coldrun_kerb_probe.site.gameplay.json").read_text(encoding="utf-8"))
    assert g["parking_plan"]["placed"]
    doc = json.loads((tmp_path / "coldrun_kerb_probe.slots.json").read_text(encoding="utf-8"))
    cars = [s for s in doc["slots"] if s["species"] == "simple_car"]
    assert len(cars) >= len(g["parking_plan"]["placed"])
    # on the plate, centre-pivot: half the car's own height up
    assert all(abs(s["transform"]["translation"][2] - s["fit"]["dims"][2] / 2) < 1e-6 for s in cars)


def test_a_module_the_index_failed_keeps_its_box(tmp_path):
    stem = "prop_simple_car_delco_1997_01_w175_d430_h145"
    write_glb(tmp_path / f"{stem}.glb", stem)
    (tmp_path / "site_kit.built.json").write_text(json.dumps({
        "modules": [{"stem": stem, "status": "fail"}]}), encoding="utf-8")
    spec = {"cover": [{"at": [1.0, 2.0], "size": [4.3, 1.45, 1.75], "species": "simple_car",
                       "yaw": 90.0, "dims": [1.75, 4.3, 1.45]}],
            "cover_modules": {"dir": str(tmp_path), "theme": "delco_1997", "style": 1},
            "buildings": []}
    refs, ext, findings = lot.cover_module_refs(spec, "", str(tmp_path / "out"))
    assert refs == {} and ext == []
    assert findings[0][0] == lot.CODE_COVER_MODULE_FAILED and "'fail'" in findings[0][1]
    # a passing row, a row built with an advisory, or no index at all,
    # stands the module as before
    for status in ("pass", "warn"):
        (tmp_path / "site_kit.built.json").write_text(json.dumps({
            "modules": [{"stem": stem, "status": status}]}), encoding="utf-8")
        assert lot.cover_module_refs(spec, "", str(tmp_path / "out"))[0] == {0: f"cover_{stem}"}
    (tmp_path / "site_kit.built.json").unlink()
    assert lot.cover_module_refs(spec, "", str(tmp_path / "out"))[0] == {0: f"cover_{stem}"}


def test_what_already_stands_occludes_and_keeps_its_daylight():
    """Cold run 9028: a container at the junction with 28 cars parked,
    because the cars were planned after the cover. What stands before the
    planner runs breaks sightlines like a placed piece and a piece keeps
    clear of it."""
    ground = (-60.0, -30.0, 60.0, 30.0)
    points = {"LT_PlayerSpawn": (-50.0, 0.0), "LT_ObjectivePoint": (50.0, 0.0),
              "Enemy_0": (40.0, 0.0)}
    bare = site_cover.plan_cover(points, [], ground, opening_range=45.0,
                                 species=site_cover.COVER_SPECIES)
    assert bare.cover, "the bare line needs a piece"
    # a car parked across the line is already the cover
    car = (-3.0, -1.0, 3.0, 1.0)
    with_car = site_cover.plan_cover(points, [], ground, opening_range=45.0,
                                     species=site_cover.COVER_SPECIES, standing=[car])
    assert len(with_car.cover) < len(bare.cover) or not with_car.cover
    for c in with_car.cover:
        assert not site_cover._overlaps(c.rect, site_cover._grow(car, site_cover.COVER_EDGE_GAP)), c.rect


def test_assemble_parks_the_cars_before_it_places_cover(tmp_path):
    lot.assemble(os.path.join(SPECS, "coldrun_kerb_probe.json"), str(tmp_path))
    doc = json.loads((tmp_path / "coldrun_kerb_probe.slots.json").read_text(encoding="utf-8"))
    order = [s["species"] for s in doc["slots"]]
    first_car = order.index("simple_car")
    first_truck = next((i for i, s in enumerate(order) if s in ("box_truck", "cargo_container")), None)
    assert first_truck is None or first_car < first_truck


# ---------------------------------------------------------------------------
# 0.70.0: a mix of cars, each facing the way its lane travels
# ---------------------------------------------------------------------------
LOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Four axis-aligned roads, one each way, far enough apart that none crosses
#: another, so every bay is a plain parallel bay.
COMPASS = {"roads": [
    {"a": [-100.0, 0.0], "b": [100.0, 0.0], "width": 10, "sidewalk": 3},      # +x
    {"a": [100.0, 300.0], "b": [-100.0, 300.0], "width": 10, "sidewalk": 3},  # -x
    {"a": [400.0, -100.0], "b": [400.0, 100.0], "width": 10, "sidewalk": 3},  # +y
    {"a": [700.0, 100.0], "b": [700.0, -100.0], "width": 10, "sidewalk": 3},  # -y
]}
#: The same four and a road at 30 degrees, for the facing only (a footprint
#: is quantised to 0/90 by `site_cover.footprint`, so a diagonal's rect is
#: not a claim anything makes).
DIAGONAL = {"roads": COMPASS["roads"] + [
    {"a": [1000.0, 0.0], "b": [1000.0 + 173.205, 100.0], "width": 10, "sidewalk": 3}]}

#: Run in a fresh interpreter by the determinism test.
_PLAN_SCRIPT = """
import json, sys
sys.path.insert(0, sys.argv[1])
import site_parking, site_streets
out = []
for spec in json.loads(sys.argv[2]):
    for c in site_parking.plan_parking(site_streets.roads(spec), [], []):
        out.append([c["breaks"], c["dims"], c.get("style"), c["yaw"]])
print(json.dumps(out))
"""


def _bay_of(road, car):
    tag = car["breaks"].split()[1]
    return next(b for b in site_streets.bays(road)
                if b["side"] == tag[0] and b["index"] == int(tag[1:]))


def _road_of(roads, car):
    return roads[int(car["breaks"].rsplit(" ", 1)[1])]


def _stems(cars):
    return {lot.cover_module_stem(c["species"], "delco_1997", int(c.get("style") or 1), c["dims"])
            for c in cars}


def test_every_bay_picks_the_same_car_in_every_process():
    """Python's `hash()` of a string is salted per process; a choice made
    from it would park a different street in the themed assemble than in
    the greybox one the kit was built from. Two interpreters with different
    hash seeds, and this one, agree on every bay's car, style and yaw."""
    specs = [_probe(), COMPASS]
    here = []
    for spec in specs:
        for c in site_parking.plan_parking(site_streets.roads(spec), [], []):
            here.append([c["breaks"], c["dims"], c.get("style"), c["yaw"]])
    assert here and all(row[2] is not None for row in here), "a parked car carries its style"
    for seed in ("0", "4242"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        got = subprocess.run([sys.executable, "-c", _PLAN_SCRIPT, LOT_DIR, json.dumps(specs)],
                             env=env, capture_output=True, text=True, check=True).stdout
        assert json.loads(got) == here, f"PYTHONHASHSEED={seed}"


def test_a_street_of_six_or_more_cars_parks_more_than_one_module(tmp_path):
    """Until 0.70.0 every car was one (dims, style), so one stem, one module
    and one car, 42 times over on cold run 9050's bank block. Counted on the
    slots the kit reads too, so a choice that never reaches the manifest
    does not count."""
    for spec in (_probe(), COMPASS):
        roads = site_streets.roads(spec)
        cars = site_parking.plan_parking(roads, [], [])
        by_road = {}
        for c in cars:
            by_road.setdefault(_road_of(roads, c).index, []).append(c)
        streets = [v for v in by_road.values() if len(v) >= 6]
        assert streets, "the fixture has a street of six or more cars"
        for street in streets:
            assert len(_stems(street)) > 1, [c["breaks"] for c in street]
        out = tmp_path / "s.slots.json"
        lot.write_site_slots({"cover": cars}, str(out))
        slots = json.loads(out.read_text(encoding="utf-8"))["slots"]
        kinds = {(s["style"], tuple(s["fit"]["dims"])) for s in slots}
        assert len(kinds) == len(_stems(cars)) > 1
        assert len(kinds) <= len(site_parking.CARS) * site_parking.STYLES


def test_a_parallel_parked_car_faces_the_way_its_lane_travels_on_both_kerbs():
    """Traffic keeps right: the kerb a car is parked at is on the RIGHT of
    its nose. Derived here from the geometry alone -- the car's offset from
    the centre line against the nose's right-hand normal -- and not from
    `site_streets.right_side`, so a wrong table there fails this too. The
    nose of a slot at yaw is (sin yaw, -cos yaw): Zoo's car is nose -Y and a
    slot yaw is a counterclockwise plan rotation (0.69.4, measured)."""
    roads = site_streets.roads(DIAGONAL)
    cars = site_parking.plan_parking(roads, [], [])
    assert {c["breaks"].split()[1][0] for c in cars} == {"L", "R"}
    assert {_road_of(roads, c).index for c in cars} == {0, 1, 2, 3, 4}
    for c in cars:
        road = _road_of(roads, c)
        r = math.radians(c["yaw"])
        nx, ny = math.sin(r), -math.cos(r)
        assert abs(abs(nx * road.along[0] + ny * road.along[1]) - 1.0) < 1e-6, c
        t = (c["at"][0] - road.a[0]) * road.along[0] + (c["at"][1] - road.a[1]) * road.along[1]
        cx, cy = road.point(t, 0.0)
        ox, oy = c["at"][0] - cx, c["at"][1] - cy
        assert ox * ny + oy * -nx > 1.0, (c["breaks"], c["yaw"], "the kerb is not on the nose's right")


def test_every_parked_car_stands_inside_its_bay_at_its_own_dims():
    """Every row of the table fits a bay and clears the cover height, and
    every car planned on an axis-aligned road lies inside its painted bay --
    along the road inside t0..t1, across inside the parking lane -- with a
    collision box that is its own dims laid along the road."""
    for name, w, d, h, _wt in site_parking.CARS:
        assert d < site_streets.BAY_LENGTH and w < site_streets.LANE_DEPTH, name
        assert h >= site_cover.MIN_COVER_HEIGHT, name
    for spec in (_probe(), COMPASS):
        roads = site_streets.roads(spec)
        for c in site_parking.plan_parking(roads, [], []):
            road, (cw, cd, ch) = _road_of(roads, c), c["dims"]
            bay = _bay_of(road, c)
            sx, sh, sy = c["size"]
            assert sh == ch
            ax, ay = abs(road.along[0]), abs(road.along[1])
            assert abs((sx * ax + sy * ay) - cd) < 1e-9, c
            assert abs((sx * ay + sy * ax) - cw) < 1e-9, c
            for kx in (-0.5, 0.5):
                for ky in (-0.5, 0.5):
                    px, py = c["at"][0] + kx * sx, c["at"][1] + ky * sy
                    t = (px - road.a[0]) * road.along[0] + (py - road.a[1]) * road.along[1]
                    off = (px - road.a[0]) * road.perp[0] + (py - road.a[1]) * road.perp[1]
                    assert bay["t0"] - 1e-3 <= t <= bay["t1"] + 1e-3, (c["breaks"], t, bay)
                    assert abs(off - bay["offset"]) <= site_streets.LANE_DEPTH / 2 + 1e-3, \
                        (c["breaks"], off, bay)


def test_the_mix_fills_the_bays_the_single_car_filled_and_says_what_it_swapped():
    roads = site_streets.roads(_probe())
    marker = [(-60.0, 0.0)]
    mixed = site_parking.plan_parking(roads, [], marker)
    saved = site_parking.CARS
    try:
        site_parking.CARS = (("compact",) + site_parking.CAR[1:] + (1,),)
        single = site_parking.plan_parking(roads, [], marker)
    finally:
        site_parking.CARS = saved
    assert [c["breaks"] for c in mixed] == [c["breaks"] for c in single]
    # a rect just past the default car's nose and inside a long car's
    # refuses the long car; the bay takes a shorter one and says so
    free = site_parking.plan_parking(roads, [], [])
    longer = next(c for c in free if c["dims"][1] > site_parking.CAR[2])
    road = _road_of(roads, longer)
    reach = site_parking.CAR[2] / 2 + 0.1
    px = longer["at"][0] + road.along[0] * reach
    py = longer["at"][1] + road.along[1] * reach
    block = (px - 0.05, py - 0.05, px + 0.05, py + 0.05)
    swapped = next(c for c in site_parking.plan_parking(roads, [block], [])
                   if c["breaks"] == longer["breaks"])
    assert swapped["dims"][1] <= site_parking.CAR[2]
    assert swapped["car_asked"] == longer["car"]


def test_a_piece_resolves_to_the_module_of_its_own_style(tmp_path):
    """The slot says style 2, Zoo builds `_02_`, and the themed site stands
    `_02_` -- not the site's one style, which is another car."""
    dims = [1.75, 4.3, 1.45]
    cars = [{"at": [0.0, 0.0], "size": [4.3, 1.45, 1.75], "species": "simple_car",
             "yaw": 90.0, "dims": dims, "style": s} for s in (1, 2)]
    for s in (1, 2):
        stem = lot.cover_module_stem("simple_car", "delco_1997", s, dims)
        write_glb(tmp_path / f"{stem}.glb", stem)
    spec = {"cover": cars, "buildings": [],
            "cover_modules": {"dir": str(tmp_path), "theme": "delco_1997", "style": 1}}
    refs, _ext, findings = lot.cover_module_refs(spec, "", str(tmp_path / "out"))
    assert findings == []
    assert refs == {0: "cover_prop_simple_car_delco_1997_01_w175_d430_h145",
                    1: "cover_prop_simple_car_delco_1997_02_w175_d430_h145"}
    out = tmp_path / "s.slots.json"
    lot.write_site_slots(spec, str(out))
    assert [s["style"] for s in json.loads(out.read_text(encoding="utf-8"))["slots"]] == [1, 2]
