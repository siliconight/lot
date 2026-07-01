"""
site_pacing.py  --  pacing estimate + structural encounter intel for Lot
========================================================================
Two offline, structural analyses over the declared site. Neither predicts
"fun" — fun is a feel property that only a playthrough reveals. These describe
STRUCTURE: how long the declared route takes, and where the geometry creates
combat opportunity. Every number is an estimate from declared inputs, shown with
its breakdown, never a verdict.

WHAT THIS IS NOT: not a simulation, not an AI, not a fun-score. It does not move
agents, fire weapons, or decide whether an encounter is good. It does arithmetic
over the connectivity graph, path lengths, and declared/derived timings, and it
reports geometric facts about routes (approach count, exposure). The in-engine
walk remains the only thing that tells you if it's actually fun.

WHY pacing is honestly computable (and fun isn't): duration is a function of
distances + objective timings + mode structure — all declared or derived. "How
many minutes" is arithmetic. "How tense" is not.

------------------------------------------------------------------------------
PACING

Estimates time-to-complete for the mode's critical route, as a min/expected/max
range (routes and player skill vary). Compared against a target window
(default 7-15 min). Defaults are derived from the mode + distances and can be
overridden per-spec under "pacing": { ... }.

  assault   : traverse spawn -> objective, + assault resolution time
  heist     : traverse spawn -> objective (+ dwell to do the objective)
                          -> extraction
  survival  : reach holdout, + holdout duration (waves x wave length)

DEFAULTS (override in spec["pacing"]):
  move_speed       4.0  m/s   (jogging player, conservative)
  objective_secs   120        per objective marker (drill/hack/search)
  loot_trip_secs   25         per loot marker (grab + carry one way)
  wave_secs        35         survival: seconds per wave
  waves            6          survival: number of waves
  setup_secs       30         pre-objective approach/positioning
  skill_spread     0.35       +/- fraction for the min/max band

------------------------------------------------------------------------------
ENCOUNTER INTEL (structural, NOT a quality score)

For each leg of the critical route, reports geometric facts:
  - approaches : how many distinct path-routes reach the destination building
                 (more = more tactical choice; a fact, not a grade)
  - length_m   : leg distance
  - exposure   : leg length crossing OUTSIDE any building footprint / cover,
                 as a rough "how much open ground" figure (longer open crossing
                 = more exposed; again a fact about geometry, not "bad")
  - cover_near : count of declared cover pieces within a band of the leg

These are opportunities the geometry creates. Whether they make a good firefight
is for the walk to tell you.
"""

import math


DEFAULTS = {
    "move_speed": 4.0,
    "objective_secs": 120,
    "loot_trip_secs": 25,
    "wave_secs": 35,
    "waves": 6,
    "setup_secs": 30,
    "skill_spread": 0.35,
}
TARGET_MIN_S = 7 * 60
TARGET_MAX_S = 15 * 60


def _cfg(site_spec):
    c = dict(DEFAULTS)
    c.update(site_spec.get("pacing", {}))
    # allow target override
    t = site_spec.get("pacing", {}).get("target_minutes")
    lo, hi = TARGET_MIN_S, TARGET_MAX_S
    if isinstance(t, (list, tuple)) and len(t) == 2:
        lo, hi = t[0] * 60, t[1] * 60
    c["_target"] = (lo, hi)
    return c


def _pos(site_spec, bid):
    for b in site_spec.get("buildings", []):
        if b["id"] == bid:
            return b["at"]
    return None


def _dist(site_spec, a, b):
    pa, pb = _pos(site_spec, a), _pos(site_spec, b)
    if pa and pb:
        return math.hypot(pb[0] - pa[0], pb[1] - pa[1])
    return 0.0


def _markers_in_building(merged, bid):
    return [m for m in merged.get("markers", []) if m.get("building") == bid]


def _count_type(merged, bid, typ):
    return sum(1 for m in _markers_in_building(merged, bid)
               if m.get("type") == typ or typ in m.get("type", ""))


def _critical_legs(site_spec):
    """Ordered list of (from, to) building legs for the mode's critical route."""
    mode = site_spec.get("mode")
    spawn = site_spec.get("spawn")
    obj = site_spec.get("objective")
    extr = site_spec.get("extraction")
    safe = site_spec.get("safe")
    legs = []
    if mode == "heist" and spawn and obj and extr:
        legs = [(spawn, obj), (obj, extr)]
    elif mode == "assault" and spawn and obj:
        legs = [(spawn, obj)]
    elif mode == "survival" and safe and obj:
        legs = [(safe, obj)]
    return legs


