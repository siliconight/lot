"""0.99.0 -- where responders arrive, and the room they need to (roadmap 212).

The walker, 2026-10-08: "have responders show up after the job, on the way
back (and this would be on the gameplay layer, but we can make thee assets
and ensure there is clearance and routes for their arrival)". Lot does not
spawn them. For each open road end it finds a lane a cruiser drives in by and
a stop it fits with its doors open, keeps every later planner out of both,
and writes each as a `responder_spawn` site marker -- which the audit judges
and the nav QA walks.

Three sites:
- the kerb probe, assembled end to end -- one road with both ends open, and
  the getaway van on its north kerb;
- cold run 9198's seed_9256 as Lot drew it, with its cover cut back to the
  van, which is what stood when the arrivals were planned;
- cold run 9204's club_block_014 seed_9181, the same way: the input site and
  the cover as drawn (0.100.0). Its getaway van stood 0.45 m into road 0's
  eastern lane and closed it; the lane steers round it now.

THE INSTRUMENTS ARE THE TESTS' OWN. A stop is read from its marker, the
lane's half from the road's own frame, and a piece's slot from its record's
`size` ([plan x, height, plan y]). The two controls at the end show the
reservation doing something: a car 9204 parked in what is now a stop,
parked again without it and kept out with it; and a cover piece refused a
kept-out spot without the spot hiding anything.
"""
import json
import math
import os
import sys

import pytest

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
#: Cold run 9204's seed_9181: the input site with the cover as drawn, and the
#: crew's points from the job's `site_walk.tscn` (Godot turned to site).
FIXTURE_9204 = os.path.join(HERE, "fixtures", "club_block_014_seed_9181.site.json")
SPAWN_9204 = (73.85, -17.95, 0.0)
OBJECTIVE_9204 = (-50.0, 5.0, 0.0)
#: Cold run 9206's seed_9080: the input site and the getaway van as placed,
#: and the crew's points from the job's `site_walk.tscn` (0.100.1).
FIXTURE_9080 = os.path.join(HERE, "fixtures", "club_block_014_seed_9080.site.json")
SPAWN_9080 = (-10.65, -24.37, 0.0)
OBJECTIVE_9080 = (-47.0, -9.42, -3.3)
#: Zoo, where the factory keeps it beside this repo.
ZOO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "zoo")


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


def _boxes(a):
    """An arrival's reserved ground: (part, rect) for its stop and every box
    of its lane."""
    return [("stop", a["stop_box"])] + [("lane", box) for box in a["lane_boxes"]]


def _in_the_way(drawn):
    return [(cv.get("species") or cv.get("source"), part)
            for m in _arrivals(drawn["site_markers"]) for part, box in _boxes(m["arrival"])
            for cv in drawn["cover"] if cv.get("size") and _overlaps(_slot(cv), box)]


