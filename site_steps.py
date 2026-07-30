#!/usr/bin/env python3
"""Every place the site asks a body to step up, measured off the EMITTED scene.

A capsule does not meet a low step the way a box does. Contact lands on the
bottom hemisphere, so the contact normal is sloped rather than horizontal, and
the LOWER the step the more vertical that normal gets. For a capsule of radius R
meeting a step of height h, the normal's vertical component is (R - h) / R, so
the tallest step a body can walk up with no step-up assistance at all is

    unassisted_step_max = R * (1 - cos(floor_max_angle))

which for Godot's default 45 degree floor angle and this stack's 0.4 m player
capsule is **0.117 m**. Above that the engine classifies the contact as a WALL
and the capsule stops dead. `agent_contract.json` states `max_step_up_m: 0.5` as
though the body were a box; that number is what a controller can lift itself
over, not what it can walk over.

Lot's own outdoor surfaces sit at:

    Ground      top 0.00
    road        top 0.08     ROAD_THICK
    path        top 0.10     PATH_THICK
    courtyard   top 0.12     COURT_THICK
    sidewalk    top 0.16     SIDEWALK_H   -- "concrete, raised curb"

Stepping off the ground onto a sidewalk is a 0.16 m rise. That is a wall to a
stock CharacterBody3D, which is why walking from a spawn toward the street stops
at the kerb and needs a jump. The courtyard edge at 0.12 clears the limit by
3 mm, which is not a margin.

This reads the scene Lot actually wrote rather than re-deriving the numbers from
the same constants that produced it -- the two agreeing costs microseconds, and
the two disagreeing is the only class of defect the emitter cannot report on
itself (the same reason `site_cover.pinches()` reads back placed cover).
"""
import json
import math
import os
import re

#: Node-name prefixes that are surfaces a body walks ON. Everything else in the
#: outdoor pass -- cover blocks, perimeter walls, blocker massing -- is an
#: obstacle, and the height of an obstacle is not a step.
WALKABLE_PREFIXES = ("Ground", "road_", "sidewalk_", "path_", "courtyard_",
                     "kerbcut_")

#: Ignore differences below this: coincident faces, float noise.
FLUSH_M = 0.02
#: Above this a transition is a wall by intent, not a step someone forgot.
MAX_STEP_OF_INTEREST_M = 1.0

CODE_TOO_TALL = "LOT_STEP_TOO_TALL_TO_WALK"
CODE_NEEDS_ASSIST = "LOT_STEP_NEEDS_ASSIST"
CODE_ROUTE_BLOCKED = "LOT_STEP_BLOCKS_A_ROUTE"


def routes(site_spec):
    """The site's designed circulation, as Godot-plan segments with a width.

    A kerb is SUPPOSED to be a wall -- that is what stops you wandering into
    traffic -- so a transition above the step limit is only a defect where
    someone is meant to walk across it. Without this, the check fires on every
    metre of every kerb and can never go green, which makes it worse than no
    check at all: nobody reads an instrument that is always red.

    Site space is (x, y_plan); Godot is (x, -y_plan)."""
    bld = {b["id"]: b for b in site_spec.get("buildings", []) or []}
    out = []
    for p in site_spec.get("paths", []) or []:
        try:
            a = bld[p["from"]]["at"] if "from" in p else p["a"]
            b = bld[p["to"]]["at"] if "to" in p else p["b"]
        except (KeyError, TypeError):
            continue
        out.append(((float(a[0]), -float(a[1])),
                    (float(b[0]), -float(b[1])),
                    float(p.get("width", 6.0))))
    return out


def _seg_hits_rect(a, b, half_w, corners):
    """Does a fat segment touch this plan rectangle? Sampled, not analytic --
    a route is a corridor, and sampling it at a fraction of its own width
    cannot step over a sidewalk that is metres wide."""
    ax, az = a
    bx, bz = b
    ln = math.hypot(bx - ax, bz - az)
    if ln < 1e-9:
        return False
    n = max(2, int(ln / 0.5))
    xs = [p[0] for p in corners]
    zs = [p[1] for p in corners]
    for i in range(n + 1):
        t = i / n
        px, pz = ax + (bx - ax) * t, az + (bz - az) * t
        if (min(xs) - half_w <= px <= max(xs) + half_w
                and min(zs) - half_w <= pz <= max(zs) + half_w):
            if _point_in(px, pz, corners, half_w):
                return True
    return False


def _point_in(px, pz, corners, margin):
    for ax, az in _axes(corners):
        ln = math.hypot(ax, az)
        if ln < 1e-9:
            continue
        nx, nz = ax / ln, az / ln
        proj = [c[0] * nx + c[1] * nz for c in corners]
        d = px * nx + pz * nz
        if d < min(proj) - margin or d > max(proj) + margin:
            return False
    return True


