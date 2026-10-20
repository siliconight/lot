"""A building's declared drops reach the site, in site space (0.125.0, factory roadmap 173).

Deli Counter 0.226.0 files a one-way off-mesh `nav_link` on every `floor_hole` / `hatch` vertical link. Lot
carried `vertical_links` verbatim, which left those positions in building coordinates -- the seam cold run
9075 found for ladders. These run `merge_gameplay` against the real shell that declares both kinds.

Run:  python -m pytest tests/test_drop_links_reach_the_site.py -q
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import lot as L  # noqa: E402

#: deli_a03 declares a floor hole (story 1, 8.5, -4) and a hatch (story 1, -12, 8), and a stair link. Until 0.126.0
#: this pinned deli_a01, which Deli Counter 0.237.0 made hole-free ("stairs and ladders are primary"): its floor hole
#: went and this file's first test failed for a reason that was not Lot's.
SHELL = "deli_a03"
BUILD = os.path.join(HERE, "..", "deli_counter", "build")


def _drops():
    p = os.path.join(BUILD, SHELL + ".gameplay.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    return [v for v in (d.get("vertical_links") or []) if v.get("nav_link")]


def test_the_shell_this_pins_against_declares_drops_with_links():
    drops = _drops()
    assert drops is not None, "deli_counter/build/%s.gameplay.json is missing: build the library" % SHELL
    assert drops, "%s's vertical links carry no nav_link: Deli Counter 0.226.0 not built yet" % SHELL
    assert {v["kind"] for v in drops} == {"floor_hole", "hatch"}


def _merge(at, rot=0):
    """The site manifest for one placement of the pinned shell, as `merge_gameplay` builds it (the same
    fixture shape as tests/test_ladders_reach_the_site.py: `gameplay` is what it resolves the data from)."""
    site_spec = {"name": "t", "buildings": [
        {"id": "b0", "glb": SHELL + ".glb", "gameplay": SHELL + ".gameplay.json", "at": list(at), "rot": rot},
    ]}
    return L.merge_gameplay(site_spec, BUILD)


def _carried(site):
    return [v for v in site["vertical_links"] if v.get("nav_link")]


def test_a_drop_link_moves_with_the_building():
    """FAILS BEFORE THIS FIX: the link's points stayed in building coordinates."""
    at = (40.0, -10.0)
    site = _merge(at, 90)
    assert site["interactives"], "the fixture loaded no building data"
    carried = _carried(site)
    assert carried, site["vertical_links"][:2]
    local = {v["nav_link"]["id"]: v for v in _drops()}
    placement = {"at": list(at), "rot": 90}
    for v in carried:
        src = local[v["nav_link"]["id"]]
        for key in ("start_position", "end_position"):
            exp = L._place_point(*src["nav_link"][key], placement)
            assert v["nav_link"][key] == exp, (key, v["nav_link"][key], exp)
        for got, (hx, hy) in zip(v["nav_link"]["hole"], src["nav_link"]["hole"]):
            rx, ry = L._rotate_xy(hx, hy, 90)
            assert got == [rx + at[0], ry + at[1]], (got, hx, hy)
        assert v["building"] == "b0"


def test_height_is_preserved_because_buildings_share_the_ground():
    site = _merge((7.0, 7.0))
    local = {v["nav_link"]["id"]: v for v in _drops()}
    for v in _carried(site):
        src = local[v["nav_link"]["id"]]
        assert v["nav_link"]["start_position"][2] == src["nav_link"]["start_position"][2]
        assert v["nav_link"]["end_position"][2] == src["nav_link"]["end_position"][2]


def test_the_buildings_own_record_is_not_rewritten():
    before = json.dumps(_drops(), sort_keys=True)
    _merge((12.0, 3.0))
    assert json.dumps(_drops(), sort_keys=True) == before


def test_a_record_without_a_link_still_rides_verbatim():
    site = _merge((5.0, 5.0))
    plain = [v for v in site["vertical_links"] if not v.get("nav_link")]
    assert plain, "%s declares a descriptive stair link; expected it carried verbatim" % SHELL
    for v in plain:
        assert v["kind"] == "stair" and v["building"] == "b0"
