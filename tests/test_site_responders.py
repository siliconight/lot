"""0.99.0 -- where responders arrive, and the room they need to (roadmap 212).

The walker, 2026-10-08: "have responders show up after the job, on the way
back (and this would be on the gameplay layer, but we can make thee assets
and ensure there is clearance and routes for their arrival)". Lot does not
spawn them. For each open road end it finds a lane a cruiser drives in by and
a stop it fits with its doors open, keeps every later planner out of both,
and writes each as a `responder_spawn` site marker -- which the audit judges
and the nav QA walks.

Two sites:
- the kerb probe, assembled end to end -- one road with both ends open, and
  the getaway van on its north kerb;
- cold run 9198's seed_9256 as Lot drew it, with its cover cut back to the
  van, which is what stood when the arrivals were planned.

THE INSTRUMENTS ARE THE TESTS' OWN. A stop is read from its marker, the
lane's half from the road's own frame, and a piece's slot from its record's
`size` ([plan x, height, plan y]). The two controls at the end show the
reservation doing something: a car 9198 parked in a stop, parked again
without it and kept out with it; and a cover piece refused a kept-out spot
without the spot hiding anything.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lot              # noqa: E402
import site_audit       # noqa: E402
import site_parking     # noqa: E402
import site_responders  # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(HERE), "specs")
PROBE = os.path.join(SPECS, "coldrun_kerb_probe.json")
FIXTURE = os.path.join(HERE, "fixtures", "bank_block_001_seed_9256.site.json")
#: seed_9256's van door (the crew's spawn and extraction) and its objective,
#: as cold run 9198's scene wrote them (site frame).
SPAWN = (18.812, -1.8, 0.0)
OBJECTIVE = (-46.0, 9.25, -3.9)


def _slot(cv):
    sx, _h, sy = cv["size"]
    x, y = cv["at"][:2]
    return (x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0)


def _overlaps(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _assembled(tmp_path):
    lot.assemble(PROBE, str(tmp_path))
    drawn = json.loads((tmp_path / "coldrun_kerb_probe.site.drawn.json").read_text(encoding="utf-8"))
    gameplay = json.loads((tmp_path / "coldrun_kerb_probe.site.gameplay.json").read_text(encoding="utf-8"))
    return drawn, gameplay


def _arrivals(markers):
    return [m for m in markers or []
            if m.get("type") == "responder_spawn" and m.get("source") == "responder_arrival"]


def _in_the_way(drawn):
    return [(cv.get("species") or cv.get("source"), part)
            for m in _arrivals(drawn["site_markers"]) for part in ("stop_box", "lane_box")
            for cv in drawn["cover"] if cv.get("size") and _overlaps(_slot(cv), m["arrival"][part])]


def test_the_probe_gets_an_arrival_at_each_open_end(tmp_path):
    """One road, both ends open: two arrivals, one from each end, each
    driving in on the half a keep-right driver keeps to, in a driving lane."""
    drawn, gameplay = _assembled(tmp_path)
    arrivals = _arrivals(drawn["site_markers"])
    assert len(arrivals) == 2, arrivals
    (road,) = site_streets.roads(drawn)
    assert sorted(m["arrival"]["travel"] for m in arrivals) == [-1, 1]
    for m in arrivals:
        travel = m["arrival"]["travel"]
        end = road.a if travel > 0 else road.b
        assert math.dist(m["arrival"]["entry"], end) < road.width / 2.0
        off = ((m["at"][0] - road.a[0]) * road.perp[0] + (m["at"][1] - road.a[1]) * road.perp[1])
        assert off * travel < 0, (travel, off)                         # keep right
        assert abs(off) < road.width / 2.0 - site_streets.LANE_DEPTH   # not the parking lane
    # the nav QA reads the gameplay file's site markers, so the route is walked
    assert len(_arrivals(gameplay["site_markers"])) == 2


def test_nothing_stands_in_a_lane_or_a_stop(tmp_path):
    """Every piece every planner stood -- the van, the parked cars, the
    furniture, the fences, the cover -- clear of every arrival's stop and
    lane, and the read-back says so."""
    drawn, gameplay = _assembled(tmp_path)
    assert _arrivals(drawn["site_markers"])
    assert not _in_the_way(drawn)
    assert not [f for f in gameplay["responder_plan"]["findings"]
                if f["code"] == "LOT_RESPONDER_BLOCKED"]


def test_no_stop_camps_the_van(tmp_path):
    """Every stop at least the audit's `CAMP_RADIUS` from the crew's spawn and
    extraction -- the van's door -- and the audit agrees."""
    drawn, _gameplay = _assembled(tmp_path)
    crew = next(m["at"] for m in drawn["site_markers"] if m.get("type") == "crew_spawn")
    for m in _arrivals(drawn["site_markers"]):
        assert math.dist(m["at"], crew) >= site_audit.CAMP_RADIUS
    codes = [f[1] for f in site_audit.audit(drawn)["findings"]]
    assert "S_RESPONDER_CAMP" not in codes and "S_NO_RESPONDERS" not in codes


