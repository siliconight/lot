"""A bank's drive-up lane (`site_driveup`, Zoo 1.138.0's `drive_up_canopy` and `drive_up_tube`): beside its wall,
served with the island on the driver's left, its pieces facing the served lane. FAILS ON 0.131.0, which has no
drive-up.
"""
import ast
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import lot              # noqa: E402
import site_driveup as D  # noqa: E402
import site_fields      # noqa: E402
import site_parking     # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(HERE, "specs")
ZOO = os.environ.get("LOT_ZOO_ROOT") or os.path.join(os.path.dirname(HERE), "zoo")
GROUND = (0.0, -20.0, 160.0, 80.0)
BANK = (60.0, 12.0, 80.0, 30.0)          # 20 m along the probe's road, its front 4 m behind the sidewalk


def _roads():
    return site_streets.roads(json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json"))))


def _plan(rects=None, slabs=(), standing=(), markers=(), ground=GROUND):
    findings = []
    recs, pieces = D.plan_driveups([("bank", (70.0, 12.0), "bank_branch_a02")], _roads(), list(slabs),
                                   rects or {"bank": BANK}, standing=standing, ground=ground, markers=markers,
                                   variants={"bank": 11}, findings=findings)
    return recs, pieces, findings


def test_the_island_is_on_the_drivers_left():
    # a driver heading north (+y) has west (-x) on the left
    assert D.served_travel((0.0, 1.0), (-1.0, 0.0)) == 1
    assert D.served_travel((0.0, 1.0), (1.0, 0.0)) == -1
    assert D.served_travel((1.0, 0.0), (0.0, 1.0)) == 1


def test_the_canopy_reaches_the_island_and_the_tube_its_run():
    # the canopy's column line is the island's centre; the station's tube top is the run's centre, 6 cm in
    assert D.CANOPY_W - D.CANOPY_COLUMN_IN == pytest.approx(D.LANE + D.ISLAND / 2.0)
    assert D.TUBE_H == pytest.approx(D.CANOPY_H - D.CANOPY_DECK - D.CANOPY_RUN_DROP + 0.06)


def test_a_drive_up_stands_beside_the_bank_its_pieces_facing_the_served_lane():
    recs, pieces, findings = _plan()
    assert len(recs) == 1 and not findings, findings
    (r,) = recs
    rect = r["rect"]
    # beside the bank: touching one end wall, from the back of the sidewalk (y 8) to the bank's rear (y 30)
    assert rect[1] == pytest.approx(8.0) and rect[3] == pytest.approx(30.0)
    assert rect[2] == pytest.approx(BANK[0]) or rect[0] == pytest.approx(BANK[2])
    assert rect[2] - rect[0] == pytest.approx(D.BLOCK)
    # the wall is the bank's end the block touches; from the block, it lies +x when the block is west of the bank
    west = rect[2] == pytest.approx(BANK[0])
    wall_x = BANK[0] if west else BANK[2]
    wall_dir = (1.0 if west else -1.0, 0.0)
    # its driveway crosses the sidewalk at the block's middle, the block's width
    dw = r["driveway"]
    assert dw["width"] == D.BLOCK and dw["a"][0] == pytest.approx((rect[0] + rect[2]) / 2.0)
    canopy, station = pieces
    assert canopy["species"] == "drive_up_canopy" and canopy["variant"] == 11
    assert station["species"] == "drive_up_tube" and station["dims"][2] == D.TUBE_H
    # the canopy's -X toward the wall; the station's receptacle (-Y) toward it, across the served lane
    y = math.radians(canopy["yaw"])
    assert (-math.cos(y)) * wall_dir[0] + (-math.sin(y)) * wall_dir[1] == pytest.approx(1.0)
    n = site_parking.nose(station["yaw"])
    assert n[0] * wall_dir[0] + n[1] * wall_dir[1] == pytest.approx(1.0)
    # the station on the island line, LANE + ISLAND / 2 off the wall; the canopy's module over the served lane
    assert abs(station["at"][0] - wall_x) == pytest.approx(D.LANE + D.ISLAND / 2.0)
    mx, _my = canopy["module_at"]
    # written to the millimetre, as every record is
    assert abs(mx - wall_x) == pytest.approx((D.CANOPY_W + D.WALL_BURY) / 2.0 - D.WALL_BURY, abs=1e-3)
    # the canopy's record is a column: footing-sized, on the island line
    assert canopy["size"] == [D.CANOPY_FOOTING, D.CANOPY_H, D.CANOPY_FOOTING]
    assert canopy["at"][0] == pytest.approx(station["at"][0])
    # and it is served with the island on the driver's left
    away = (0.0, 1.0)
    toward_island = ((station["at"][0] - wall_x) / abs(station["at"][0] - wall_x), 0.0)
    assert r["served_travel"] == ("away" if D.served_travel(away, toward_island) > 0 else "toward")


def test_an_end_that_does_not_fit_is_passed_and_neither_is_said():
    # a neighbour 3 m off each end: neither 9.2 m block fits
    rects = {"bank": BANK, "left": (40.0, 12.0, 57.0, 30.0), "right": (83.0, 12.0, 100.0, 30.0)}
    recs, pieces, findings = _plan(rects=rects)
    assert recs == [] and pieces == []
    assert any("LOT_DRIVEUP_NO_ROOM" in f for f in findings), findings
    # one neighbour only: the other end takes it
    rects = {"bank": BANK, "left": (40.0, 12.0, 57.0, 30.0)}
    (r,), _p, _f = _plan(rects=rects)
    assert r["rect"][0] == pytest.approx(BANK[2])


def _landing(x, y):
    return {"name": "landing", "family": "path", "centre": [x, y], "size": [3.0, 3.0], "yaw_deg": 0.0}


def test_a_door_landing_back_on_the_wall_shortens_the_lane_to_stop_short_of_it():
    """The bank level's both side walls carry a door's landing: the lane runs from the street to it, and stops."""
    # on the west wall, the end tried first: the lane stops at the landing's near edge (y 22.5)
    (r,), _p, _f = _plan(slabs=[_landing(55.0, 24.0)])
    assert r["rect"][2] == pytest.approx(BANK[0]) and r["rect"][1] == pytest.approx(8.0), r
    assert r["rect"][3] == pytest.approx(22.5) and r["rect"][3] - r["rect"][1] >= D.MIN_DEPTH - 1e-9
    # on the east wall with a neighbour taking the west end: the east lane stops at its landing
    (r,), _p, _f = _plan(rects={"bank": BANK, "left": (40.0, 12.0, 57.0, 30.0)}, slabs=[_landing(85.0, 24.0)])
    assert r["rect"][0] == pytest.approx(BANK[2]) and r["rect"][3] == pytest.approx(22.5), r
    # a landing on the OTHER wall does not shorten this one
    (r,), _p, _f = _plan(slabs=[_landing(85.0, 24.0)])
    assert r["rect"][2] == pytest.approx(BANK[0]) and r["rect"][3] == pytest.approx(30.0), r


def test_a_landing_too_near_the_street_refuses_that_end_and_both_are_said():
    # 6.5 m from the sidewalk's back: a lane stopped short of it is under MIN_DEPTH
    (r,), _p, _f = _plan(slabs=[_landing(55.0, 16.0)])
    assert r["rect"][0] == pytest.approx(BANK[2]), r
    recs, _p, findings = _plan(slabs=[_landing(55.0, 16.0), _landing(85.0, 16.0)])
    assert recs == [] and any("crosses drawn surface(s) landing" in f for f in findings), findings


def test_a_marker_on_the_island_refuses_it():
    # the island's plan point, read back from the station
    _r, pieces, _f = _plan()
    sx, sy = pieces[1]["at"]
    recs2, pieces2, findings = _plan(markers=[(sx, sy)])
    assert recs2 == [] and any("LOT_DRIVEUP_ON_A_MARKER" in f for f in findings), findings


def _recipe_constants(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def test_the_copied_measures_are_zoos():
    rec = os.path.join(ZOO, "zoo_keeper", "recipes", "drive_up_canopy.py")
    if not os.path.isfile(rec):
        pytest.skip("Zoo before 1.138.0, or none at %s (set LOT_ZOO_ROOT)" % ZOO)
    c = _recipe_constants(rec)
    assert c["DECK"] == D.CANOPY_DECK and c["TUBE_DROP"] == D.CANOPY_RUN_DROP
    assert c["FOOTING"][0] == D.CANOPY_FOOTING
    assert c["FOOTING"][0] / 2.0 + c["SHY"] == pytest.approx(D.CANOPY_COLUMN_IN)
    assert c["FOOTING"][0] / 2.0 + c["SHY"] == pytest.approx(D.CANOPY_COLUMN_END_IN)
    for species, dims in (("drive_up_canopy", (D.CANOPY_W + D.WALL_BURY, D.CANOPY_D, D.CANOPY_H)),
                          ("drive_up_tube", (D.STATION[0], D.STATION[1], D.TUBE_H))):
        g = json.load(open(os.path.join(ZOO, "zoo_keeper", "genome", "species", species + ".json"), encoding="utf-8"))
        for k, v in zip(("width", "depth", "height"), dims):
            assert g["dimensions"][k]["min"] <= v <= g["dimensions"][k]["max"], (species, k, v)
    g = json.load(open(os.path.join(ZOO, "zoo_keeper", "genome", "species", "drive_up_canopy.json"), encoding="utf-8"))
    assert g["module_variants"] == 16


def test_field_slabs_draws_a_drive_up_as_the_lots_asphalt():
    recs, _p, _f = _plan()
    slabs = lot.field_slabs({"driveups": recs})
    assert [s["name"] for s in slabs] == ["driveup_0"] and slabs[0]["family"] == "parking"
