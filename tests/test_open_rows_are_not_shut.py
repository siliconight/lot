"""A row the fences leave open shuts nothing (0.122.0).

`plan_fences` leaves an Empty row open, unfenced, when a mission marker stands in the band behind its front line;
`site_spawns.place_enemies` kept every enemy out of every row's band anyway. On the factory's urban street the
near side's Empties stand between the mission's buildings, each a row of its own whose band runs from its front
line to the plate's edge across the plate's whole width -- the mission's own half of the plate, or the street.

The fixture is cold run 9289's urban_row_001 seed_9205 as `place_enemies` read it in its job (the factory's
`docs/findings/urban_street/spawn_filters.py`, whose rerun reproduced the job's enemies): there, all six enemies
were dropped (LOT_ENEMY_SPAWN_UNPLACEABLE) and Laser Tag refused the map.

THE INSTRUMENTS HERE ARE THE TEST'S OWN where they can be: a blocker's rect, a building's footprint and the far
row's front line are read from the fixture's fields, not through the functions this release changes.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import site_extent                    # noqa: E402
import site_fences                    # noqa: E402
import site_spawns                    # noqa: E402
import site_streets                   # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "urban_row_001_seed_9205.place_enemies.json")
STRIP = os.path.join(HERE, "fixtures", "restaurant_row_001_seed_9205.site.json")
STRIP_POSITIONS = {"spawn": (-8.0, 13.5, 0.0), "objective": (62.75, 0.5, 3.2),
                   "extraction": (-47.0, -15.47, 0.0)}


def _fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        d = json.load(f)
    return d["site_spec"], {k: tuple(v) for k, v in d["positions"].items()}


def _points(positions):
    return [tuple(positions[k][:2]) for k in ("spawn", "objective", "extraction")]


def _solids(spec):
    """``{id: rect}`` for every blocker (``size_x``/``size_y`` are world extents) and every building
    (``_footprint`` is its width and depth about ``at``; every building here stands at rot 0)."""
    out = {}
    for bk in spec["blockers"]:
        x, y, hx, hy = bk["at"][0], bk["at"][1], bk["size_x"] / 2.0, bk["size_y"] / 2.0
        out[bk["id"]] = (x - hx, y - hy, x + hx, y + hy)
    for b in spec["buildings"]:
        assert int(b.get("rot", 0)) % 360 == 0, b["id"]
        x, y = b["at"]
        hx, hy = b["_footprint"][0] / 2.0, b["_footprint"][1] / 2.0
        out[b["id"]] = (x - hx, y - hy, x + hx, y + hy)
    return out


def _inside(p, r):
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]


def test_the_fixture_is_the_starved_candidate():
    """Before trusting a fix against it: the far row and the near block, and the objective behind the near
    block's front line, where its band (on 0.121.0) shut it."""
    spec, positions = _fixture()
    ids = sorted(bk["id"] for bk in spec["blockers"])
    assert ids == ["e%d" % i for i in range(9)] + ["n0"], ids
    rows = site_fences.rows(spec)
    assert sorted(len(m) for _a, m in rows) == [1, 9]
    assert positions["objective"][:2] == (-42.0, -5.99)


def test_a_row_the_fences_leave_open_is_not_shut():
    spec, positions = _fixture()
    roads, plate = site_streets.roads(spec), site_extent.resolve(spec).rect
    found = []
    site_fences.plan_fences(spec, roads, plate, 0.7, markers=_points(positions), findings=found)
    left_open = [f for f in found if "left open" in str(f)]
    assert len(left_open) == 1, found                        # the near block's row, the objective behind it
    bands = site_fences.shut_bands(spec, roads, plate, markers=_points(positions))
    far_front = max(r[3] for bid, r in _solids(spec).items() if bid.startswith("e"))
    assert len(bands) == 1 and abs(bands[0][3] - far_front) < 1e-6, bands
    # without the mission's points every row is shut, as before
    assert len(site_fences.shut_bands(spec, roads, plate)) == 2


def test_the_starved_candidates_enemies_stand_on_open_ground():
    spec, positions = _fixture()
    plan = site_spawns.place_enemies(spec, positions)
    assert len(plan.positions) == 6, (plan.dropped, [f["code"] for f in plan.findings])
    solids = _solids(spec)
    far_front = max(r[3] for bid, r in solids.items() if bid.startswith("e"))
    for i, p in enumerate(plan.positions):
        assert not [bid for bid, r in solids.items() if _inside(p, r)], ("Enemy_%d" % i, p)
        assert p[1] > far_front + site_spawns.WALL_MARGIN, ("Enemy_%d" % i, p, far_front)


def test_a_strip_rows_band_stays_shut():
    """The strip's row is fenced -- no mission point behind it -- so its band is still kept out."""
    with open(STRIP, encoding="utf-8") as f:
        spec = json.load(f)
    roads, plate = site_streets.roads(spec), site_extent.resolve(spec).rect
    assert len(site_fences.shut_bands(spec, roads, plate, markers=_points(STRIP_POSITIONS))) == 1
    assert site_spawns.shut_band_rects(spec, markers=_points(STRIP_POSITIONS)) == \
        site_spawns.shut_band_rects(spec)


def test_one_question_answers_both():
    """`plan_fences` and `shut_bands` ask `markers_behind`, and nothing else spells it (read as source)."""
    here = os.path.dirname(HERE)
    fences = open(os.path.join(here, "site_fences.py"), encoding="utf-8").read()
    spawns = open(os.path.join(here, "site_spawns.py"), encoding="utf-8").read()
    assert "stranded = markers_behind(band, members, markers)" in fences      # plan_fences
    assert "if markers_behind(band, members, markers):" in fences            # shut_bands
    assert fences.count("band[0] < m[0] < band[2]") == 1                      # spelt once, in the helper
    assert "shut_band_rects(site_spec, markers=mission_points)" in spawns
