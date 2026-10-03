"""
site_paths.py  --  where a path's ends are, decided once
========================================================
A site spec declares a path two ways: ``{"from": id, "to": id}`` between
buildings, or ``{"a": [x, y], "b": [x, y]}`` between points (Level Factory's
door spur, which also names its owner in ``building``). Seven readers in
this repo resolved the first form to the buildings' CENTRES, each in its own
line, and drew, zoned, gated and kerb-cut a corridor that ran from the middle
of one building to the middle of the next. The walker, 2026-10-03, on cold
run 9139's lot: "sidewalks don't consistently lead up to doors which seems
random" and, after the first look, "lot still not drawing walkways to open
doorways". It was not random: the spur to the bank ran at the bank's centre
x while its doors sat metres to the side, and the wide path between two
buildings met each at whatever point of the facade the centre line crossed.

THE BUILDING KNOWS WHERE ITS DOORS ARE. `site_enterability._approach_points`
reads every storey-0 exterior entry out of the merged gameplay with its
outward normal; this module uses that answer and nothing it would have to
guess. `snap_to_doors` runs once in `assemble`, after the gameplay merge and
before anything reads a path, and writes the resolved ``a``/``b`` into the
spec's own path records (the ids stay, so the connectivity graph and the
surface labels do not move). `endpoints` is the one reader every consumer
calls: ``a``/``b`` when a path carries them, the centres otherwise -- so a
hand-authored spec that predates this resolves exactly as it did.

What a snap does, per path end that belongs to a building:

  * the end LEAVES the building in some direction -- a spur's, away from its
    owner toward its far end; a building path's, toward the other building;
  * the entries whose outward normal faces that way (within `FACING_DOT`)
    are the doors on the facade the path meets;
  * the nearest of them to the path's own line wins;
  * a spur slides sideways along the facade until it runs at that door, its
    standoff from the face kept as authored; a building path's end becomes
    the point `DOOR_STANDOFF` in front of that door.

A facade with no door is said (`LOT_PATH_END_OFF_DOOR`) and the end stays
where it was: a path that reaches a blank wall is a defect this cannot fix
by inventing a door, and the finding is what the brief or the building's
author needs to see.

Site space throughout: plan (x, y), metres. Godot is (x, -y).
"""
from __future__ import annotations
import math

#: How far in front of its door's face a building path ends, in metres. The
#: figure Level Factory's door spur uses for its own near end (`road_grammar.
#: _spurs`: ``face - 1.0``), so a snapped building path and a spur stop the
#: same distance short of the wall and the ground in front of a door reads
#: as one thing. `site_enterability.APPROACH_CLEARANCE` (1.5) is the space a
#: body needs there, not where the slab ends; a slab ending 1.0 m out leaves
#: that space clear.
DOOR_STANDOFF = 1.0

#: A door faces a path's leaving direction when the dot of its outward normal
#: with that direction is at least this. 0.7 is about 45 degrees: a door on
#: the facade the path meets, never one round the corner, with room for a
#: building rotated off the row.
FACING_DOT = 0.7

#: The findings' category, in the shape `site_extent._finding` writes.
CATEGORY = "site_paths"


def _unit(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n) if n > 1e-9 else (0.0, 0.0)


def endpoints(p, bld):
    """``((ax, ay), (bx, by))`` for a path record: its own ``a``/``b`` when it
    carries both, else the centres of its ``from``/``to`` buildings. Raises
    KeyError or TypeError when neither resolves, like the inline readers it
    replaces did, so callers that skip such a record still can."""
    if p.get("a") is not None and p.get("b") is not None:
        a, b = p["a"], p["b"]
    else:
        a = bld[p["from"]]["at"]
        b = bld[p["to"]]["at"]
    return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


def endpoints_or_none(p, bld):
    """`endpoints`, or ``(None, None)`` for a record it cannot resolve."""
    try:
        return endpoints(p, bld)
    except (KeyError, TypeError, IndexError):
        return None, None


