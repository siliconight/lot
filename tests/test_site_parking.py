"""Cars parked in the kerb lanes' bays (roadmap 153), and a module stood
only when the kit index says it passed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot            # noqa: E402
import site_cover     # noqa: E402
import site_parking   # noqa: E402
import site_streets   # noqa: E402

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
        assert c["yaw"] == 90.0                       # length along an X road
        assert c["size"] == [4.3, 1.45, 1.75]         # plan x, height, plan y
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
    assert all(abs(s["transform"]["translation"][2] - 0.725) < 1e-6 for s in cars)


def test_a_module_the_index_failed_keeps_its_box(tmp_path):
    stem = "prop_simple_car_delco_1997_01_w175_d430_h145"
    (tmp_path / f"{stem}.glb").write_bytes(b"glTF")
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
