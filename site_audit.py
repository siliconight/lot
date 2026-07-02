#!/usr/bin/env python3
"""
site_audit.py -- the site-level genre grammar (between the buildings)
=====================================================================
Deli Counter's combat_audit rule packs judge the INSIDE of buildings
(PayDay 2 heist grammar, Ready or Not CQB, L4D2 flow). This is the layer
those grammars live on BETWEEN buildings -- the run across open ground:

  EXFIL SHAPE   PayDay: the escape should not rewind the entry. If the
                extraction sits where the crew spawned AND the bearing home
                is the bearing in, the second half of the heist is the
                first half played backwards.
  RESPONDER     PayDay: assault waves should arrive from spread directions.
  PRESSURE      Responders bunched in one arc = every wave is the same
                wave; a responder spawn on top of the exfil = spawn camping
                by construction.
  SAFE ANCHORS  L4D2: the run's endpoints (crew spawn, extraction) want a
                backstop -- cover or a building edge to fight from. A naked
                anchor in open ground is a shooting-gallery start/finish.
  LEG RHYTHM    L4D2: every critical leg (spawn->objective, objective->
                extraction) needs punctuation. A long leg with zero cover
                in its corridor is an open-ground sprint, not a fight.
  STREET CROSS  CQB, site-scale: a road is a long sightline both ways;
                every critical-leg crossing is an exposure moment. Reported
                so the author places cover or accepts the dash.

Report-only, like combat_audit: severities HIGH / MED / INFO, and a walked
site that plays well should sweep clean (gs_heist is the calibration site).

USAGE
    python site_audit.py specs/gs_heist.json [--json]
Also runs automatically at the end of every lot.py assembly.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import site_tactical  # noqa: E402

LEG_COVER_RADIUS = 6.0     # corridor half-width when counting leg cover
LEG_BARE_MIN_LEN = 20.0    # legs shorter than this may be bare
ANCHOR_RADIUS = 8.0        # backstop search radius around spawn/extraction
BACKTRACK_ANGLE = 35.0     # degrees; tighter than this = same bearing
BACKTRACK_NEAR = 18.0      # m; spawn and extraction basically co-located
RESPONDER_ARC = 150.0      # all responders inside this arc = one-note waves
CAMP_RADIUS = 12.0         # responder spawn this close to an anchor = camp


# ---------------------------------------------------------------------------
# resolution helpers
# ---------------------------------------------------------------------------
def _marker_pt(site, typ):
    for m in site.get("site_markers", []):
        if m.get("type") == typ and m.get("at"):
            return tuple(m["at"][:2])
    return None


def _building_pt(site, bid):
    for b in site.get("buildings", []):
        if b.get("id") == bid and b.get("at"):
            return tuple(b["at"][:2])
    return None


def _anchor(site, kind):
    """kind in spawn/objective/extraction -> world point.
    site_markers win; the named building's anchor is the fallback."""
    typ = {"spawn": "crew_spawn", "extraction": "extraction",
           "objective": "objective"}[kind]
    pt = _marker_pt(site, typ)
    if pt:
        return pt
    return _building_pt(site, site.get(kind))


def _cover_rects(site):
    out = []
    for c in site.get("cover", []):
        (x, y), s = c["at"][:2], c.get("size", [1, 1, 1])
        out.append((x - s[0] / 2, y - s[1] / 2, x + s[0] / 2, y + s[1] / 2))
    return out


def _building_rects(site, merged=None):
    """Approximate building footprints. Exact extents live in the built
    gameplay; at spec level a conservative box around the anchor is enough
    for backstop tests."""
    out = []
    for b in site.get("buildings", []):
        if not b.get("at"):
            continue
        x, y = b["at"][:2]
        r = 8.0
        out.append((x - r, y - r, x + r, y + r))
    for bl in site.get("blockers", []):
        if bl.get("at"):
            x, y = bl["at"][:2]
            sx = bl.get("size_x", 12.0) / 2
            sy = bl.get("size_y", 4.0) / 2
            out.append((x - sx, y - sy, x + sx, y + sy))
    return out