def estimate_pacing(site_spec, merged):
    """Return a pacing estimate (dict). Pure arithmetic; never raises."""
    c = _cfg(site_spec)
    mode = site_spec.get("mode")
    legs = _critical_legs(site_spec)

    breakdown = []
    base = 0.0

    # traversal along the critical route. Site-level crew_spawn / extraction
    # markers (where the crew actually stages / leaves — a site concern, see
    # lot._walk_positions) refine the route endpoints; the building ids stay
    # the fallback, so sites without the markers estimate exactly as before.
    def _site_marker_at(typ):
        for sm in site_spec.get("site_markers", []):
            if sm.get("type") == typ and sm.get("at"):
                return (sm["at"][0], sm["at"][1], typ)
        return None

    travel = 0.0
    if legs:
        ids = [legs[0][0]] + [b for _, b in legs]
        pts = []
        for i in ids:
            p = _pos(site_spec, i)
            pts.append((p[0], p[1], i) if p else (0.0, 0.0, i))
        sp = _site_marker_at("crew_spawn")
        if sp:
            pts[0] = sp
        ep = _site_marker_at("extraction")
        if ep and mode == "heist":
            pts[-1] = ep
        for (ax, ay, la), (bx, by, lb) in zip(pts, pts[1:]):
            d = math.hypot(bx - ax, by - ay)
            secs = d / c["move_speed"]
            travel += secs
            breakdown.append({"phase": f"travel {la}->{lb}",
                              "secs": round(secs, 1), "detail": f"{d:.1f} m"})
    base += travel

    # setup
    base += c["setup_secs"]
    breakdown.append({"phase": "setup/positioning", "secs": c["setup_secs"]})

    # objective interaction (count objective markers in the objective building)
    obj = site_spec.get("objective")
    if obj:
        n_obj = max(1, _count_type(merged, obj, "objective"))
        osecs = n_obj * c["objective_secs"]
        base += osecs
        breakdown.append({"phase": "objective work",
                          "secs": osecs,
                          "detail": f"{n_obj} objective(s) x {c['objective_secs']}s"})
        n_loot = _count_type(merged, obj, "loot")
        if n_loot:
            lsecs = n_loot * c["loot_trip_secs"]
            base += lsecs
            breakdown.append({"phase": "loot trips", "secs": lsecs,
                              "detail": f"{n_loot} loot x {c['loot_trip_secs']}s"})

    # mode extras
    if mode == "survival":
        hsecs = c["waves"] * c["wave_secs"]
        base += hsecs
        breakdown.append({"phase": "holdout",
                          "secs": hsecs,
                          "detail": f"{c['waves']} waves x {c['wave_secs']}s"})

    spread = c["skill_spread"]
    lo, hi = base * (1 - spread), base * (1 + spread)
    tlo, thi = c["_target"]

    status = "within target"
    if hi < tlo:
        status = "likely TOO SHORT vs target"
    elif lo > thi:
        status = "likely TOO LONG vs target"
    elif lo < tlo or hi > thi:
        status = "partly outside target (range straddles the window)"

    return {
        "mode": mode,
        "estimate_min_s": round(lo),
        "estimate_expected_s": round(base),
        "estimate_max_s": round(hi),
        "estimate_expected_min": round(base / 60, 1),
        "range_min": f"{lo/60:.1f}-{hi/60:.1f} min",
        "target_min": f"{tlo/60:.0f}-{thi/60:.0f} min",
        "status": status,
        "breakdown": breakdown,
        "note": ("estimate from declared structure + derived timings; "
                 "not a measure of fun. Walk it to feel the pacing."),
    }


# ---------------------------------------------------------------------------
# structural encounter intel (facts about geometry, NOT a quality score)
# ---------------------------------------------------------------------------
def _distinct_approaches(adj, target, start):
    """Reuse the connectivity idea: count target's neighbours reachable from
    start without passing through target."""
    if target not in adj:
        return 0
    n = 0
    for nb in adj[target]:
        sub = {k: (v - {target}) for k, v in adj.items()}
        if nb == start:
            n += 1
        else:
            seen, stack = {start}, [start]
            while stack:
                cur = stack.pop()
                for x in sub.get(cur, ()):
                    if x not in seen:
                        seen.add(x)
                        stack.append(x)
            if nb in seen:
                n += 1
    return n


def _leg_exposure(site_spec, a, b):
    """Rough 'open ground' on a leg: the straight-line distance minus any span
    that lies within a building footprint (we don't have footprints precisely,
    so we approximate building cover as a radius around each building origin).
    A fact about how much open crossing the route has, not a judgment."""
    pa, pb = _pos(site_spec, a), _pos(site_spec, b)
    if not pa or not pb:
        return 0.0
    total = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
    # subtract a nominal covered radius at each end (near-building cover)
    covered = min(total, 12.0)  # ~6 m of near-cover at each end, capped
    return round(max(0.0, total - covered), 1)


def _cover_near_leg(site_spec, a, b, band=10.0):
    """Count declared cover pieces within `band` metres of the leg segment."""
    pa, pb = _pos(site_spec, a), _pos(site_spec, b)
    if not pa or not pb:
        return 0
    ax, ay = pa
    bx, by = pb
    seg = math.hypot(bx - ax, by - ay) or 1.0
    n = 0
    for cov in site_spec.get("cover", []):
        cx, cy = cov["at"]
        # distance from point to segment
        t = max(0.0, min(1.0, ((cx - ax) * (bx - ax) + (cy - ay) * (by - ay)) / seg ** 2))
        px, py = ax + t * (bx - ax), ay + t * (by - ay)
        if math.hypot(cx - px, cy - py) <= band:
            n += 1
    return n


def encounter_intel(site_spec, adj):
    """Per-leg structural facts about combat OPPORTUNITY. Not a quality score."""
    legs = _critical_legs(site_spec)
    start = site_spec.get("spawn") or site_spec.get("safe")
    out = []
    for a, b in legs:
        out.append({
            "leg": f"{a}->{b}",
            "length_m": round(_dist(site_spec, a, b), 1),
            "approaches": _distinct_approaches(adj, b, start) if start else None,
            "open_ground_m": _leg_exposure(site_spec, a, b),
            "cover_near": _cover_near_leg(site_spec, a, b),
        })
    return {
        "legs": out,
        "note": ("geometric facts about each route leg (route choice, open "
                 "ground, nearby cover). Describes opportunity, not quality — "
                 "whether it plays well is for the walk to tell you."),
    }
