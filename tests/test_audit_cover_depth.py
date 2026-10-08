"""0.98.2 -- the audit measures cover by its depth, not its height (roadmap 211).

`site_audit._cover_rects` read a cover record's `size` as [plan x, plan y,
...]. Every planner writes [plan x, height, plan y] -- `lot.py` stands each
piece's box at half the middle number -- so every rect the audit measured had
its height for a depth. One check reads the extent: `S_NAKED_ANCHOR`, the
distance from the crew's spawn and extraction to the nearest cover or building
edge. (`S_BARE_LEG` reads a rect's centre, which the error does not move.)

The sites here are built so the two readings must disagree, and their
instrument is their own: the expected verdicts follow from the piece's
dimensions and `ANCHOR_RADIUS`, asserted beside each case, not from
`_cover_rects`.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import site_audit     # noqa: E402


def _site(piece, anchor):
    """One cover piece and the crew's spawn-and-extraction point, nothing
    else on the site, the objective far off."""
    return {"name": "cover_depth_probe", "mode": "heist", "buildings": [], "cover": [piece],
            "site_markers": [{"type": "crew_spawn", "at": list(anchor)},
                             {"type": "extraction", "at": list(anchor)},
                             {"type": "objective", "at": [60.0, 60.0]}]}


def _naked(site):
    return [f for f in site_audit.audit(site)["findings"] if f[1] == "S_NAKED_ANCHOR"]


def test_a_parked_car_is_its_own_length_deep():
    """A 4.7 m car at yaw 0, the anchor 10 m off its centre along its length:
    7.65 m from its end, inside `ANCHOR_RADIUS`. Read by its 1.73 m height it
    stood 9.135 m away, and the anchor was called naked."""
    car = {"at": [0.0, 0.0], "size": [1.8, 1.73, 4.7], "yaw": 0.0}
    assert 10.0 - 4.7 / 2 < site_audit.ANCHOR_RADIUS < 10.0 - 1.73 / 2
    assert _naked(_site(car, (0.0, 10.0))) == []


def test_a_streetlight_is_not_six_metres_deep():
    """A pole 0.7 m deep and 6.0 m tall, the anchor 10.5 m off its centre:
    10.15 m from its face, outside `ANCHOR_RADIUS`. Read by its height it
    stood 7.5 m away and passed as a backstop it is not."""
    pole = {"at": [0.0, 0.0], "size": [0.3, 6.0, 0.7], "yaw": 90.0}
    assert 10.5 - 6.0 / 2 < site_audit.ANCHOR_RADIUS < 10.5 - 0.7 / 2
    assert len(_naked(_site(pole, (0.0, 10.5)))) == 1


def test_the_middle_number_is_the_height():
    """Read the way `lot.py` stands the box: x by the first number, plan y by
    the third."""
    (rect,) = site_audit._cover_rects({"cover": [{"at": [0.0, 0.0], "size": [1.8, 1.73, 4.7]}]})
    assert rect == (-0.9, -2.35, 0.9, 2.35)
