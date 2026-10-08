"""0.98.1 -- no crew member stands in the getaway van.

Cold run 9198, bank_block_001 seed_9256: Laser Tag refused the map before a
single run -- ``SPAWN_IN_COLLISION: LT_PlayerSpawn_1 is inside world
collision`` -- and graded it BROKEN on 0 runs (LT_NOT_EVALUATED), so one
candidate of three was never evaluated. `crew_spawns` puts the crew's other
members on the first ring points `CREW_SPACING` (2.0 m) clear of the spawn,
and the rings start along +X: the scene carried LT_PlayerSpawn_1 at (20.812,
-1.8), inside the step_van's slot, x 20.062 to 22.662. The crew was kept out
of buildings and blockers (`solid_rects`) and had never been asked about
cover; until 0.98.0 parked the van beside the spawn, no cover stood that
close to one.

The fixture is that candidate's site as Lot drew it: the lot_assemble job's
`site.site.drawn.json`, byte for byte. THE INSTRUMENTS ARE THE TEST'S OWN. A
cover piece's slot is read from the fixture, `size` as [plan x, height, plan
y] -- the way `lot.py` stands the piece's box, at half the middle number --
not through the function this release adds, so on 0.98.0 these fail on where
the crew stands rather than on a missing name. The last test is the one that
asks the new function directly.
"""
import json
import math
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lot             # noqa: E402
import site_spawns     # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "bank_block_001_seed_9256.site.json")

#: The van's door point, the crew's spawn AND its extraction, and the
#: objective, as 9198's scene wrote them (site frame: x, y north, metres).
SPAWN = (18.812, -1.8, 0.0)
OBJECTIVE = (-46.0, 9.25, -3.9)
#: Where 9198 put LT_PlayerSpawn_1.
SHIPPED_MEMBER_1 = (20.812, -1.8)


def _spec():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def _slot(cv):
    """A cover piece's plan rect: ``size`` is [plan x, height, plan y]."""
    sx, _h, sy = cv["size"]
    x, y = cv["at"][:2]
    return (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)


def _gap(p, r):
    """Metres from point ``p`` to rect ``r``; 0.0 inside it."""
    return math.hypot(max(r[0] - p[0], 0.0, p[0] - r[2]),
                      max(r[1] - p[1], 0.0, p[1] - r[3]))


def _van(spec):
    (van,) = [cv for cv in spec["cover"] if cv.get("source") == "getaway_van"]
    return van


def test_the_fixture_is_the_refused_site():
    """Before trusting a fix against it: the fixture's van stands where the
    refused crew member stood, and the crew spawns and leaves at its door."""
    spec = _spec()
    assert spec["crew_size"] == 4
    assert _gap(SHIPPED_MEMBER_1, _slot(_van(spec))) == 0.0
    markers = {m["type"]: tuple(m["at"]) for m in spec["site_markers"]}
    assert markers["crew_spawn"] == markers["extraction"] == SPAWN[:2]


def test_no_crew_member_stands_in_the_van():
    spec = _spec()
    van = _slot(_van(spec))
    crew = site_spawns.crew_spawns(spec, SPAWN, spec["crew_size"])
    assert len(crew) == 4, crew
    for i, member in enumerate(crew[1:], 1):
        assert _gap(member, van) > site_spawns.WALL_MARGIN - 1e-9, (i, member, van)


def test_no_crew_member_stands_in_any_cover():
    """The van is the piece that found it; a parked car, a meter or a
    newspaper box is the same question. Every member but the spawn -- which
    is never moved here -- keeps `WALL_MARGIN` off every piece."""
    spec = _spec()
    crew = site_spawns.crew_spawns(spec, SPAWN, spec["crew_size"])
    for i, member in enumerate(crew[1:], 1):
        near = [(cv.get("species"), round(_gap(member, _slot(cv)), 3))
                for cv in spec["cover"] if cv.get("size")
                and _gap(member, _slot(cv)) <= site_spawns.WALL_MARGIN - 1e-9]
        assert not near, (i, member, near)


def test_the_spawn_is_unmoved_and_the_crew_stays_at_it():
    """THE FIRST IS ALWAYS THE SPAWN; the others still take the nearest free
    ring, a step from it, not the far side of the van.

    One ring past `CREW_SPACING`, not on it: a point exactly that far out can
    be refused by the last bits of its own distance -- 1.9999999999999998 at
    270 deg here, against ``< spacing`` -- so the third member stands on the
    next ring, 2.5 m out. Seen in 0.98.1 and not changed by it."""
    spec = _spec()
    crew = site_spawns.crew_spawns(spec, SPAWN, spec["crew_size"])
    assert crew[0] == SPAWN
    reach = site_spawns.CREW_SPACING + site_spawns.PUSH_STEP
    for i, a in enumerate(crew):
        assert math.dist(a[:2], SPAWN[:2]) <= reach + 1e-9, (i, a)
        for b in crew[i + 1:]:
            assert math.dist(a[:2], b[:2]) >= site_spawns.CREW_SPACING - 1e-9, (a, b)


def test_the_scene_laser_tag_reads_keeps_the_crew_out_of_the_van():
    """What refused the map was a NODE, the walk scene's LT_PlayerSpawn_1,
    so it is read back from `_lasertag_hook_nodes`' own body (Godot frame:
    x, up, -y)."""
    spec = _spec()
    pos = {"spawn": SPAWN, "objective": OBJECTIVE, "extraction": SPAWN}
    body = "\n".join(lot._lasertag_hook_nodes(pos, spec))
    found = re.findall(r'\[node name="(LT_PlayerSpawn(?:_\d+)?)" [^\n]*\]\n'
                       r'transform = Transform3D\(1, 0, 0, 0, 1, 0, 0, 0, 1, '
                       r'([-\d.e]+), [-\d.e]+, ([-\d.e]+)\)', body)
    assert [n for n, _x, _z in found] == [
        "LT_PlayerSpawn", "LT_PlayerSpawn_1", "LT_PlayerSpawn_2", "LT_PlayerSpawn_3"], found
    van = _slot(_van(spec))
    for name, gx, gz in found:
        p = (float(gx), -float(gz))
        assert _gap(p, van) > site_spawns.WALL_MARGIN - 1e-9, (name, p, van)


def test_cover_rects_reads_the_middle_number_as_the_height():
    """`cover_rects` reads ``size`` the way `lot.py` stands the box: [plan x,
    height, plan y]. Read the other way this van would be 3.05 m deep, not
    6.8 -- which is what `site_audit._cover_rects` does (filed, not fixed in
    this release)."""
    (rect,) = site_spawns.cover_rects({"cover": [_van(_spec())]}, margin=0.0)
    assert rect == pytest.approx((20.062, -3.55, 22.662, 3.25))
    (grown,) = site_spawns.cover_rects({"cover": [_van(_spec())]})
    assert grown == pytest.approx((19.062, -4.55, 23.662, 4.25))
