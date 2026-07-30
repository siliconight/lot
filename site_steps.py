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
    road                     ROAD_THICK
    path                     PATH_THICK
    courtyard                COURT_THICK
    sidewalk    top 0.16     SIDEWALK_H   -- "concrete, raised curb"

The three slabs are derived in lot.py from this limit rather than pinned, and
have to satisfy it in both directions: walkable from the ground, and walkable
onto the sidewalk beside them, so each sits inside [SIDEWALK_H - limit, limit].
They were picked once and COURT_THICK had drifted to 0.12 against a limit of
0.1025 -- a wall, on ballpark_block's own circulation.

Stepping off the ground onto a sidewalk is a 0.16 m rise. That is a wall to a
stock CharacterBody3D, which is why walking from a spawn toward the street stops
at the kerb and needs a jump. It stays a wall on purpose; kerb cuts are what
make the crossings legal.

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
    """Is (px, pz) within `margin` of this convex plan polygon?

    The projection test is a cheap REJECT only. Allowing `margin` of slack on
    each of the polygon's own axes inflates it per-axis -- a BOX inflation --
    which is not the set of points within `margin` of the polygon. Near a corner
    it over-reports by up to sqrt(2)*margin, and it did: on ballpark_block it put
    two sidewalk sections into LOT_STEP_BLOCKS_A_ROUTE whose exact clearance from
    the route centreline was 3.43 m against a 3.00 m half-width. The route never
    reaches them. An instrument that reports a wall a body cannot touch is the
    same substitution defect it exists to catch, so the slack test rejects and an
    exact distance decides.
    """
    inside = True
    for ax, az in _axes(corners):
        ln = math.hypot(ax, az)
        if ln < 1e-9:
            continue
        nx, nz = ax / ln, az / ln
        proj = [c[0] * nx + c[1] * nz for c in corners]
        d = px * nx + pz * nz
        if d < min(proj) - margin or d > max(proj) + margin:
            return False                      # beyond margin on some axis
        if d < min(proj) or d > max(proj):
            inside = False
    if inside:
        return True
    n = len(corners)
    return any(_seg_point_dist(px, pz, corners[i], corners[(i + 1) % n])
               <= margin for i in range(n))


def _seg_point_dist(px, pz, a, b):
    """Exact distance from a plan point to a plan segment."""
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    ln2 = dx * dx + dz * dz
    if ln2 < 1e-12:
        return math.hypot(px - ax, pz - az)
    t = max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / ln2))
    return math.hypot(px - (ax + dx * t), pz - (az + dz * t))


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


def _find_contract(explicit=None):
    """The agent contract, in the search order lot.py already uses.

    An empty contract is not a neutral default. Every number below then falls
    back, and the output looks authoritative while being derived from nothing.
    """
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("DC_AGENT_CONTRACT"):
        cands.append(os.environ["DC_AGENT_CONTRACT"])
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(os.path.dirname(here), "deli_counter",
                              "agent_contract.json"))
    for c in cands:
        try:
            with open(c, "r", encoding="utf-8") as f:
                return json.load(f), c
        except (OSError, ValueError):
            continue
    return {}, None


def _all_specs():
    """[(directory name, path, parsed spec)] for every site spec beside this."""
    here = os.path.dirname(os.path.abspath(__file__))
    base = os.path.join(here, "specs")
    out = []
    if not os.path.isdir(base):
        return out
    for entry in sorted(os.listdir(base)):
        d = os.path.join(base, entry)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith("_site.json"):
                continue
            try:
                with open(os.path.join(d, fname), "r", encoding="utf-8") as f:
                    out.append((entry, os.path.join(d, fname), json.load(f)))
            except (OSError, ValueError):
                continue
    return out


