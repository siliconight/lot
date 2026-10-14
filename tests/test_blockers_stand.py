"""The planners that keep clear of what already stands keep clear of the blockers too (Lot 0.121.0, factory
roadmap 241).

Parking fields and the cars in them, the forecourt pylons and the dumpsters, the dumpsters' pads and bags, and the
cover planner each take a `standing` list -- the plan rects of what already stands -- and each was handed the
cover pieces placed so far and nothing else. The blockers (Level Factory's Empties) were left out. That was
harmless while every Empty stood across the road, where none of these places anything. The urban street's near
side stands Empties in the gaps beside the mission's buildings, which is where fields, dumpsters, pads and cover
go, so each list now starts with every blocker's rect (`site_spawns.blocker_rects`, as built).

This spies on the four planners during a real `assemble` of the example compound with two Empties added, and
asks that every call's `standing` holds both. On 0.120.2 none does.
"""
import contextlib
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lot             # noqa: E402
import site_cover      # noqa: E402
import site_dumpsters  # noqa: E402
import site_extent     # noqa: E402
import site_fields     # noqa: E402
import site_yards      # noqa: E402

SPECS = os.path.join(os.path.dirname(HERE), "specs")
#: Two Empties on the example's plate (120 x 80 about the origin), clear of its bank and warehouse.
BLOCKERS = [{"id": "e0", "archetype": "gs_midrise_a", "at": [-45.0, -28.0], "rot": 0,
             "size_x": 12.0, "size_y": 10.0, "empty": True},
            {"id": "e1", "archetype": "gs_midrise_b", "at": [-45.0, 28.0], "rot": 180,
             "size_x": 12.0, "size_y": 10.0, "empty": True}]
PLANNERS = ((site_fields, "plan_fields"), (site_dumpsters, "plan_dumpsters"),
            (site_yards, "plan_yards"), (site_cover, "plan_cover"))


def test_every_planner_that_keeps_clear_is_handed_the_blockers(monkeypatch, tmp_path):
    spec = json.load(open(os.path.join(SPECS, "example_compound.json"), encoding="utf-8"))
    spec["blockers"] = copy.deepcopy(BLOCKERS)
    path = tmp_path / "example_with_empties.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    seen = {}
    for mod, name in PLANNERS:
        def spy(*a, _real=getattr(mod, name), _name=name, **k):
            seen.setdefault(_name, []).append([tuple(r) for r in (k.get("standing") or [])])
            return _real(*a, **k)
        monkeypatch.setattr(mod, name, spy)
    with contextlib.redirect_stdout(io.StringIO()):
        lot.assemble(str(path), str(tmp_path / "out"))
    want = [tuple(site_extent.blocker_rect(b)) for b in BLOCKERS]
    assert sorted(seen) == sorted(name for _m, name in PLANNERS), sorted(seen)
    for name, calls in seen.items():
        for standing in calls:
            missing = [r for r in want if r not in standing]
            assert not missing, (name, missing)


def test_a_site_with_no_blockers_hands_the_planners_what_it_did():
    """No blocker, nothing added: the lists are the cover pieces they always were."""
    import site_spawns
    assert site_spawns.blocker_rects({"blockers": []}, margin=0.0) == []
