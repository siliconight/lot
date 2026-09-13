"""The street rules (docs/STREET_RULES.md) as assertions.

Stop signs, MUTCD: one per stop-controlled approach, on the approaching
driver's right; the plate's near edge at least 1.83 m from the pavement
edge; no more than 15.2 m from the intersecting travelled way; about 1.2 m
before the leg's marked crosswalk; a second on the left only on a
multi-lane approach; the plate facing the driver; none at a footpath
crossing, none at a signalised junction. Crosswalks, NACTO: every leg of a
signalised junction is marked.

The measurements here are taken from what Lot WRITES -- the transform text,
the markings -- not from the planner's own intermediate numbers, so a
planner that agrees with itself and not with the scene still fails.
Traffic keeps right. Plan metres, spec Z-up.
"""
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_streets     # noqa: E402

PLATE_W = site_furniture.SPECIES["stop_sign"][0]
#: The rules' own numbers, written out rather than read from the planner's
#: constants, so moving a constant cannot move the rule with it.
LATERAL_MIN = 1.83          # 6 ft, pavement edge to the plate
MAX_FROM_JUNCTION = 15.2    # 50 ft
BEFORE_CROSSWALK = 1.2      # 4 ft


def _spec(roads, paths=(), buildings=()):
    return {"name": "rules", "ground": {"size_x": 260, "size_y": 260},
            "buildings": list(buildings), "paths": list(paths), "roads": roads}


def _written_face(piece):
    """Where the blade's face points in plan, read off the transform Lot
    writes for the module. Godot 4.7 parses the twelve numbers as basis
    ROWS (measured with `str_to_var`); a Zoo stop sign faces its local +Z
    after the Y-up export; plan is Godot (x, -z)."""
    txt = lot._godot_transform(tuple(piece["at"]), float(piece["yaw"]))
    n = [float(v) for v in txt.split(",")]
    zx, _zy, zz = n[2], n[5], n[8]          # basis * (0, 0, 1)
    return (zx, -zz)


def _local(road, xy):
    dx, dy = xy[0] - road.a[0], xy[1] - road.a[1]
    return (dx * road.along[0] + dy * road.along[1],
            dx * road.perp[0] + dy * road.perp[1])


def _painted_bands(road, roads):
    """[(t0, t1)] of each crosswalk ``road`` paints, from its bars."""
    bars = sorted((_local(road, m["at"])[0] - m["size"][0] / 2,
                   _local(road, m["at"])[0] + m["size"][0] / 2)
                  for m in site_streets.markings(roads)
                  if m["kind"] == "crosswalk_bar" and m["road"] == road.index)
    bands = []
    for b0, b1 in bars:
        if bands and b0 - bands[-1][1] <= site_streets.BAR_GAP + 1e-6:
            bands[-1] = (bands[-1][0], b1)
        else:
            bands.append((b0, b1))
    return bands


def _check_stop_sign(piece, road, roads, travel, crosser, at_crosswalk=True):
    """Every placement rule for one right-hand stop sign serving a driver
    travelling ``travel`` along ``road`` toward ``crosser``."""
    t, off = _local(road, piece["at"])
    # on the driver's right: travelling +t the right is negative offset
    assert (off < 0) == (travel > 0), (piece, travel)
    # the plate faces the driver: back down the road against travel
    fx, fy = _written_face(piece)
    back = (-travel * road.along[0], -travel * road.along[1])
    assert fx * back[0] + fy * back[1] > 0.999, (piece, (fx, fy), back)
    # lateral: the plate stands across the road, its near edge half a plate
    # nearer the pavement than the post
    near_edge = abs(off) - road.width / 2.0 - PLATE_W / 2.0
    assert near_edge >= LATERAL_MIN - 1e-6, (piece, near_edge)
    # on the band
    assert abs(off) + PLATE_W / 2.0 <= road.width / 2.0 + road.sidewalk + 1e-6
    # longitudinal: within 15.2 m of the crossing road's travelled way
    (cut,) = [c for c in road.crossings if c.kind == "road" and c.crosser == crosser]
    edge_t = cut.t - travel * cut.width / 2.0
    to_edge = travel * (edge_t - t)
    assert 0.0 < to_edge <= MAX_FROM_JUNCTION + 1e-6, (piece, to_edge)
    # about 1.2 m before the leg's painted crosswalk
    if at_crosswalk:
        ahead = [travel * ((b0 if travel > 0 else b1) - t)
                 for b0, b1 in _painted_bands(road, roads)]
        ahead = [d for d in ahead if d > 0]
        assert ahead and abs(min(ahead) - BEFORE_CROSSWALK) < 1e-6, (piece, ahead)
    return to_edge


