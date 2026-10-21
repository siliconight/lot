"""Lot's carried copies of the agent contract equal the contract, and `LOT_COVER_PINCH` states the
threshold its check used (Lot 0.120.2).

`site_cover._NAV_BAKE_FALLBACK` said cell_size_m 0.15 from 2026-07-29 until Lot 0.120.2. That was the
contract's value on the day it was written, 2026-07-27; two days later the contract moved to 0.1 and
recorded why in its own `cell_size_derivation` -- 0.15 capped the connected slope at 45 deg against a
stated 55, and eight path proofs failed as disjoint islands. `lot._AGENT_DEFAULTS` was refreshed the
next day; this copy was not, and nothing compared either with the file.

What it cost: `lot.py` hands `plan_cover` the contract's bake, so the pinch read-back measured lanes
against 1.0 m, while `findings` stated `min_passable_gap()` -- no bake, the fallback's -- and
`LOT_COVER_PINCH` said 1.2 m above it. Under a bake whose gap is neither, it listed a lane wider than
the number it said the lane was under.

The guard is `deli_counter/test_agent_contract.py`'s: not the number, the invariant.

    python -m pytest tests/test_cover_fallback.py -q
"""
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import lot          # noqa: E402
import site_cover   # noqa: E402


def _contract_path():
    """Where `lot._agent` looks, in its order: $DC_AGENT_CONTRACT, then the deli_counter sibling."""
    for path in (os.environ.get("DC_AGENT_CONTRACT"),
                 os.path.join(os.path.dirname(HERE), "deli_counter", "agent_contract.json")):
        if path and os.path.isfile(path):
            return path
    return None


def _live():
    path = _contract_path()
    if path is None:
        pytest.skip("no deli_counter/agent_contract.json beside this checkout")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pairs(defaults, live, path=""):
    """Every (dotted key, fallback, contract value) the two blocks share."""
    for key, fallback in defaults.items():
        if key not in live:
            continue
        here = f"{path}{key}"
        if isinstance(fallback, dict) and isinstance(live[key], dict):
            yield from _pairs(fallback, live[key], here + ".")
        else:
            yield here, fallback, live[key]


def _copies(live):
    """Lot's two carried copies, each beside the block of the contract it copies."""
    return [("lot._AGENT_DEFAULTS", lot._AGENT_DEFAULTS, live),
            ("site_cover._NAV_BAKE_FALLBACK", site_cover._NAV_BAKE_FALLBACK, live["nav_bake"])]


def test_every_fallback_equals_the_ratified_value():
    """THE GUARD. Not the one number -- the invariant, over both copies Lot carries, so the next value
    to move cannot rot the same way while both copies still look plausible."""
    drift = [(name, k, f, v) for name, copy, block in _copies(_live())
             for k, f, v in _pairs(copy, block) if f != v]
    assert drift == [], "\n".join(
        f"  {name} {k}: fallback {f!r}, contract {v!r}" for name, k, f, v in drift)


def test_the_shared_keys_are_actually_shared():
    """A guard that compares an empty intersection passes for free. Every key of the cover fallback is
    in the contract, and the agent defaults share at least the 19 keys they share today: 21 until 0.126.1,
    when the fallback stopped mirroring `npc_standard`'s radius and height, which Lot never read and the
    contract stopped restating (Deli Counter 0.253.0, the factory's roadmap 292)."""
    (_n1, defaults, whole), (_n2, cover, bake) = _copies(_live())
    assert len(list(_pairs(cover, bake))) == len(cover), sorted(cover)
    assert len(list(_pairs(defaults, whole))) >= 19, [k for k, _f, _v in _pairs(defaults, whole)]


def test_with_no_bake_the_gap_is_the_contracts():
    """A caller that passes no bake -- the message did, `BUILDING_CLEARANCE` does -- gets the gap and
    the clearance the contract's bake gives. 0.120.1: 1.2 m and 2.7 m against 1.0 m and 2.5 m."""
    bake = _live()["nav_bake"]
    assert site_cover.min_passable_gap() == site_cover.min_passable_gap(bake)
    assert site_cover.BUILDING_CLEARANCE == site_cover.building_clearance(site_cover.COVER_SIZE, bake)


#: One 3 m square piece lands at (35, 0), on the 100 m line from the crew to the enemy, and the room
#: beside a wall is forced to nothing, so a wall whose face is `lane` metres off the piece's edge
#: stands where it is put.
POINTS = {"LT_PlayerSpawn": (0.0, 0.0), "Enemy_0": (100.0, 0.0)}
GROUND = (-20.0, -30.0, 120.0, 30.0)


def _plan(lane, bake):
    wall = (30.0, 1.5 + lane, 40.0, 12.0)
    return site_cover.plan_cover(POINTS, [wall], GROUND, opening_range=45.0, clearance=0.0,
                                 nav_bake=bake)


def _stated(plan):
    """The number `LOT_COVER_PINCH` says a lane was closed to less than."""
    found = site_cover.findings(plan, opening_range=45.0)
    pinch = [f for f in found if f["code"] == "LOT_COVER_PINCH"]
    assert len(pinch) == 1, [f["code"] for f in found]
    m = re.search(r"less than the ([0-9.]+) m", pinch[0]["message"])
    assert m, pinch[0]["message"]
    return float(m.group(1))


def test_the_pinch_message_states_the_threshold_the_check_used():
    """A 0.25 m cell bakes away 1.5 m, so a 1.3 m lane is a pinch under it and under neither the
    fallback's gap nor the contract's. 0.120.1 listed that lane as "less than the 1.2 m an agent can
    walk through"."""
    bake = {"agent_radius_m": 0.4, "cell_size_m": 0.25}
    used = site_cover.min_passable_gap(bake)
    assert used == 1.5 and used != site_cover.min_passable_gap(), "the fixture must tell the two apart"
    plan = _plan(1.3, bake)
    assert [g for _n, _w, g in plan.pinches] == [1.3], plan.pinches
    stated = _stated(plan)
    assert stated == used, f"LOT_COVER_PINCH states {stated} m; the check measured against {used} m"
    assert all(g < stated for _n, _w, g in plan.pinches)
    assert plan.passable_gap == used


def test_under_the_contracts_bake_the_message_states_the_contracts_gap():
    """As `lot.py` calls it. 0.120.1 stated 1.2 m above a check made at 1.0 m."""
    bake = _live()["nav_bake"]
    plan = _plan(0.5, bake)
    assert [g for _n, _w, g in plan.pinches] == [0.5], plan.pinches
    assert _stated(plan) == site_cover.min_passable_gap(bake) == 1.0


def test_a_plan_that_does_not_carry_its_threshold_is_refused():
    """Only `plan_cover` makes a `CoverPlan`, and it sets both. One made any other way has pinches and
    no measurement to state, and stating the fallback's number for it is the defect this file is about."""
    plan = site_cover.CoverPlan(pinches=[("Cover_0", "a building", 0.5)])
    with pytest.raises(ValueError):
        site_cover.findings(plan, opening_range=45.0)