def unassisted_step_max_m(radius_m, floor_max_angle_deg):
    """The tallest step a capsule walks up with no step-up code at all."""
    return radius_m * (1.0 - math.cos(math.radians(floor_max_angle_deg)))


# ---------------------------------------------------------------------------
# reading the emitted scene
# ---------------------------------------------------------------------------
_BOX = re.compile(
    r'\[node name="([\w\-]+)" type="StaticBody3D" parent="\."\]\s*\n'
    r'transform = Transform3D\(([^)]*)\)(.*?)shape = SubResource\("(\w+)"\)',
    re.S)
_SHAPE = re.compile(
    r'\[sub_resource type="BoxShape3D" id="(\w+)"\]\s*\nsize = Vector3\(([^)]*)\)')


def surfaces(tscn_path):
    """Walkable outdoor boxes as {name, top, corners} in Godot plan space."""
    src = open(tscn_path, encoding="utf-8").read()
    shapes = {m.group(1): [float(v) for v in m.group(2).split(",")]
              for m in _SHAPE.finditer(src)}
    out = []
    for m in _BOX.finditer(src):
        name = m.group(1)
        if not name.startswith(WALKABLE_PREFIXES):
            continue
        size = shapes.get(m.group(4))
        if not size:
            continue
        n = [float(v) for v in m.group(2).split(",")]
        bx, by, bz, o = n[0:3], n[3:6], n[6:9], n[9:12]
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        pts = []
        top = -1e9
        for sx in (-hx, hx):
            for sy in (-hy, hy):
                for sz in (-hz, hz):
                    p = [bx[k] * sx + by[k] * sy + bz[k] * sz + o[k]
                         for k in range(3)]
                    top = max(top, p[1])
                    pts.append((p[0], p[2]))
        # the plan rectangle: the four corners at any one y
        corners = []
        for sx in (-hx, hx):
            for sz in (hz, -hz):
                p = [bx[k] * sx + bz[k] * sz + o[k] for k in range(3)]
                corners.append((p[0], p[2]))
        corners = [corners[0], corners[1], corners[3], corners[2]]
        out.append({"name": name, "top": top, "corners": corners})
    return out


def _axes(c):
    return [(c[1][0] - c[0][0], c[1][1] - c[0][1]),
            (c[3][0] - c[0][0], c[3][1] - c[0][1])]


def _overlap(a, b, margin=0.05):
    """Separating-axis test on two plan rectangles, with a touching margin.

    Rotated roads and sidewalks make axis-aligned bounds useless -- a long
    diagonal road's AABB touches half the site, and every ground tile under it
    would read as adjacent."""
    for rect in (a, b):
        for ax, az in _axes(rect):
            ln = math.hypot(ax, az)
            if ln < 1e-9:
                continue
            nx, nz = ax / ln, az / ln
            pa = [p[0] * nx + p[1] * nz for p in a]
            pb = [p[0] * nx + p[1] * nz for p in b]
            if min(pa) - margin > max(pb) or min(pb) - margin > max(pa):
                return False
    return True


def steps(tscn_path, *, radius_m, floor_max_angle_deg, assist_m):
    """Every rise between two touching walkable surfaces, classified."""
    limit = unassisted_step_max_m(radius_m, floor_max_angle_deg)
    surf = surfaces(tscn_path)
    out = []
    for i, a in enumerate(surf):
        for b in surf[i + 1:]:
            rise = abs(a["top"] - b["top"])
            if rise <= FLUSH_M or rise > MAX_STEP_OF_INTEREST_M:
                continue
            if not _overlap(a["corners"], b["corners"]):
                continue
            lo, hi = (a, b) if a["top"] < b["top"] else (b, a)
            out.append({
                "from": lo["name"], "to": hi["name"],
                "from_top": round(lo["top"], 3), "to_top": round(hi["top"], 3),
                "rise_m": round(rise, 3),
                "walkable_unassisted": rise <= limit,
                "climbable_with_assist": rise <= assist_m,
            })
    out.sort(key=lambda s: (-s["rise_m"], s["from"], s["to"]))
    return out