def test_the_stem_of_an_unsignalised_t_gets_one_sign_by_the_rules_either_way_round():
    # a side street of two 8 m roads with 3 m bands: no parking, no arterial
    for stem, travel in (({"a": [0, 0], "b": [0, 60], "width": 8, "sidewalk": 3}, -1),
                         ({"a": [0, 60], "b": [0, 0], "width": 8, "sidewalk": 3}, 1),
                         ({"a": [0, 0], "b": [0, -60], "width": 8, "sidewalk": 3}, -1),
                         ({"a": [0, -60], "b": [0, 0], "width": 8, "sidewalk": 3}, 1)):
        roads = site_streets.roads(_spec([{"a": [-80, 0], "b": [80, 0], "width": 8,
                                           "sidewalk": 3}, stem]))
        findings = []
        pieces = site_furniture.plan_furniture(roads, findings=findings)
        stops = [p for p in pieces if p["species"] == "stop_sign"]
        assert len(stops) == 1, (stem, stops)
        assert stops[0]["road"] == 1                     # the leg that ends stops
        _check_stop_sign(stops[0], roads[1], roads, travel, crosser=0)
        assert not [p for p in pieces if p["species"] == "traffic_signal"]
        assert findings == []


def test_a_sign_blocked_by_a_crossing_steps_back_and_never_past_the_limit():
    tee = [{"a": [-80, 0], "b": [80, 0], "width": 8, "sidewalk": 3},
           {"a": [0, 0], "b": [0, 60], "width": 8, "sidewalk": 3}]
    # a 4 m path across the stem where the sign would stand: it steps back
    # up the leg, past the dropped kerb and the paint, and stays in reach
    roads = site_streets.roads(_spec(tee, paths=[{"a": [-20, 9.5], "b": [20, 9.5], "width": 4}]))
    findings = []
    (stop,) = [p for p in site_furniture.plan_furniture(roads, findings=findings)
               if p["species"] == "stop_sign"]
    to_edge = _check_stop_sign(stop, roads[1], roads, -1, crosser=0, at_crosswalk=False)
    assert to_edge > 7.0 and findings == []
    for k in roads[1].kerbs:
        assert site_furniture._clear_of_cuts(stop["t"], 0.04, k)
    # a 20 m one pushes every clear station past 15.2 m: no sign, and said
    roads = site_streets.roads(_spec(tee, paths=[{"a": [-20, 15], "b": [20, 15], "width": 20}]))
    findings = []
    assert not [p for p in site_furniture.plan_furniture(roads, findings=findings)
                if p["species"] == "stop_sign"]
    assert [f for f in findings if f.startswith("LOT_STOP_SIGN_NO_ROOM")]


def test_a_multi_lane_approach_gets_a_second_sign_on_the_left():
    # a 20 m stem with parking drives 7.8 m each way: two lanes
    roads = site_streets.roads(_spec([{"a": [-80, 0], "b": [80, 0], "width": 8, "sidewalk": 3},
                                      {"a": [0, 0], "b": [0, 60], "width": 20, "sidewalk": 3}]))
    assert site_streets.approach_lanes(roads[1]) == 2
    stops = [p for p in site_furniture.plan_furniture(roads) if p["species"] == "stop_sign"]
    assert len(stops) == 2
    right = [p for p in stops if _local(roads[1], p["at"])[1] > 0]      # -t: right is +offset
    left = [p for p in stops if _local(roads[1], p["at"])[1] < 0]
    assert len(right) == 1 and len(left) == 1
    _check_stop_sign(right[0], roads[1], roads, -1, crosser=0)
    # the left sign serves the same driver: same station, same facing
    assert right[0]["t"] == left[0]["t"]
    assert _written_face(left[0]) == _written_face(right[0])
    # and a single-lane stem gets none on the left
    narrow = site_streets.roads(_spec([{"a": [-80, 0], "b": [80, 0], "width": 8, "sidewalk": 3},
                                       {"a": [0, 0], "b": [0, 60], "width": 12, "sidewalk": 3}]))
    assert site_streets.approach_lanes(narrow[1]) == 1
    assert len([p for p in site_furniture.plan_furniture(narrow)
                if p["species"] == "stop_sign"]) == 1


