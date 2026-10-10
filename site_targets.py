"""site_targets.py -- the level's numbers against the guide's starting gameplay targets (Lot 0.112.0).

Roadmap 230, the fourth adoption of the walker's adjacency and layout guide
(`docs/reference/PA_1990S_ADJACENCY_AND_LAYOUT_GUIDE.md`, 10.9 "Editable gameplay targets" and
7.4 "Dimensions for initial greyboxing"). The guide's numbers are "starting targets for a small
cooperative mission ... to tune in playtests, not minimum content quotas", so every finding here
is INFO: the measure, the range, and what the gap means. A planner that wants to move a number
reads it here; nothing gates on it.

WHAT IS MEASURED, FROM THE DRAWN SITE SPEC ALONE:
- enterable buildings: the spec's `buildings`, every one of which has a gameplay manifest and a
  door (the guide: 3 to 8);
- ordinary fabric: the Empties (`blockers` flagged `empty`, every instance, facade-only ones
  included, as the guide's denominator says) and the lot buildings that are not the objective,
  over all of them (the guide: 50 to 75 %);
- approaches: the road ends that reach the plate's edge (the ways a crew, a responder or a
  getaway can enter), and the distinct first hops to the objective from the spawn across the site
  graph (`site_tactical._distinct_routes_to`, the number `S_ONE_APPROACH` grades when it is 1;
  the guide: 2 meaningful approaches to the mission area);
- a return loop: the cycles of the road graph, edges less nodes plus components, the roads being
  axis-aligned segments that meet where one crosses or ends on another (the guide: preferred);
- focal points along the critical route: the straight legs spawn -> objective and objective ->
  extraction, the focal candidates being the leg's ends, every lot building whose centre lies
  within `FOCAL_REACH` of the leg (a threshold, a storefront) and every road junction within it (a
  corner); the longest stretch between consecutive candidates along the leg, against the guide's
  20 to 50 m "traveled". A straight line under-reads the travel and over-reads the focus, so the
  number is a floor on the real gap, and the finding says so;
- parking and service: the parking fields and their bays, the driveways and the yards with a
  dumpster, against the buildings they serve (the guide: a parking strategy by use and history,
  never "huge parking lots behind every use").

NOT MEASURED HERE, and said rather than guessed: landmarks (the spec carries signs, not a
landmark; the brief does), simultaneous choices at a decision, regrouping room, and any route
test that needs the navmesh.
"""
import math

ENTERABLE = (3, 8)
ORDINARY_SHARE = (0.50, 0.75)
APPROACHES = 2
FOCAL_SPACING = (20.0, 50.0)
#: how far off a straight leg a building's centre or a junction still reads as a focal point
FOCAL_REACH = 20.0
CODE = "S_TARGETS"


def _pt(b):
    at = b.get("at")
    if isinstance(at, dict):
        return float(at.get("x", 0.0)), float(at.get("y", 0.0))
    if isinstance(at, (list, tuple)) and len(at) >= 2:
        return float(at[0]), float(at[1])
    return None


def _building_pt(site, bid):
    for b in site.get("buildings", []):
        if b.get("id") == bid:
            return _pt(b)
    return None


def _seg_hit(r, s):
    """Where road r meets road s, for axis-aligned roads: the point, and whether it lies at an
    end of r / of s (within half a width), else None. Parallel roads never meet here: a shared
    end would be a corner, which the graph sees as one node anyway."""
    (ax, ay), (bx, by) = r["a"], r["b"]
    (cx, cy), (dx, dy) = s["a"], s["b"]
    rw, sw = float(r.get("width", 10.0)) / 2.0, float(s.get("width", 10.0)) / 2.0
    r_h, s_h = abs(by - ay) < 1e-6, abs(dy - cy) < 1e-6
    if r_h == s_h:
        return None
    if r_h:
        px, py = cx, ay
        if not (min(ax, bx) - rw <= px <= max(ax, bx) + rw and min(cy, dy) - sw <= py <= max(cy, dy) + sw):
            return None
    else:
        px, py = ax, cy
        if not (min(ay, by) - rw <= py <= max(ay, by) + rw and min(cx, dx) - sw <= px <= max(cx, dx) + sw):
            return None
    r_end = min(math.hypot(px - ax, py - ay), math.hypot(px - bx, py - by)) <= rw + sw
    s_end = min(math.hypot(px - cx, py - cy), math.hypot(px - dx, py - dy)) <= rw + sw
    return (px, py), r_end, s_end