def findings(tscn_path, *, radius_m, floor_max_angle_deg, assist_m,
             site_spec=None):
    limit = unassisted_step_max_m(radius_m, floor_max_angle_deg)
    issues = []
    found = steps(tscn_path, radius_m=radius_m,
                  floor_max_angle_deg=floor_max_angle_deg, assist_m=assist_m)

    # Which of these does someone have to walk across? Given the spec, a
    # transition only matters where a route crosses it; without one, every
    # transition is reported and the reader has to guess which are kerbs doing
    # their job.
    on_route = set()
    if site_spec is not None:
        surf = {s["name"]: s["corners"] for s in surfaces(tscn_path)}
        for a, b, w in routes(site_spec):
            for s in found:
                key = (s["from"], s["to"])
                if key in on_route:
                    continue
                c = surf.get(s["to"])
                if c and _seg_hits_rect(a, b, w / 2.0, c):
                    on_route.add(key)
        blocking = [s for s in found
                    if (s["from"], s["to"]) in on_route
                    and not s["walkable_unassisted"]]
        if blocking:
            where = "; ".join(f"{s['from']} -> {s['to']} = {s['rise_m']} m"
                              for s in blocking[:6])
            issues.append({
                "code": CODE_ROUTE_BLOCKED, "severity": "major",
                "category": "traversal",
                "message": (
                    f"{len(blocking)} transition(s) that a path crosses rise "
                    f"above {limit:.3f} m, the tallest step a {radius_m} m "
                    f"capsule walks up unassisted: {where}. A body following "
                    f"the site's own circulation is stopped here."),
                "suggested_fix": "Drop the kerb where the route crosses it. A "
                                 "kerb elsewhere is doing its job; a kerb on a "
                                 "crossing is a wall across the way in.",
            })

    def pairs(rows):
        seen, out = set(), []
        for r in rows:
            key = (re.sub(r"_?\d*[LR]?$", "", r["from"]),
                   re.sub(r"_?\d*[LR]?$", "", r["to"]), r["rise_m"])
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    blocked = pairs([s for s in found if not s["climbable_with_assist"]])
    if blocked:
        where = "; ".join(f"{s['from']} ({s['from_top']}) -> {s['to']} "
                          f"({s['to_top']}) = {s['rise_m']} m"
                          for s in blocked[:6])
        issues.append({
            "code": CODE_TOO_TALL, "severity": "major", "category": "traversal",
            "message": (
                f"{len(blocked)} walkable-to-walkable transition(s) rise more "
                f"than the {assist_m} m a controller can lift itself over, so "
                f"nothing crosses them without a jump: {where}"),
            "suggested_fix": "Ramp the transition or lower the upper surface. "
                             "A body cannot get onto it and the navmesh will "
                             "route around it silently.",
        })

    assisted = pairs([s for s in found
                      if s["climbable_with_assist"]
                      and not s["walkable_unassisted"]
                      and (s["from"], s["to"]) not in on_route])
    if assisted:
        where = "; ".join(f"{s['from']} ({s['from_top']}) -> {s['to']} "
                          f"({s['to_top']}) = {s['rise_m']} m"
                          for s in assisted[:6])
        issues.append({
            # Off-route: a kerb that is a wall is a kerb. Worth stating once,
            # because the deliverable ships into projects with no step-up code
            # in them, but it is not a defect to go and fix.
            "code": CODE_NEEDS_ASSIST, "severity": "minor",
            "category": "traversal",
            "message": (
                f"{len(assisted)} transition(s) rise above {limit:.3f} m, the "
                f"tallest step a {radius_m} m capsule walks up unassisted at a "
                f"{floor_max_angle_deg:.0f} deg floor angle. A stock "
                f"CharacterBody3D meets these as a WALL and stops: {where}"),
            "suggested_fix": "The deliverable has to work in a project with "
                             "none of these tools in it, so it cannot assume "
                             "the consumer implemented step-up. Drop the kerb "
                             "where a route crosses it, or bring the surfaces "
                             "within {:.3f} m of each other.".format(limit),
        })
    return issues


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python site_steps.py <site.tscn> [agent_contract.json]")
        raise SystemExit(2)
    contract = {}
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        contract = json.load(open(sys.argv[2], encoding="utf-8"))
    r = float(((contract.get("qa") or {}).get("walker_capsule_radius_m")) or 0.4)
    assist = float(((contract.get("characters") or {}).get("player") or {})
                   .get("max_step_up_m") or 0.5)
    angle = 45.0
    print(f"capsule radius {r} m, floor angle {angle} deg -> unassisted step "
          f"max {unassisted_step_max_m(r, angle):.3f} m; assist {assist} m\n")
    rows = steps(sys.argv[1], radius_m=r, floor_max_angle_deg=angle,
                 assist_m=assist)
    for s in rows:
        flag = ("ok" if s["walkable_unassisted"]
                else ("needs step-up" if s["climbable_with_assist"] else "JUMP"))
        print(f"  {s['from']:<16} {s['from_top']:+.3f}  ->  {s['to']:<16} "
              f"{s['to_top']:+.3f}   rise {s['rise_m']:.3f} m   {flag}")
    print(f"\n{len(rows)} transition(s)")
    for f in findings(sys.argv[1], radius_m=r, floor_max_angle_deg=angle,
                      assist_m=assist):
        print(f"\n[{f['code']}] {f['message']}")