def test_an_x_of_unequal_roads_stops_the_minor_road_on_both_approaches():
    """central_vault's shape: a 9 m and an 8 m road crossing, neither an
    arterial. The narrower yields; the wider keeps its right of way."""
    roads = site_streets.roads(_spec([{"a": [-110, -20], "b": [110, -20], "width": 9, "sidewalk": 3},
                                      {"a": [10, -85], "b": [10, 80], "width": 8, "sidewalk": 3}]))
    stops = [p for p in site_furniture.plan_furniture(roads) if p["species"] == "stop_sign"]
    assert {p["road"] for p in stops} == {1} and len(stops) == 2
    travels = set()
    for p in stops:
        t, _o = _local(roads[1], p["at"])
        (cut,) = [c for c in roads[1].crossings if c.kind == "road"]
        travel = 1 if t < cut.t else -1
        travels.add(travel)
        _check_stop_sign(p, roads[1], roads, travel, crosser=0)
    assert travels == {1, -1}
    # two equal roads: an all-way stop, four signs
    equal = site_streets.roads(_spec([{"a": [-110, 0], "b": [110, 0], "width": 8, "sidewalk": 3},
                                      {"a": [0, -110], "b": [0, 110], "width": 8, "sidewalk": 3}]))
    assert len([p for p in site_furniture.plan_furniture(equal)
                if p["species"] == "stop_sign"]) == 4


def test_a_band_too_narrow_for_the_offset_places_the_sign_and_says_so():
    roads = site_streets.roads(_spec([{"a": [-80, 0], "b": [80, 0], "width": 8, "sidewalk": 1},
                                      {"a": [0, 0], "b": [0, 60], "width": 8, "sidewalk": 1}]))
    findings = []
    stops = [p for p in site_furniture.plan_furniture(roads, findings=findings)
             if p["species"] == "stop_sign"]
    assert len(stops) == 1
    _t, off = _local(roads[1], stops[0]["at"])
    # as far out as the plate still stands over the 1 m band
    assert abs(abs(off) - (4.0 + 1.0 - PLATE_W / 2.0)) < 1e-6
    assert [f for f in findings if f.startswith("LOT_STOP_SIGN_OFFSET_SHORT")]


def _cold_run_9049():
    """The roads, paths and buildings of cold run 9049's generated site spec
    (`bank_block_001/candidate_seed_9049/site.json`, sha256 4f759a02...): a
    signalised T, three 4 m door spurs ending on the through road's centre
    line and an 8 m building path across the side street."""
    y = -23.150000005960464
    return _spec(
        roads=[{"a": [-90.5, y], "b": [90.5, y], "sidewalk": 3.0, "width": 10.0},
               {"a": [-35.5, y], "b": [-35.5, 35.5], "sidewalk": 3.0, "width": 10.0}],
        paths=[{"from": "b0", "to": "b1", "width": 8.0},
               {"from": "b1", "to": "b2", "width": 8.0},
               {"a": [-62.0, -9.150000005960464], "b": [-62.0, y], "width": 4.0},
               {"a": [0.0, -14.150000005960464], "b": [0.0, y], "width": 4.0},
               {"a": [59.0, -3.1500000059604645], "b": [59.0, y], "width": 4.0}],
        buildings=[{"id": "b0", "at": [-62, 10]}, {"id": "b1", "at": [0, 0]},
                   {"id": "b2", "at": [59, 10]}])


def test_cold_run_9049_has_no_stop_sign_at_a_footpath_or_under_its_signal():
    """0.69.3 planned eight stop signs on this site: one at each door spur,
    a pair at the building path across the side street, and a pair on the
    side street's kerbs inside the signalised junction."""
    spec = _cold_run_9049()
    roads = site_streets.roads(spec)
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    assert not [p for p in pieces if p["species"] == "stop_sign"]
    assert [p["species"] for p in pieces if p["species"] == "traffic_signal"] == ["traffic_signal"]


