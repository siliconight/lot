#!/usr/bin/env python3
r"""site_layout_lint.py -- LAYOUT_RULES guard rails at SITE scale.

Complements lot.py's hard pvp gates (spawn separation, approach counts) with
the level-design rules from LAYOUT_RULES.md sections A/D applied to the site:

  S1 spine pacing     attacker spawn -> objective -> extraction distances sit
                      inside the mission tier's envelope (no instant rushes,
                      no marathon walks)
  S2 extraction pull  extraction is a REAL second trip: away from the attacker
                      spawn, outside every building footprint, inside the ground
  S3 open kill lanes  any declared path leg > 40 m with no cover within 8 m of
                      the line is a naked crossing (err on less cover, but not
                      none on the main lanes)
  S4 lane structure   3-8 building-graph edges (FPS lane canon: 3-4 lanes,
                      chokepoints not all coverable from one spot)
  S5 approach spread  the objective building's path neighbors approach from
                      >= 90 degrees apart, so one defender angle cannot hold
                      every approach

    python site_layout_lint.py specs\<site>\<site>_site.json [...]
    python site_layout_lint.py --all

Advisory layer: the engine gates (walktest, mp_smoke) stay the traversal truth.
"""
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DELI_SPECS = os.path.normpath(os.path.join(HERE, "..", "deli_counter", "specs"))

SPINE_MIN = 40.0        # m, spawn->objective floor (no instant rush)
SPINE_MAX = 220.0       # m, spawn->objective ceiling (no marathon)
EXTRACT_MIN = 30.0      # m, extraction pulled away from attacker spawn
LANE_MIN, LANE_MAX = 3, 8
KILL_LANE = 40.0        # m, uncovered straight leg
COVER_NEAR = 8.0        # m, cover counts if within this of the leg line
SPREAD_MIN = 90.0       # deg, angular spread of objective approaches


def footprint(glb_name):
    stem = os.path.basename(glb_name)[:-4]
    p = os.path.join(DELI_SPECS, stem + ".json")
    if os.path.exists(p):
        s = json.load(open(p))
        return s.get("footprint_x", 20.0), s.get("footprint_y", 20.0)
    return 20.0, 20.0


def _seg_point_dist(a, b, p):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def lint(path):
    s = json.load(open(path))
    name = s.get("name", os.path.basename(path))
    fails, warns = [], []
    if s.get("mode") != "pvp_heist":
        return name, fails, warns

    pos = {b["id"]: tuple(b["at"]) for b in s.get("buildings", [])}
    fp = {b["id"]: footprint(b["glb"]) for b in s.get("buildings", [])}
    edges = [(p["from"], p["to"]) for p in s.get("paths", [])]
    cover = [tuple(c["at"]) for c in s.get("cover", [])]
    # The ground the site is actually built on, from the one module that
    # decides it. Halving the declared size assumes the plate is centred on the
    # origin, and a site whose row is not centred fails S2 for markers that are
    # standing on ground.
    import site_extent
    ground = site_extent.resolve(s).rect or (0.0, 0.0, 0.0, 0.0)

    atk = ext = None
    for m in s.get("site_markers", []):
        if m.get("type") == "attacker_spawn":
            atk = tuple(m["at"])
        elif m.get("type") == "extraction":
            ext = tuple(m["at"])
    obj = s.get("objective")
    spawn_b = s.get("spawn")
    extr_b = s.get("extraction")

    if not (atk and obj in pos):
        fails.append("S1 missing attacker_spawn marker or objective building")
        return name, fails, warns

    # S1: spine pacing
    d_obj = math.hypot(atk[0] - pos[obj][0], atk[1] - pos[obj][1])
    if d_obj < SPINE_MIN:
        fails.append(f"S1 attacker spawn only {d_obj:.0f}m from objective "
                     f"building (< {SPINE_MIN:.0f}m: instant rush)")
    elif d_obj > SPINE_MAX:
        warns.append(f"S1 attacker spawn {d_obj:.0f}m from objective "
                     f"(> {SPINE_MAX:.0f}m: marathon approach)")

    # S2: extraction is a real second trip, in bounds, outside footprints
    if ext:
        d_ext = math.hypot(atk[0] - ext[0], atk[1] - ext[1])
        if d_ext < EXTRACT_MIN:
            fails.append(f"S2 extraction {d_ext:.0f}m from attacker spawn "
                         f"(< {EXTRACT_MIN:.0f}m: no loop, spawn-camp exit)")
        if not (ground[0] <= ext[0] <= ground[2]
                and ground[1] <= ext[1] <= ground[3]):
            fails.append(f"S2 extraction marker {ext} outside ground bounds")
        for bid, (bx, by) in pos.items():
            w, d = fp[bid]
            if (abs(ext[0] - bx) < w / 2 and abs(ext[1] - by) < d / 2
                    and bid != extr_b):
                warns.append(f"S2 extraction marker sits inside building "
                             f"'{bid}' footprint (marker is ground-level)")

    # S3: naked crossings on declared paths
    for a, b in edges:
        if a not in pos or b not in pos:
            continue
        L = math.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1])
        if L <= KILL_LANE:
            continue
        near = any(_seg_point_dist(pos[a], pos[b], c) <= COVER_NEAR
                   for c in cover)
        if not near:
            warns.append(f"S3 path {a}->{b} is {L:.0f}m with no cover within "
                         f"{COVER_NEAR:.0f}m: naked crossing")

    # S4: lane structure
    if not (LANE_MIN <= len(edges) <= LANE_MAX):
        warns.append(f"S4 {len(edges)} path edges (lane canon wants "
                     f"{LANE_MIN}-{LANE_MAX})")

    # S5: angular spread of objective approaches
    nbrs = [b for a, b in edges if a == obj] + [a for a, b in edges if b == obj]
    angs = []
    for n in set(nbrs):
        if n in pos:
            angs.append(math.degrees(math.atan2(pos[n][1] - pos[obj][1],
                                                pos[n][0] - pos[obj][0])))
    if len(angs) >= 2:
        angs.sort()
        spread = max((angs[i] - angs[i - 1]) % 360 for i in range(len(angs)))
        spread = 360 - spread if len(angs) > 1 else 0
        if spread < SPREAD_MIN:
            warns.append(f"S5 objective approaches span only {spread:.0f} deg "
                         f"(< {SPREAD_MIN:.0f}: one angle holds them all)")
    elif len(angs) == 1:
        warns.append("S5 objective has a single path neighbor")

    return name, fails, warns


def main():
    args = sys.argv[1:]
    if "--all" in args:
        paths = sorted(glob.glob(os.path.join(HERE, "specs", "*", "*_site.json")))
    else:
        paths = [a for a in args if a.endswith(".json")]
    tf = tw = 0
    for p in paths:
        try:
            name, fails, warns = lint(p)
        except Exception as e:
            print(f"== {os.path.basename(p)} ==\n  SITE-LINT-ERROR: {e}")
            tf += 1
            continue
        if not fails and not warns:
            continue
        print(f"== {name} ==")
        for f in fails:
            print(f"  SITE-LINT-FAIL: {f}")
        for w in warns:
            print(f"  SITE-LINT-WARN: {w}")
        tf += len(fails)
        tw += len(warns)
    print(f"\n[site-lint] {len(paths)} sites: {tf} FAIL, {tw} WARN")
    sys.exit(1 if tf else 0)


if __name__ == "__main__":
    main()
