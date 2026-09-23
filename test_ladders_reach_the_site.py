"""A building's ladders reach the site, in site space.

COLD RUN 9075 FALSIFIED the claim that Dispatch 0.5.0 carried a ladder's
off-mesh nav link into the package. That change patched Dispatch's DELI COUNTER
importer; a site mission runs the LOT importer, whose manifest is
`lot.gameplay.json`, and Lot concatenated its buildings' `interactives` while
dropping their `ladders`. The package shipped 23 gb_ladder surfaces and
`links: []`.

Unit tests on both sides had passed. What nobody tested was the SEAM, so these
run `merge_gameplay` -- the function that builds the site manifest -- against
the real shell that carries a ladder.

Run:  python -m pytest test_ladders_reach_the_site.py -q
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lot as L  # noqa: E402

#: The shell cold run 9075 actually shipped a ladder in.
SHELL = "market_hall_a01"
BUILD = os.path.join(HERE, "..", "deli_counter", "build")


def _has_ladder():
    p = os.path.join(BUILD, SHELL + ".gameplay.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    lads = [l for l in (d.get("ladders") or []) if l.get("nav_link")]
    return lads[0] if lads else None


def test_the_shell_this_pins_against_still_carries_a_ladder():
    """If this fails the fixture moved, not the code -- and the tests below
    would pass vacuously, which is the failure mode 9075 was made of."""
    assert _has_ladder() is not None, (
        f"{SHELL} no longer has a ladder with a nav_link; repoint these tests")


def test_a_ladder_reaches_the_site_manifest():
    """FAILS BEFORE THIS FIX: `merge_gameplay` had no `ladders` key at all."""
    lad = _has_ladder()
    assert lad is not None
    site_spec = {"name": "t", "buildings": [
        # `gameplay` is what merge_gameplay resolves the data from; a
        # building without it places fine and contributes nothing, which is
        # how the first draft of this test passed vacuously.
        {"id": "b0", "glb": SHELL + ".glb",
         "gameplay": SHELL + ".gameplay.json",
         "at": [100.0, 50.0], "rot": 90},
    ]}
    site = L.merge_gameplay(site_spec, BUILD)
    # A building whose gameplay ref does not resolve contributes NOTHING and
    # every list below would be empty -- which is how the first draft of this
    # test failed for the wrong reason. Prove the fixture loaded at all.
    assert site["interactives"], "the fixture loaded no building data"
    assert "ladders" in site, sorted(site)
    got = [l for l in site["ladders"] if l.get("nav_link")]
    assert got, "the site carries no ladder with a nav_link"
    assert got[0]["building"] == "b0"


def test_every_position_moves_together():
    """A nav link in site space beside route nodes in building space is worse
    than shipping nothing: an AI would path to where the ladder is not."""
    lad = _has_ladder()
    site_spec = {"name": "t", "buildings": [
        # `gameplay` is what merge_gameplay resolves the data from; a
        # building without it places fine and contributes nothing, which is
        # how the first draft of this test passed vacuously.
        {"id": "b0", "glb": SHELL + ".glb",
         "gameplay": SHELL + ".gameplay.json",
         "at": [100.0, 50.0], "rot": 90},
    ]}
    site = L.merge_gameplay(site_spec, BUILD)
    got = [l for l in site["ladders"] if l.get("nav_link")][0]
    start = got["nav_link"]["start_position"]
    # the foot of the climb, by three independent routes through the record
    assert got["lower_anchor"][:2] == start[:2], (got["lower_anchor"], start)
    assert got["route_nodes"]["lower_approach"][:2] == start[:2]
    assert got["traversal_component"]["climb_axis"][0][:2] == start[:2]
    # and it MOVED -- a pass that transformed nothing would also satisfy the
    # equalities above
    assert start[:2] != lad["nav_link"]["start_position"][:2], start


def test_height_is_preserved_because_buildings_share_the_ground():
    lad = _has_ladder()
    site_spec = {"name": "t", "buildings": [
        # `gameplay` is what merge_gameplay resolves the data from; a
        # building without it places fine and contributes nothing, which is
        # how the first draft of this test passed vacuously.
        {"id": "b0", "glb": SHELL + ".glb",
         "gameplay": SHELL + ".gameplay.json",
         "at": [100.0, 50.0], "rot": 90},
    ]}
    site = L.merge_gameplay(site_spec, BUILD)
    got = [l for l in site["ladders"] if l.get("nav_link")][0]
    assert got["nav_link"]["end_position"][2] == \
        lad["nav_link"]["end_position"][2]


def test_the_buildings_own_record_is_not_rewritten():
    """`merge_gameplay` reads these files for several passes. A shared nested
    dict would put site coordinates into the building's own gameplay.json."""
    before = json.dumps(_has_ladder(), sort_keys=True)
    site_spec = {"name": "t", "buildings": [
        # `gameplay` is what merge_gameplay resolves the data from; a
        # building without it places fine and contributes nothing, which is
        # how the first draft of this test passed vacuously.
        {"id": "b0", "glb": SHELL + ".glb",
         "gameplay": SHELL + ".gameplay.json",
         "at": [100.0, 50.0], "rot": 90},
    ]}
    L.merge_gameplay(site_spec, BUILD)
    assert json.dumps(_has_ladder(), sort_keys=True) == before