def _plan_9204():
    full = json.load(open(FIXTURE_9204, encoding="utf-8"))
    spec = dict(full, cover=[cv for cv in full["cover"] if cv.get("source") == "getaway_van"])
    findings = []
    arrivals = site_responders.plan(spec, {"spawn": SPAWN_9204, "extraction": SPAWN_9204,
                                           "objective": OBJECTIVE_9204}, findings)
    return full, spec, arrivals, findings


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
        assert not any(_overlaps(box, van) for _part, box in _boxes(a))
        assert math.dist(a["stop"], SPAWN[:2]) >= site_audit.CAMP_RADIUS
        for b in arrivals[i + 1:]:
            assert not _overlaps(a["stop_box"], b["stop_box"])
            assert not any(_overlaps(a["stop_box"], box) for box in b["lane_boxes"])
            assert not any(_overlaps(b["stop_box"], box) for box in a["lane_boxes"])


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

    Cold run 9204 planned seed_9181 before the lane could steer: road 0's
    east end had no arrival, and `plan_parking` parked a car at (66.5,
    -20.25) -- in what is now arrival 1's stop, where the steered lane comes
    back into its half. `plan_parking` parks there again given no
    reservation, and given the reservation keeps every car out of every
    stop and lane -- and the read-back names 9204's car.

    *Through 0.99.1* this was cold run 9198's car at (21.112, 14.85) on
    seed_9256, in arrival 0's stop. The cruiser's 5.545 m length and its
    station grid moved that stop 0.36 m, and the car's slot now misses it by
    about 4 cm: an instance lost, not a reservation that stopped working."""
    full, spec, arrivals, _findings = _plan_9204()
    shipped = site_responders.blocked(arrivals, full["cover"])
    assert len(shipped) == 1 and "(66.5, -20.2)" in shipped[0]["message"], shipped
    assert "arrival 1's stop" in shipped[0]["message"]
    roads, van = site_streets.roads(spec), [_slot(spec["cover"][0])]

    def parked_in(keep):
        cars = site_parking.plan_parking(roads, van + list(keep), [SPAWN_9204[:2], OBJECTIVE_9204[:2]])
        return [tuple(cv["at"]) for cv in cars
                if any(_overlaps(_slot(cv), box) for a in arrivals for _part, box in _boxes(a))]

    assert parked_in([]) == [(66.5, -20.25)]
    assert parked_in(site_responders.keep_out(arrivals)) == []


# --------------------------------------------------------------------------- #
# 0.100.0: the cruiser's size, and a lane that steers
# --------------------------------------------------------------------------- #

def test_the_lane_steers_round_the_van_on_9204():
    """Cold run 9204's seed_9181, as its assemble planned it: three arrivals
    where 0.99.1 found two and `LOT_RESPONDER_ENTRY_NO_STOP` for road 0's
    east end. That end's lane moves toward the centre line by exactly what
    the van's slot needs, tapered, clears the van, and is back in its own
    half by the stop."""
    _full, spec, arrivals, findings = _plan_9204()
    assert [f["code"] for f in findings] == []
    assert len(arrivals) == 3
    (road0,) = [r for r in site_streets.roads(spec) if r.index == 0]
    east = [a for a in arrivals if a["road"] == 0 and a["travel"] == -1]
    assert len(east) == 1, arrivals
    a = east[0]
    van = _slot(spec["cover"][0])
    w = site_responders.VEHICLE[1] + 2.0 * site_responders.LANE_MARGIN
    off = site_responders.lane_offset(road0, -1)

    def across(rect):
        vals = [(x - road0.a[0]) * road0.perp[0] + (y - road0.a[1]) * road0.perp[1]
                for x in (rect[0], rect[2]) for y in (rect[1], rect[3])]
        return min(vals), max(vals)

    # the van's edge nearest the centre line, and the shift that clears it
    # by the record's precision (0.100.1)
    v0, v1 = across(van)
    near = v0 if off > 0 else v1
    need = abs(off) + w / 2.0 - abs(near)
    assert a["lane_shift"] == pytest.approx(need + site_responders.RECORD_PRECISION, abs=1e-6)
    assert 0.6 < need < 0.7                        # 0.648 m: 0.45 + the mirror and margin growth
    boxes = a["lane_boxes"]
    assert not any(_overlaps(box, van) for box in boxes)
    # tapered: neighbouring boxes' centres step by no more than the rate allows
    centres = [sum(across(b)) / 2.0 for b in boxes]
    shifts = [abs(off) - abs(c) for c in centres]
    for s0, s1 in zip(shifts, shifts[1:]):
        assert abs(s1 - s0) <= site_responders.SHIFT_RATE * site_responders.STATION_STEP + 1e-6
    # back in its own half by the stop; every box on the carriageway
    assert shifts[-1] == pytest.approx(0.0, abs=1e-9)
    limit = site_responders.shift_limit(road0, off, w)
    assert max(shifts) <= limit


def test_what_the_planner_keeps_the_read_back_finds_clear():
    """Cold run 9206's seed_9080: a lane steered round the getaway van. 0.100.0
    cleared the van by 1e-6 m and rounded the record's box onto the van's
    edge, and `blocked` reported the van in the lane -- LOT_RESPONDER_BLOCKED,
    major -- by 3.6e-15 m. The planner now checks the boxes it records, and
    a steered lane clears what it passes by the record's precision."""
    spec = json.load(open(FIXTURE_9080, encoding="utf-8"))
    findings = []
    arrivals = site_responders.plan(spec, {"spawn": SPAWN_9080, "extraction": SPAWN_9080,
                                           "objective": OBJECTIVE_9080}, findings)
    assert len(arrivals) == 3 and findings == []
    assert site_responders.blocked(arrivals, spec["cover"]) == []
    steered = [a for a in arrivals if a["lane_shift"] > 0]
    assert len(steered) == 1
    van = _slot(spec["cover"][0])
    for box in steered[0]["lane_boxes"]:
        if box[0] < van[2] and van[0] < box[2]:       # beside the van along the road
            gap = max(van[1] - box[3], box[1] - van[3])
            assert gap >= site_responders.RECORD_PRECISION / 2.0, (box, van, gap)
    # every box in a record is already at the record's precision
    for a in arrivals:
        for _part, box in _boxes(a):
            assert list(site_responders._recorded(box)) == list(box)


