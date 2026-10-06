"""The fence at the playable edge, phase one: an Empty row's gaps (Lot 0.97.0)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402
import site_fences as SF  # noqa: E402
import site_streets  # noqa: E402

#: The player's capsule, twice: what the caller passes (`lot._agent`).
BODY = 2 * lot._agent()["characters"]["player"]["radius_m"]
GROUND = (-30.0, -50.0, 30.0, 50.0)
_EW_ROAD = {"a": [-30, -24], "b": [30, -24], "width": 10.0, "sidewalk": 3.0}


def _empty(eid, x0, x1, y0=-46.0, y1=-34.0, rot=180):
    return {"id": eid, "empty": True, "rot": rot, "at": [(x0 + x1) / 2, (y0 + y1) / 2],
            "size_x": x1 - x0, "size_y": y1 - y0}


def _plan(blockers, roads=(_EW_ROAD,), ground=GROUND, **kw):
    site = {"name": "t", "buildings": [], "blockers": list(blockers), "roads": list(roads)}
    findings = []
    got = SF.plan_fences(site, site_streets.roads(site), ground, BODY,
                         findings=findings, **kw)
    return got, findings


def test_the_body_is_the_players_capsule():
    assert abs(BODY - 0.7) < 1e-9


def test_a_gap_a_body_fits_through_is_fenced_along_the_front_line():
    got, findings = _plan([_empty("e0", -10, -4), _empty("e1", -1, 5)])
    assert findings == []
    gap = next(p for p in got if p["breaks"] == "between e0 and e1")
    assert gap["species"] == "chain_link_fence" and gap["yaw"] == 0.0
    assert gap["dims"] == [3.0, SF.DEPTH, SF.HEIGHT]
    assert abs(gap["at"][0] - -2.5) < 1e-9
    # flush with the front facades, on the row's side of the line: the road
    # is to the north, so the fence's strip lies just below y = -34
    assert abs(gap["at"][1] - (-34.0 - SF.DEPTH / 2)) < 1e-3
    # and the two ends, out to the plate's edge
    assert sorted(p["dims"][0] for p in got) == [3.0, 20.0, 25.0]


def test_a_gap_too_narrow_for_a_body_is_left_alone():
    got, _ = _plan([_empty("e0", -10, -4), _empty("e1", -3.5, 2)], ground=None)
    assert got == []


def test_a_run_out_from_the_row_stops_at_a_road():
    ns_road = {"a": [20, -50], "b": [20, 50], "width": 8.0, "sidewalk": 2.0}  # box x 14..26
    got, findings = _plan([_empty("e0", -10, 5)], roads=(_EW_ROAD, ns_road))
    east = next(p for p in got if "beyond e0" in p["breaks"] and p["at"][0] > 0)
    assert abs(east["dims"][0] - 9.0) < 1e-9 and abs(east["at"][0] - 9.5) < 1e-9
    assert findings == []


def test_a_gap_a_path_crosses_is_not_fenced_and_is_said():
    path = (-4.5, -40.0, -0.5, -20.0)
    got, findings = _plan([_empty("e0", -10, -4), _empty("e1", -1, 5)], keep_out=[path])
    assert not any(p["breaks"] == "between e0 and e1" for p in got)
    assert any(f.startswith("LOT_FENCE_SKIPPED: between e0 and e1") for f in findings)


def test_a_fence_never_stands_on_a_mission_marker():
    got, findings = _plan([_empty("e0", -10, -4), _empty("e1", -1, 5)],
                          markers=[(-2.5, -34.5)])
    assert not any(p["breaks"] == "between e0 and e1" for p in got)
    assert any("mission marker" in f for f in findings)


def test_a_row_with_a_marker_behind_it_is_left_open_and_said():
    """Fenced, the band behind the front line is shut off from the street:
    a marker there would be stranded."""
    got, findings = _plan([_empty("e0", -10, -4), _empty("e1", -1, 5)],
                          markers=[(20.0, -45.0)])
    assert got == []
    assert any(f.startswith("LOT_FENCE_SKIPPED: row 0 left open") for f in findings)
    # a marker in front of the row strands nothing
    got, findings = _plan([_empty("e0", -10, -4), _empty("e1", -1, 5)],
                          markers=[(20.0, -20.0)])
    assert len(got) == 3 and findings == []


def test_the_fence_does_not_grow_the_plate_it_marks():
    """0.97.1. Cold run 9183's plate went 246 -> 254 m: the end runs reach
    the plate's edge, and counted as content they asked for CLEARANCE past
    themselves, so each ended 4 m short of the moved perimeter."""
    import site_extent
    site = {"name": "t", "buildings": [], "roads": [_EW_ROAD],
            "blockers": [_empty("e0", -10, -4), _empty("e1", -1, 5)],
            "ground": {"size_x": 60, "size_y": 100}}
    before = site_extent.resolve(site).rect
    fences = SF.plan_fences(site, site_streets.roads(site), before, BODY)
    assert any("end" in f["breaks"] for f in fences)
    site["cover"] = fences
    assert site_extent.resolve(site).rect == before
    # and the end runs still reach it, within the centimetre a run's length
    # is quantised to
    xs = [f["at"][0] + s * f["dims"][0] / 2 for f in fences for s in (-1, 1)]
    assert abs(min(xs) - before[0]) < SF.QUANTUM and abs(max(xs) - before[2]) < SF.QUANTUM


def test_a_row_facing_x_runs_along_y():
    ns_road = {"a": [10, -50], "b": [10, 50], "width": 10.0, "sidewalk": 3.0}
    got, _ = _plan([_empty("e0", 20, 32, -10, -4, rot=90), _empty("e1", 20, 32, -1, 5, rot=90)],
                   roads=(ns_road,), ground=None)
    (gap,) = got
    assert gap["yaw"] == 90.0 and gap["size"][0] == SF.DEPTH
    # the road is to the west: the front is the row's west edge, x = 20
    assert abs(gap["at"][0] - (20.0 + SF.DEPTH / 2)) < 1e-3
    assert abs(gap["at"][1] - -2.5) < 1e-9


def test_cold_run_9180s_row():
    """`workspaces/cold-9180-ws/.../warehouse_yard_001/candidate_seed_9004/
    site.json`: fifteen Empties across the street (`at` y -40.8, 12.3 deep,
    rot 180), the plate 115 x 102. One alley of 3.0 m between the seventh
    and eighth houses, and 4.0 m and 12.5 m at the row's ends."""
    xs = [(-50.45, 6.1), (-44.25, 6.3), (-37.95, 6.3), (-31.85, 5.9), (-25.6, 6.6),
          (-19.4, 5.8), (-13.1, 6.8), (-3.5, 6.4), (2.85, 6.3), (9.35, 6.7),
          (15.6, 5.8), (21.75, 6.5), (28.35, 6.7), (34.95, 6.5), (41.6, 6.8)]
    row = [{"id": f"e{i}", "empty": True, "rot": 180, "at": [x, -40.8],
            "size_x": w, "size_y": 12.3} for i, (x, w) in enumerate(xs)]
    roads = ({"a": [-57.5, -24.65], "b": [57.5, -24.65], "width": 10.0, "sidewalk": 3.0},
             {"a": [-1.5, -24.65], "b": [-1.5, 33.0], "width": 10.0, "sidewalk": 3.0})
    got, findings = _plan(row, roads=roads, ground=(-57.5, -51.0, 57.5, 51.0))
    assert findings == []
    assert sorted(round(p["dims"][0], 2) for p in got) == [3.0, 4.0, 12.5]
    assert {p["breaks"] for p in got} >= {"between e6 and e7"}