def _on(r, p):
    (ax, ay), (bx, by) = r["a"], r["b"]
    w = float(r.get("width", 10.0)) / 2.0
    inside = (min(ax, bx) - w <= p[0] <= max(ax, bx) + w) and (min(ay, by) - w <= p[1] <= max(ay, by) + w)
    return inside and (abs(by - ay) < 1e-6 and abs(p[1] - ay) <= w or abs(bx - ax) < 1e-6 and abs(p[0] - ax) <= w)


def road_graph(roads):
    """``(junctions, loops)``: the points where two roads meet, and the cycles of the graph whose
    nodes are road ends and junctions and whose edges are the pieces between them."""
    junctions = []
    for i, r in enumerate(roads):
        for j, s in enumerate(roads):
            if j <= i:
                continue
            hit = _seg_hit(r, s)
            if hit is not None:
                junctions.append(hit[0])
    nodes = {}

    def node(p):
        key = (round(p[0], 2), round(p[1], 2))
        return nodes.setdefault(key, len(nodes))

    pieces = []
    for r in roads:
        pts = [tuple(r["a"]), tuple(r["b"])] + [p for p in junctions if _on(r, p)]
        along = sorted(set((round(p[0], 2), round(p[1], 2)) for p in pts))
        for p in along:
            node(p)
        pieces += list(zip(along, along[1:]))
    parent = list(range(len(nodes)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p, q in pieces:
        a, b = find(node(p)), find(node(q))
        if a != b:
            parent[a] = b
    comps = len({find(i) for i in range(len(nodes))}) if nodes else 0
    return junctions, len(pieces) - len(nodes) + comps


def plate_approaches(roads, ground):
    """The road ends within a road's width of the plate's edge."""
    sx, sy = float(ground.get("size_x", 0.0)), float(ground.get("size_y", 0.0))
    out = []
    if sx <= 0.0 or sy <= 0.0:
        return out
    for r in roads:
        w = float(r.get("width", 10.0))
        for end in (r["a"], r["b"]):
            ex, ey = float(end[0]), float(end[1])
            if min(abs(ex + sx / 2.0), abs(ex - sx / 2.0), abs(ey + sy / 2.0), abs(ey - sy / 2.0)) <= w:
                out.append((round(ex, 1), round(ey, 1)))
    return out


def focal_gaps(site, junctions):
    """``[(leg, length, longest gap)]`` along the straight legs of the critical route."""
    sp = _building_pt(site, site.get("spawn"))
    ob = _building_pt(site, site.get("objective"))
    ex = _building_pt(site, site.get("extraction"))
    legs = []
    if sp and ob:
        legs.append(("spawn->objective", sp, ob))
    if ob and ex and site.get("extraction") != site.get("objective"):
        legs.append(("objective->extraction", ob, ex))
    cands = [p for p in (_pt(b) for b in site.get("buildings", [])) if p] + list(junctions)
    out = []
    for name, a, b in legs:
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1e-6:
            continue
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        ts = [0.0, length]
        for px, py in cands:
            t = (px - a[0]) * ux + (py - a[1]) * uy
            lateral = abs((px - a[0]) * uy - (py - a[1]) * ux)
            if 0.0 < t < length and lateral <= FOCAL_REACH:
                ts.append(t)
        ts.sort()
        out.append((name, length, max(q - p for p, q in zip(ts, ts[1:]))))
    return out


def measures(site):
    """The numbers, as a dict; `findings` words them."""
    buildings = site.get("buildings", [])
    empties = [b for b in site.get("blockers", []) if b.get("empty")]
    hero = site.get("objective")
    ordinary = len(empties) + sum(1 for b in buildings if b.get("id") != hero)
    total = len(empties) + len(buildings)
    roads = site.get("roads", [])
    junctions, loops = road_graph(roads)
    routes = None
    try:
        import site_tactical
        sb, ob = site.get("spawn"), site.get("objective")
        if sb and ob and sb != ob:
            routes = site_tactical._distinct_routes_to(site_tactical.build_graph(site), ob, sb)
    except Exception:                                    # noqa: BLE001
        routes = None
    fields = site.get("fields") or []
    return {
        "enterable": len(buildings),
        "empties": len(empties),
        "total": total,
        "ordinary_share": (ordinary / float(total)) if total else None,
        "plate_approaches": len(plate_approaches(roads, site.get("ground") or {})),
        "objective_routes": routes,
        "junctions": len(junctions),
        "loops": loops,
        "focal": focal_gaps(site, junctions),
        "fields": len(fields),
        "bays": sum(int(f.get("bays", 0) or 0) for f in fields),
        "driveways": len(site.get("driveways") or []),
        "yards": len(site.get("yards") or []),
    }


def _where(value, lo, hi):
    return "inside" if lo <= value <= hi else ("below" if value < lo else "above")


def findings(site):
    """``[(severity, code, message)]``, every one INFO: the guide's targets are starting numbers."""
    m = measures(site)
    out = []
    n = m["enterable"]
    lo, hi = ENTERABLE
    out.append(("INFO", CODE, f"{n} enterable building(s), {_where(n, lo, hi)} the guide's starting "
                             f"{lo} to {hi}; {m['empties']} Empties stand beside them"))
    s = m["ordinary_share"]
    if s is not None:
        lo, hi = ORDINARY_SHARE
        tail = (": the terrace outnumbers the level's buildings" if s > hi
                else (": too few ordinary buildings for the heroes" if s < lo else ""))
        out.append(("INFO", CODE, f"ordinary fabric {s:.0%} of {m['total']} building instances, the "
                                 f"objective the one hero, {_where(s, lo, hi)} the guide's {lo:.0%} to "
                                 f"{hi:.0%}{tail}"))
    r = m["objective_routes"]
    graph = (f" and {r} distinct first hop(s) reach the objective from the spawn across the site graph"
             if r is not None else "; the site graph was not asked")
    out.append(("INFO", CODE, f"{m['plate_approaches']} road end(s) reach the plate's edge{graph}; the "
                             f"guide asks {APPROACHES} meaningful approaches to the mission area"))
    tail = ": the way back is the way in, and the guide prefers a return loop" if m["loops"] == 0 else ""
    out.append(("INFO", CODE, f"{m['loops']} loop(s) in the road graph over {m['junctions']} junction(s){tail}"))
    lo, hi = FOCAL_SPACING
    for name, length, gap in m["focal"]:
        tail = "; wants a corner, a threshold or a landmark view" if gap > hi else ""
        out.append(("INFO", CODE, f"{name}: {length:.0f} m as the crow flies, the longest stretch between "
                                 f"focal points {gap:.0f} m against the guide's {lo:.0f} to {hi:.0f} m "
                                 f"traveled (the leg's ends, the lot buildings and the junctions within "
                                 f"{FOCAL_REACH:.0f} m of the line count, so the real gap is longer){tail}"))
    out.append(("INFO", CODE, f"{m['fields']} parking field(s) with {m['bays']} bay(s), {m['driveways']} "
                             f"driveway(s) and {m['yards']} yard(s) with a dumpster for {n} building(s)"))
    return out