def test_a_t_is_not_an_entry():
    """On 9198's seed_9256, road 1 ends on road 0: three open ends, not four."""
    spec = json.load(open(FIXTURE, encoding="utf-8"))
    ends = sorted((r.index, round(t, 3), tr)
                  for r, t, tr in site_responders.entries(site_streets.roads(spec)))
    assert ends == [(0, 0.0, 1), (0, 187.0, -1), (1, 56.65, -1)]


def test_the_bank_site_arrivals_keep_clear_of_each_other():
    """seed_9256 with only the van standing: three arrivals, none in another's
    stop or lane, none in the van, none camping it."""
    spec = json.load(open(FIXTURE, encoding="utf-8"))
    spec["cover"] = [cv for cv in spec["cover"] if cv.get("source") == "getaway_van"]
    arrivals = site_responders.plan(spec, {"spawn": SPAWN, "extraction": SPAWN,
                                           "objective": OBJECTIVE})
    assert len(arrivals) == 3
    van = _slot(spec["cover"][0])
    for i, a in enumerate(arrivals):
        assert not _overlaps(a["stop_box"], van) and not _overlaps(a["lane_box"], van)
        assert math.dist(a["stop"], SPAWN[:2]) >= site_audit.CAMP_RADIUS
        for b in arrivals[i + 1:]:
            assert not _overlaps(a["stop_box"], b["stop_box"])
            assert not _overlaps(a["stop_box"], b["lane_box"])
            assert not _overlaps(b["stop_box"], a["lane_box"])


def test_one_test_for_a_road_end():
    """`_ends_on`, `_slab` and the arrivals ask one function whether a road's
    end lies on another road (read as source): three spellings of one test
    are three places for it to drift."""
    src = open(os.path.join(os.path.dirname(HERE), "site_streets.py"), encoding="utf-8").read()
    assert src.count("abs(across) <= 1.0 and -1.0 <= along <= other.length + 1.0") == 1
    assert "abs(across) > 1.0 or along < -1.0" not in src


def test_without_the_reservation_a_car_parks_in_a_stop():
    """The control, on real ground. On the probe nothing lands in a lane or a
    stop even unreserved -- its stops sit where the way back crosses the
    road, which keeps its bays empty anyway -- so the probe alone cannot
    show the reservation doing anything.

    Cold run 9198 planned seed_9256 with no reservation and parked a car in
    bay L6 on road 1, at (21.112, 14.85): in what is now arrival 0's stop.
    `plan_parking` parks there again given no reservation, and given the
    reservation keeps every car out of every stop and lane -- and the
    read-back names 9198's car."""
    full = json.load(open(FIXTURE, encoding="utf-8"))
    spec = dict(full, cover=[cv for cv in full["cover"] if cv.get("source") == "getaway_van"])
    arrivals = site_responders.plan(spec, {"spawn": SPAWN, "extraction": SPAWN,
                                           "objective": OBJECTIVE})
    shipped = site_responders.blocked(arrivals, full["cover"])
    assert len(shipped) == 1 and "(21.1, 14.8)" in shipped[0]["message"], shipped
    roads, van = site_streets.roads(spec), [_slot(spec["cover"][0])]

    def parked_in(keep):
        cars = site_parking.plan_parking(roads, van + list(keep), [SPAWN[:2], OBJECTIVE[:2]])
        return [tuple(cv["at"]) for cv in cars
                if any(_overlaps(_slot(cv), a[part])
                       for a in arrivals for part in ("stop_box", "lane_box"))]

    assert parked_in([]) == [(21.112, 14.85)]
    assert parked_in(site_responders.keep_out(arrivals)) == []


def test_cover_keeps_out_of_a_lane_and_the_lane_hides_nobody():
    """`plan_cover(keep_out=)`. On open ground a 60 m line from the crew to an
    enemy gets one piece. Keep that piece's spot out and the piece stands
    elsewhere on the line, which is still broken: the kept-out rect refused
    it and hid nothing. Had it been measured as an occluder, the line would
    have read as broken already and no piece would stand at all."""
    import site_cover
    points = {"LT_PlayerSpawn": (0.0, 0.0), "Enemy_0": (60.0, 0.0)}
    ground = (-10.0, -20.0, 70.0, 20.0)
    free = site_cover.plan_cover(points, [], ground, opening_range=45.0)
    assert len(free.cover) == 1 and not free.open_lines
    lane = tuple(free.cover[0].rect)
    kept = site_cover.plan_cover(points, [], ground, opening_range=45.0, keep_out=[lane])
    assert kept.cover and not kept.open_lines
    assert not any(_overlaps(piece.rect, lane) for piece in kept.cover)