def _find_spec(tscn_path, explicit=None):
    """The site spec that produced this scene.

    Matched on spec["name"] against the scene's stem FIRST, and only then on the
    directory the spec lives in: Lot names a scene from the name FIELD, so
    specs/ref_pvp/ref_pvp_site.json builds ref_pvp_site.tscn -- and a directory
    named ref_pvp_site also exists, so a single pass that accepted either would
    resolve by directory-listing order rather than by intent. Two passes, name
    first, is deterministic.
    """
    if explicit:
        with open(explicit, "r", encoding="utf-8") as f:
            return json.load(f), explicit
    stem = os.path.splitext(os.path.basename(tscn_path))[0]
    specs = _all_specs()
    for _dir, path, spec in specs:
        if spec.get("name") == stem:
            return spec, path
    for _dir, path, spec in specs:
        if _dir == stem:
            return spec, path
    return None, None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Every place a site asks a body to step up, off the "
                    "emitted scene.")
    ap.add_argument("scene", help="a built <site>.tscn")
    ap.add_argument("contract_positional", nargs="?", default=None,
                    help="agent_contract.json (legacy positional form)")
    ap.add_argument("--contract", default=None,
                    help="agent_contract.json; otherwise "
                         "$DC_AGENT_CONTRACT then the deli_counter sibling")
    ap.add_argument("--spec", default=None,
                    help="the site spec; otherwise matched on its name field")
    args = ap.parse_args()

    contract, cpath = _find_contract(args.contract or args.contract_positional)
    if cpath is None:
        print("NO AGENT CONTRACT FOUND. Every metric below would be a fallback, "
              "so nothing is reported. Pass --contract or set "
              "$DC_AGENT_CONTRACT.")
        raise SystemExit(2)

    player = (contract.get("characters") or {}).get("player") or {}
    # The BODY, not the QA walker and not the bake radius. What a capsule walks
    # up is a property of the thing that walks; the walker is deliberately
    # narrower and the bake radius deliberately wider than any body.
    r = float(player.get("radius_m") or 0)
    assist = float(player.get("max_step_up_m") or 0)
    if not r or not assist:
        print(f"{cpath} has no characters.player radius_m / max_step_up_m. "
              f"Nothing is reported rather than guessing a body.")
        raise SystemExit(2)
    angle = 45.0

    spec, spath = _find_spec(args.scene, args.spec)
    print(f"contract {cpath}")
    print(f"player radius {r} m, floor angle {angle:.0f} deg -> walks up "
          f"{unassisted_step_max_m(r, angle):.4f} m unassisted; a controller "
          f"lifts itself {assist} m")
    if spec is None:
        print("NO SITE SPEC FOUND for this scene, so nothing knows which "
              "transitions are ON a route.\n  "
              f"{CODE_ROUTE_BLOCKED} CANNOT FIRE -- pass --spec. A quiet run "
              "here is not a clean one.")
    else:
        print(f"spec     {spath}")
    print()

    rows = steps(args.scene, radius_m=r, floor_max_angle_deg=angle,
                 assist_m=assist)
    for s in rows:
        flag = ("ok" if s["walkable_unassisted"]
                else ("needs step-up" if s["climbable_with_assist"] else "JUMP"))
        print(f"  {s['from']:<16} {s['from_top']:+.3f}  ->  {s['to']:<16} "
              f"{s['to_top']:+.3f}   rise {s['rise_m']:.3f} m   {flag}")
    print(f"\n{len(rows)} transition(s)")

    issues = findings(args.scene, radius_m=r, floor_max_angle_deg=angle,
                      assist_m=assist, site_spec=spec)
    for f in issues:
        print(f"\n[{f['code']}] {f['message']}")
    if not issues:
        print("\nno findings"
              + ("" if spec is not None else " -- but see the missing-spec note "
                                            "above"))
    # 1 = checked, found a major finding. 2 = COULD NOT check. 0 = checked,
    # clean. A run whose major branch was unreachable must not exit 0, or every
    # wrapper reads "could not check" as "passed" -- which is the whole reason
    # this entry point needed fixing.
    if any(f.get("severity") == "major" for f in issues):
        raise SystemExit(1)
    raise SystemExit(0 if spec is not None else 2)