def _dist_pt_rect(px, py, r):
    dx = max(r[0] - px, 0, px - r[2])
    dy = max(r[1] - py, 0, py - r[3])
    return math.hypot(dx, dy)


def _dist_pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _bearing(fr, to):
    return math.degrees(math.atan2(to[1] - fr[1], to[0] - fr[0])) % 360.0


def _arc_between(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _seg_crosses_seg(a, b, c, d):
    def cr(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = cr(c, d, a), cr(c, d, b)
    d3, d4 = cr(a, b, c), cr(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


# ---------------------------------------------------------------------------
# the audit
# ---------------------------------------------------------------------------
def audit(site):
    findings = []
    F = findings.append
    name = site.get("name", "site")
    mode = site.get("mode", "heist")

    spawn = _anchor(site, "spawn")
    obj = _anchor(site, "objective")
    extr = _anchor(site, "extraction")
    cover = _cover_rects(site)
    backstops = cover + _building_rects(site)

    legs = []
    if spawn and obj:
        legs.append(("spawn->objective", spawn, obj))
    if obj and extr and mode == "heist":
        legs.append(("objective->extraction", obj, extr))

    # --- exfil shape (PayDay): the escape must not rewind the entry
    if spawn and obj and extr and mode == "heist":
        near = math.hypot(spawn[0] - extr[0], spawn[1] - extr[1])
        ang = _arc_between(_bearing(obj, spawn), _bearing(obj, extr))
        if near < BACKTRACK_NEAR and ang < BACKTRACK_ANGLE:
            F(("MED", "S_BACKTRACK",
               f"extraction sits {near:.0f} m from the crew spawn and "
               f"{ang:.0f} deg off the entry bearing: the exfil rewinds the "
               f"entry -- the second half of the heist is the first half "
               f"backwards. Move the extraction to a different edge or "
               f"corner of the site."))

    # --- responder pressure (PayDay)
    resp = [tuple(m["at"][:2]) for m in site.get("site_markers", [])
            if m.get("type") == "responder_spawn" and m.get("at")]
    if resp and obj and mode == "heist":
        bearings = sorted(_bearing(obj, r) for r in resp)
        if len(bearings) >= 2:
            # widest gap between consecutive bearings; spread = 360 - gap
            gaps = [(bearings[(i + 1) % len(bearings)] - bearings[i]) % 360.0
                    for i in range(len(bearings))]
            spread = 360.0 - max(gaps)
            if spread < (360.0 - RESPONDER_ARC):
                F(("MED", "S_RESPONDER_ARC",
                   f"all {len(resp)} responder spawns arrive from a "
                   f"{spread:.0f} deg arc around the objective: every "
                   f"assault wave is the same wave. Spread spawns so "
                   f"pressure changes direction between waves."))
        for kind, pt in (("crew spawn", spawn), ("extraction", extr)):
            if not pt:
                continue
            for r in resp:
                d = math.hypot(r[0] - pt[0], r[1] - pt[1])
                if d < CAMP_RADIUS:
                    F(("MED", "S_RESPONDER_CAMP",
                       f"a responder spawn sits {d:.0f} m from the {kind}: "
                       f"waves materialize on top of the anchor -- spawn "
                       f"camping by construction. Keep responder spawns "
                       f">= {CAMP_RADIUS:.0f} m from both anchors."))
    if mode == "heist" and not resp:
        F(("INFO", "S_NO_RESPONDERS",
           "no responder_spawn markers: the heist has no escalation "
           "pressure layer at site level."))

    # --- safe anchors (L4D2): endpoints want a backstop
    for kind, pt in (("crew spawn", spawn), ("extraction", extr)):
        if not pt:
            continue
        d = min((_dist_pt_rect(pt[0], pt[1], r) for r in backstops),
                default=1e9)
        if d > ANCHOR_RADIUS:
            F(("MED", "S_NAKED_ANCHOR",
               f"the {kind} at ({pt[0]:.0f}, {pt[1]:.0f}) has no cover or "
               f"building edge within {ANCHOR_RADIUS:.0f} m: a naked anchor "
               f"in open ground -- the hold there is a shooting gallery. "
               f"Give it a backstop (cover cluster, alcove, or wall)."))

    # --- leg rhythm (L4D2): every long leg needs punctuation
    for label, a, b in legs:
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < LEG_BARE_MIN_LEN:
            continue
        n = 0
        for r in cover:
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            if _dist_pt_seg(cx, cy, a[0], a[1], b[0], b[1]) <= LEG_COVER_RADIUS:
                n += 1
        if n == 0:
            F(("MED", "S_BARE_LEG",
               f"the {label} leg is {L:.0f} m with zero cover in its "
               f"{LEG_COVER_RADIUS:.0f} m corridor: an open-ground sprint, "
               f"not a fight. One or two cover pieces along the line give "
               f"the leg a rhythm."))

    # --- street crossings (CQB at site scale): exposure moments, reported
    for label, a, b in legs:
        for rd in site.get("roads", []):
            ra, rb = rd.get("a"), rd.get("b")
            if not (ra and rb):
                continue
            if _seg_crosses_seg(a, b, tuple(ra[:2]), tuple(rb[:2])):
                F(("INFO", "S_STREET_CROSS",
                   f"the {label} leg crosses a road: a long sightline both "
                   f"ways at the crossing -- an exposure moment. Cover near "
                   f"the crossing or accept the dash."))

    # --- horde ingress spread (L4D2), when horde spawns exist
    horde = [tuple(m["at"][:2]) for m in site.get("site_markers", [])
             if m.get("type") == "horde_spawn" and m.get("at")]
    if horde and obj:
        if len(horde) < 3:
            F(("INFO", "S_FEW_HORDE",
               f"only {len(horde)} horde_spawn marker(s) at site level: "
               f"the director has few ingress choices; waves will feel "
               f"same-y."))
        elif len(horde) >= 2:
            bearings = sorted(_bearing(obj, h) for h in horde)
            gaps = [(bearings[(i + 1) % len(bearings)] - bearings[i]) % 360.0
                    for i in range(len(bearings))]
            spread = 360.0 - max(gaps)
            if spread < 120.0:
                F(("MED", "S_HORDE_ARC",
                   f"all horde spawns arrive from a {spread:.0f} deg arc: "
                   f"the horde always comes from the same side."))

    # --- route diversity across the site graph, when it applies
    try:
        adj = site_tactical.build_graph(site)
        sb, ob = site.get("spawn"), site.get("objective")
        if sb and ob and sb != ob and hasattr(site_tactical,
                                              "_distinct_routes_to"):
            n = site_tactical._distinct_routes_to(adj, ob, sb)
            if n == 1:
                F(("MED", "S_ONE_APPROACH",
                   f"one route from '{sb}' to '{ob}' across the site graph: "
                   f"the approach is a single funnel between buildings."))
    except Exception:
        pass

    counts = {"HIGH": 0, "MED": 0, "INFO": 0}
    for sev, code, msg in findings:
        counts[sev] += 1
    return {"name": name, "mode": mode, "findings": findings,
            "counts": counts}


def format_report(res):
    lines = [f"[site_audit] {res['name']} ({res['mode']}): "
             f"{res['counts']['HIGH']} HIGH / {res['counts']['MED']} MED / "
             f"{res['counts']['INFO']} INFO"]
    order = {"HIGH": 0, "MED": 1, "INFO": 2}
    for sev, code, msg in sorted(res["findings"],
                                 key=lambda f: (order[f[0]], f[1])):
        lines.append(f"  [{sev}] {code}: {msg}")
    if not res["findings"]:
        lines.append("  clean -- structural estimate, not a measure of fun;"
                     " walk it")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="site-level design grammar audit")
    ap.add_argument("spec", help="site spec json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    site = json.load(open(a.spec))
    res = audit(site)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(format_report(res))


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