def test_a_shift_ramps_up_before_and_down_after():
    """`steer`: a 0.6 m need at slices 4-5 of twelve, 1 m slices, at the
    MUTCD rate for 25 mph (0.192 across per metre along)."""
    rate = site_responders.SHIFT_RATE
    assert rate == pytest.approx(120.0 / 25.0 ** 2)
    need = [0.0] * 4 + [0.6, 0.6] + [0.0] * 6
    s = site_responders.steer(need, rate, [1.0] * 12)
    assert s[4] == s[5] == 0.6
    assert s[3] == pytest.approx(0.6 - rate) and s[6] == pytest.approx(0.6 - rate)
    assert s[0] == 0.0 and s[-1] == 0.0
    # the same need two slices from the stop cannot get back in time
    assert site_responders.steer([0.0] * 8 + [0.6, 0.6, 0.0, 0.0], rate, [1.0] * 12) is None


def test_a_lane_nothing_can_pass_is_refused():
    """Ground standing across the whole carriageway leaves no shift that
    clears it: the slice needs None, and the entry gets no stop."""
    _full, spec, _arrivals, _findings = _plan_9204()
    (road0,) = [r for r in site_streets.roads(spec) if r.index == 0]
    van = _slot(spec["cover"][0])
    stations = [(x - road0.a[0]) * road0.along[0] + (y - road0.a[1]) * road0.along[1]
                for x in (van[0], van[2]) for y in (van[1], van[3])]
    t = (min(stations) + max(stations)) / 2.0          # the van's station, from the road's frame
    corners = [road0.point(t + dt, side * road0.width) for dt in (-0.5, 0.5) for side in (-1.0, 1.0)]
    wall = (min(c[0] for c in corners), min(c[1] for c in corners),
            max(c[0] for c in corners), max(c[1] for c in corners))
    off = site_responders.lane_offset(road0, -1)
    w = site_responders.VEHICLE[1] + 2.0 * site_responders.LANE_MARGIN
    limit = site_responders.shift_limit(road0, off, w)
    assert site_responders._needs(road0, -1, off, w, [(t + 0.5, t - 0.5)], [wall], limit) == [None]
    # and the van alone, at the same slice, needs the shift that clears it
    assert site_responders._needs(road0, -1, off, w, [(t + 0.5, t - 0.5)], [van], limit)[0] > 0.6


def test_the_vehicle_is_zoos_cruiser():
    """Lot does not import Zoo, so `VEHICLE` and `MIRROR_OUT` are pinned:
    read Zoo's `cruiser` genome and its `car_forms.CRUISER` row when Zoo
    stands beside this repo, and fail when they disagree."""
    genome = os.path.join(ZOO, "zoo_keeper", "genome", "species", "cruiser.json")
    if not os.path.exists(genome):
        pytest.skip("Zoo is not beside this repo")
    dims = json.load(open(genome, encoding="utf-8"))["dimensions"]
    want = tuple(dims[k]["default"] for k in ("width", "depth", "height"))
    assert site_responders.VEHICLE == ("cruiser",) + want
    forms = open(os.path.join(ZOO, "zoo_keeper", "core", "car_forms.py"), encoding="utf-8").read()
    row = forms[forms.index("CRUISER = {"):forms.index("FORMS[\"cruiser\"] = CRUISER")]
    assert '"mirror_out": %r' % site_responders.MIRROR_OUT in row


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