def _entries(site_spec, merged):
    """{building id: [(entry (x, y), outward normal (nx, ny), wall)]} for
    every storey-0 exterior entry, from the enterability gate's own reading."""
    import site_enterability
    out = {}
    for bid, rows in site_enterability._approach_points(site_spec, merged).items():
        lst = []
        for (ex, ey), (ax, ay), wall in rows:
            lst.append(((ex, ey), _unit(ax - ex, ay - ey), wall))
        out[bid] = lst
    return out


def _facing_door(entries, origin, leaving):
    """The entry whose normal faces `leaving` and which lies nearest the line
    through `origin` along `leaving`; None when no door faces that way."""
    lx, ly = leaving
    best, best_d = None, None
    for (ex, ey), (nx, ny), wall in entries:
        if nx * lx + ny * ly < FACING_DOT:
            continue
        # perpendicular distance from the door to the path's line
        vx, vy = ex - origin[0], ey - origin[1]
        d = abs(vx * ly - vy * lx)
        if best is None or d < best_d:
            best, best_d = ((ex, ey), (nx, ny), wall), d
    return best


def snap_to_doors(site_spec, merged):
    """Rewrite every path's ``a``/``b`` in `site_spec` so each end that
    belongs to a building meets one of that building's doors. Returns the
    findings (``{"code", "severity", "category", "message"}``) for ends it
    had to leave alone."""
    bld = {b["id"]: b for b in site_spec.get("buildings", []) or []}
    entries = _entries(site_spec, merged)
    findings = []
    for i, p in enumerate(site_spec.get("paths", []) or []):
        a, b = endpoints_or_none(p, bld)
        if a is None:
            continue
        snapped = {}
        if "from" in p and "to" in p:
            # a building path: each end leaves toward the other building
            ends = {"a": (p["from"], a, b), "b": (p["to"], b, a)}
            for key, (bid, here, there) in ends.items():
                leaving = _unit(there[0] - here[0], there[1] - here[1])
                door = _facing_door(entries.get(bid, []), here, leaving)
                if door is None:
                    findings.append(_off_door(i, p, key, bid, "its centre"))
                    continue
                (ex, ey), (nx, ny), wall = door
                p[key] = [ex + nx * DOOR_STANDOFF, ey + ny * DOOR_STANDOFF]
                snapped[key] = wall
            # A HALF-SNAPPED PATH CARRIES BOTH POINTS. `endpoints` reads a/b
            # only when both are there, so writing the one end that found a
            # door would lose it again to the centres; the end that found
            # none is written as the centre it stays at.
            if snapped:
                for key, (_bid, here, _there) in ends.items():
                    if key not in snapped:
                        p[key] = [here[0], here[1]]
        elif p.get("building") in bld:
            # a door spur: the end nearer its owner is the door end; it
            # leaves toward the far end; the whole spur slides sideways
            bid = p["building"]
            at = bld[bid]["at"]
            near_key, far_key = ("a", "b") if math.dist(a, at) <= math.dist(b, at) else ("b", "a")
            here, there = (a, b) if near_key == "a" else (b, a)
            leaving = _unit(there[0] - here[0], there[1] - here[1])
            door = _facing_door(entries.get(bid, []), here, leaving)
            if door is None:
                findings.append(_off_door(i, p, near_key, bid, "where it was authored"))
                continue
            (ex, ey), _n, wall = door
            vx, vy = ex - here[0], ey - here[1]
            along = vx * leaving[0] + vy * leaving[1]
            sx, sy = vx - along * leaving[0], vy - along * leaving[1]
            p["a"] = [a[0] + sx, a[1] + sy]
            p["b"] = [b[0] + sx, b[1] + sy]
            snapped[near_key] = wall
        else:
            continue
        if snapped:
            p["snapped"] = snapped
    return findings


def _off_door(i, p, key, bid, stays):
    label = (f"{p.get('from')}->{p.get('to')}" if "from" in p
             else f"spur of {p.get('building')}")
    return {"code": "LOT_PATH_END_OFF_DOOR", "severity": "minor",
            "category": CATEGORY,
            "message": (f"path {i} ({label}): building '{bid}' has no ground "
                        f"door on the face this path meets at end '{key}'; the "
                        f"end stays at {stays} and the walkway reaches a blank "
                        "wall.")}