def test_every_leg_of_a_signalised_junction_is_marked():
    """NACTO: a signalised junction marks every leg that has pedestrian
    access. Checked against the paint, per leg."""
    for spec in (_cold_run_9049(),
                 _spec([{"a": [-80, 0], "b": [80, 0], "width": 10, "sidewalk": 3},
                        {"a": [0, 0], "b": [0, 60], "width": 10, "sidewalk": 3}]),
                 _spec([{"a": [-80, 0], "b": [80, 0], "width": 10, "sidewalk": 3},
                        {"a": [0, -80], "b": [0, 80], "width": 8, "sidewalk": 3}])):
        roads = site_streets.roads(spec)
        legs = site_streets.approaches(roads)
        signal = [ap for ap in legs if ap.control == "signal"]
        assert signal and len({ap.control for ap in legs}) == 1, legs
        for ap in signal:
            road = roads[ap.road]
            lo, hi = site_streets.crossing_box(
                next(c for c in road.crossings if c.kind == "road" and c.crosser == ap.crosser))
            bands = _painted_bands(road, roads)
            if ap.travel > 0:
                marked = [b for b in bands if lo - 1e-6 <= b[0] and b[1] <= ap.station]
            else:
                marked = [b for b in bands if ap.station <= b[0] and b[1] <= hi + 1e-6]
            assert ap.ped_access and marked, (ap, bands)
        assert not [p for p in site_furniture.plan_furniture(roads)
                    if p["species"] == "stop_sign"]


def test_the_stop_bar_is_on_the_approaching_drivers_lane():
    roads = site_streets.roads(_spec([{"a": [-80, 0], "b": [80, 0], "width": 8, "sidewalk": 3},
                                      {"a": [0, 0], "b": [0, 60], "width": 8, "sidewalk": 3}]))
    (bar,) = [m for m in site_streets.markings(roads)
              if m["kind"] == "stop_bar" and m["road"] == 1]
    _t, off = _local(roads[1], bar["at"])
    assert off > 0           # the -t driver's half, the side of the right-hand sign
    (stop,) = [p for p in site_furniture.plan_furniture(roads) if p["species"] == "stop_sign"]
    assert (_local(roads[1], stop["at"])[1] > 0) == (off > 0)


def test_plate_facing_matches_the_written_transform():
    for yaw in (0.0, 30.0, 90.0, 180.0, 270.0):
        fx, fy = site_furniture.plate_facing(yaw)
        wx, wy = _written_face({"at": [0.0, 0.0], "yaw": yaw})
        assert math.isclose(fx, wx, abs_tol=1e-6) and math.isclose(fy, wy, abs_tol=1e-6)


def test_each_marking_wears_its_own_paint_offset_and_keeps_it(tmp_path):
    """Paint projects in world space, so bars a whole number of tiles apart
    wore the same scuffs (5 of 210 pairs on cold run 9044). Each marking's
    material carries its own `uv1_offset`, the same on every build."""
    import json
    import re
    pack = tmp_path / "road_paint_delco_1997"
    pack.mkdir()
    (pack / "road_paint_delco_albedo.png").write_bytes(b"PNG")
    (pack / "road_paint_delco.pack.json").write_text(json.dumps({
        "maps": {"albedo": "road_paint_delco_albedo.png"}, "meters_per_tile": 8.0,
        "material_profile": "road_paint_delco",
        "import_hints": {"interpolation": "nearest",
                         "transparency": {"opacity": 1.0, "alpha_mode": "scissor"}}}),
        encoding="utf-8")
    spec = _spec([{"a": [-60, 0], "b": [60, 0], "width": 10, "sidewalk": 3},
                  {"a": [0, 0], "b": [0, 50], "width": 10, "sidewalk": 3}])
    spec["ground_skins"] = {"paint": str(pack)}
    skins, _f = lot.ground_skins(spec)

    def offsets():
        _body, sub = lot._outdoor_nodes(spec, skins=skins)
        txt = "\n".join(sub)
        found = re.findall(r'id="Mat_(mark_\d+_\w+)"\]\n(?:[^\[]*?)uv1_offset = Vector3\(([^)]*)\)',
                           txt)
        return dict(found)

    first = offsets()
    n_marks = len(site_streets.markings(site_streets.roads(spec)))
    assert len(first) == n_marks > 10
    assert len(set(first.values())) == n_marks            # no two markings share one
    assert offsets() == first                             # stable within a process
    # and across processes, whose str hash is salted differently
    key = "0|crosswalk_bar|-7.750|0.000"
    code = ("import sys; sys.path.insert(0, %r); import lot; print(lot.paint_offset(%r))"
            % (os.path.dirname(os.path.dirname(os.path.abspath(__file__))), key))
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONHASHSEED=seed)).stdout.strip()
            for seed in ("1", "2")}
    assert outs == {str(lot.paint_offset(key))}
    # without a paint pack the flat greybox paint carries no offset
    plain = dict(spec)
    plain.pop("ground_skins")
    _body, sub = lot._outdoor_nodes(plain)
    assert "uv1_offset" not in "\n".join(sub)
