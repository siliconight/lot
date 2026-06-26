"""
site_tactical.py  --  site-level tactical intel for Lot
=======================================================
The site-scale echo of Deli Counter's tactical layer. Deli Counter reasons about
reachability and the three modes WITHIN a building (over rooms and doorways). Lot
reasons about them ACROSS the site (over buildings and the paths you declared
between them). Same two ideas, one scale up.

    Deli Counter:  reachability + modes  within a building   (rooms, doors)
    Lot:           reachability + modes  across the site      (buildings, paths)

This is INTEL + light gates, not a navmesh. It analyzes what you DECLARED — the
buildings and the `paths` connecting them, plus the merged markers — never a
computed nav graph over geometry. The in-engine walk stays the real validator
(an offline graph can't prove you can physically cross the courtyard; it can
prove you never declared a route to a building at all). Deterministic, offline.

Two kinds of output, mirroring Deli Counter:
  * INTEL (never fails the build): connectivity, route distances, per-building
    reachability from spawn.
  * GATES (fail the build) only when a site `mode` is declared and its minimum
    structural needs aren't met — the site echo of the per-mode gates.

Site spec additions (all optional; no `mode` => pure intel, no gates):
  "mode": "assault" | "heist" | "survival",
  "objective": "<building id>",      # which building holds the site objective
  "spawn": "<building id>",          # where attackers/crew start
  "extraction": "<building id>",     # heist: where you exit
  "safe": "<building id>",           # survival: the safe building
"""

import math


class SiteTacticalError(Exception):
    """Raised when a declared site mode's hard gate fails."""


def _path_endpoints(p):
    """A declared path connects two building ids (from/to) or raw points. For
    the connectivity graph we only care about building-to-building edges."""
    a = p.get("from")
    b = p.get("to")
    if a is not None and b is not None:
        return a, b
    return None, None


def build_graph(site_spec):
    """Adjacency over building ids using declared building-to-building paths.
    Returns {bid: set(neighbour bids)}. Paths to raw points don't connect
    buildings and are ignored here (they're still geometry in the scene)."""
    ids = [b["id"] for b in site_spec.get("buildings", [])]
    adj = {bid: set() for bid in ids}
    for p in site_spec.get("paths", []):
        a, b = _path_endpoints(p)
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def _reachable_from(adj, start):
    """BFS set of building ids reachable from start over declared paths."""
    if start not in adj:
        return set()
    seen, stack = {start}, [start]
    while stack:
        cur = stack.pop()
        for nb in adj[cur]:
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return seen


def _route_exists(adj, a, b):
    return b in _reachable_from(adj, a)


def _building_pos(site_spec, bid):
    for b in site_spec.get("buildings", []):
        if b["id"] == bid:
            return b["at"]
    return None


def _path_distance(site_spec, a, b):
    """Straight-line distance between two buildings (intel only)."""
    pa, pb = _building_pos(site_spec, a), _building_pos(site_spec, b)
    if pa and pb:
        return math.hypot(pb[0] - pa[0], pb[1] - pa[1])
    return None


def _distinct_routes_to(adj, target, start):
    """Count edge-distinct first hops that can still reach `target` — a cheap
    proxy for 'multiple independent approaches' (the site echo of an assault
    objective room needing >=2 access). Not full max-flow; intentionally simple
    and honest: how many of the target's neighbours sit on a route from start."""
    if target not in adj:
        return 0
    routes = 0
    for nb in adj[target]:
        # can we reach `nb` from start without passing through target?
        sub = {k: (v - {target}) for k, v in adj.items()}
        if nb == start or _route_exists(sub, start, nb):
            routes += 1
    return routes


def analyze(site_spec):
    """Return a site tactical report (intel). Pure analysis, never raises."""
    adj = build_graph(site_spec)
    ids = list(adj.keys())
    report = {
        "mode": site_spec.get("mode"),
        "buildings": ids,
        "edges": sorted({tuple(sorted((a, b))) for a in adj for b in adj[a]}),
        "designations": {
            k: site_spec.get(k) for k in
            ("objective", "spawn", "extraction", "safe")
            if site_spec.get(k)
        },
        "intel": {},
        "warnings": [],
    }
    if not ids:
        return report

    # connectivity intel: reachability from the spawn (or first building)
    root = site_spec.get("spawn") or ids[0]
    reachable = _reachable_from(adj, root)
    isolated = [b for b in ids if b not in reachable]
    report["intel"]["root"] = root
    report["intel"]["reachable_from_root"] = sorted(reachable)
    report["intel"]["isolated_buildings"] = isolated
    if isolated:
        report["warnings"].append(
            f"buildings with no declared path-route from '{root}': "
            f"{', '.join(isolated)}")

    # route distances between consecutive designated points (intel)
    objv = site_spec.get("objective")
    if objv:
        d = _path_distance(site_spec, root, objv)
        if d is not None:
            report["intel"]["spawn_to_objective_dist"] = round(d, 2)
        report["intel"]["objective_approaches"] = _distinct_routes_to(adj, objv, root)

    return report


def gate(site_spec):
    """Apply the declared site mode's hard gates. Raises SiteTacticalError on
    failure. No mode => no gates (pure intel). Mirrors Deli Counter's per-mode
    structural gates, lifted to the site."""
    mode = site_spec.get("mode")
    if not mode:
        return  # pure intel, nothing to gate

    adj = build_graph(site_spec)
    ids = set(adj.keys())

    def need(field, label):
        v = site_spec.get(field)
        if v is None:
            raise SiteTacticalError(
                f"site mode '{mode}' requires a '{field}' building ({label})")
        if v not in ids:
            raise SiteTacticalError(
                f"'{field}' names '{v}', which is not a building in the site")
        return v

    if mode == "assault":
        # objective building must be reachable by >=2 distinct approaches
        obj = need("objective", "the building to assault")
        spawn = site_spec.get("spawn") or next(iter(ids))
        if not _route_exists(adj, spawn, obj):
            raise SiteTacticalError(
                f"assault: no declared path-route from spawn '{spawn}' to "
                f"objective '{obj}'")
        n = _distinct_routes_to(adj, obj, spawn)
        if n < 2:
            raise SiteTacticalError(
                f"assault: objective building '{obj}' has {n} approach route(s); "
                f"needs >=2 distinct approaches (declare another path to it)")

    elif mode == "heist":
        # spawn -> objective -> extraction must be path-connected
        spawn = need("spawn", "where the crew starts")
        obj = need("objective", "the loot/objective building")
        extr = need("extraction", "where the crew exits")
        if not _route_exists(adj, spawn, obj):
            raise SiteTacticalError(
                f"heist: no route from spawn '{spawn}' to objective '{obj}'")
        if not _route_exists(adj, obj, extr):
            raise SiteTacticalError(
                f"heist: no route from objective '{obj}' to extraction '{extr}'")

    elif mode == "survival":
        # a safe building and a holdout (objective) building, path-connected
        safe = need("safe", "the safe starting building")
        hold = need("objective", "the holdout building")
        if not _route_exists(adj, safe, hold):
            raise SiteTacticalError(
                f"survival: no route from safe building '{safe}' to holdout "
                f"'{hold}'")

    else:
        raise SiteTacticalError(
            f"unknown site mode '{mode}' (expected assault/heist/survival)")
