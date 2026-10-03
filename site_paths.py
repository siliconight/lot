"""
site_paths.py  --  where a walk goes, decided once
==================================================
A site spec declares a path two ways: ``{"from": id, "to": id}`` between
buildings, or ``{"a": [x, y], "b": [x, y]}`` between points (Level Factory's
door spur, which also names its owner in ``building``). This module decides
what each becomes on the ground, once, after the gameplay merge, and every
reader that draws or measures a walk asks it.

THE HISTORY, kept because each step answered the one before:

  * to 0.87.0 seven readers resolved ``from``/``to`` to the buildings'
    CENTRES, so a walk met a facade wherever the centre line crossed it;
  * 0.88.0 moved each end to the nearest way in on the facade it met;
  * 0.89.0 drew the walk between two doors as square legs at the
    sidewalk's width -- the walker: "these look goofy" of the diagonal band;
  * 0.91.0, this. The walker, walking 0.90.0: "still have sidewalks going to
    walls", and of the legs between two side doors, "looks better, but you
    should do some research as to what looks more natural on a path between
    the sides of 2 buildings ... (not the normal path that customers would
    likely take)".

WHAT THE RESEARCH SAID (`docs/findings/entry_paths/NOTES.md`): design codes
ask for a continuous walk along a facade with a CUSTOMER entrance, tied to
the street's sidewalk; a site walk crosses open pavement only where it must,
square to the aisle, and the aisle itself is never the walkway; building
codes put a level LANDING outside every exterior door -- at least the door's
width and 36 in deep, 60 x 60 in for an accessible one -- with the lot's own
pavement past it. Two separate businesses' side doors are not joined by a
walk.

WHAT 0.91.0 DOES WITH THAT:

  * A WALK LEADS TO A DOOR. Only an opening of kind ``door`` that a body
    fits through counts (`site_enterability._opening_is_entry` and the
    kind): a breach is a wall a team blows through, a vaultable window is a
    window, a garage is for a truck -- the gate counts all three as ways in,
    and the walker's frame of the bank's west wall was a walk to a breach.
  * A DOOR SPUR slides along the facade to the nearest door facing the way
    it leaves, and its near end runs to the wall (`DOOR_BURY` into it, so
    the slab's end face is hidden) instead of stopping a metre short.
  * A SPUR WITH NO DOOR TO MEET IS NOT DRAWN. Its record stays, marked
    ``drawn: False``: the street graph reads it to know the building meets
    that road, and that is still true.
  * A BUILDING PATH IS NOT DRAWN. Two neighbours' side doors get a landing
    each, not a walk across the lot. The record stays for the connectivity
    graph, as above.
  * EVERY DOOR NO WALK REACHES GETS A LANDING: a slab from the wall out
    `LANDING_DEPTH` along the door's normal, the door's width plus
    `LANDING_SIDE` each side, never under `LANDING_MIN`. It is appended to
    the spec's paths as a point path naming its building in ``landing_of``
    (not ``building``: that key means a door spur to the street).

`drawn(site_spec)` is the list a reader that draws or measures a walk
iterates; `endpoints(p, bld)` resolves one record. The connectivity graph
(`site_tactical`) and the plate's extent keep reading every record.

Site space throughout: plan (x, y), metres. Godot is (x, -y).
"""
from __future__ import annotations
import math

#: A door faces a spur's leaving direction when the dot of its outward
#: normal with that direction is at least this: about 45 degrees.
FACING_DOT = 0.7

#: How far a slab that meets a wall runs INTO it, in metres, so its end face
#: sits inside the wall's solid rather than on its plane. Lot cuts the
#: ground 0.45 m inside a footprint (`lot.GROUND_HOLE_INSET`), so the ground
#: is under it.
DOOR_BURY = 0.05

#: A landing outside a door: 60 in deep (the accessible landing, ICC A117.1
#: / the IBC's 36 in minimum rounded up to it), the door's width plus a foot
#: each side, and never narrower than 60 in.
LANDING_DEPTH = 1.525
LANDING_SIDE = 0.3
LANDING_MIN = 1.525

#: The opening kinds a walk may lead to.
DOOR_KINDS = ("door",)

#: The findings' category, in the shape `site_extent._finding` writes.
CATEGORY = "site_paths"


def _unit(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n) if n > 1e-9 else (0.0, 0.0)


def endpoints(p, bld):
    """``((ax, ay), (bx, by))`` for a path record: its own ``a``/``b`` when it
    carries both, else the centres of its ``from``/``to`` buildings. Raises
    KeyError or TypeError when neither resolves."""
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


def drawn(site_spec):
    """The path records a reader that draws or measures a walk iterates:
    every record not marked ``drawn: False``."""
    return [p for p in site_spec.get("paths", []) or [] if p.get("drawn", True)]


def doors(site_spec, merged):
    """{building id: [((x, y), (nx, ny), half width, wall)]}: every storey-0
    exterior opening of a `DOOR_KINDS` kind a body fits through, in site
    space, with its outward normal."""
    import site_enterability as SE
    placements = {b["id"]: b for b in merged.get("buildings", []) or []}
    out = {bid: [] for bid in placements}
    for op in merged.get("openings", []) or []:
        bid = op.get("building")
        if bid not in placements or op.get("kind") not in DOOR_KINDS:
            continue
        if not SE._opening_is_entry(op):
            continue
        where = SE.wall_of(op.get("wall"), op.get("story"))
        if where is None:
            continue
        exterior, story, side = where
        if not exterior or story != 0:
            continue
        b = placements[bid]
        at, rot = b["at"], b.get("rot", 0)
        ex, ey = SE._rot(op.get("x", 0.0), op.get("y", 0.0), rot)
        nx, ny = SE._rot(*SE._WALL_NORMAL[side], rot)
        out[bid].append(((ex + at[0], ey + at[1]), _unit(nx, ny),
                         float(op.get("width") or 1.0) / 2.0, op.get("wall")))
    return out


def _facing_door(entries, origin, leaving):
    """The door whose normal faces `leaving` and which lies nearest the line
    through `origin` along `leaving`; None when no door faces that way."""
    lx, ly = leaving
    best, best_d = None, None
    for e in entries:
        (ex, ey), (nx, ny) = e[0], e[1]
        if nx * lx + ny * ly < FACING_DOT:
            continue
        vx, vy = ex - origin[0], ey - origin[1]
        d = abs(vx * ly - vy * lx)
        if best is None or d < best_d:
            best, best_d = e, d
    return best


def landing(door, bid):
    """The landing record outside one door."""
    (ex, ey), (nx, ny), hw, wall = door
    w = max(LANDING_MIN, 2.0 * hw + 2.0 * LANDING_SIDE)
    return {"a": [ex - nx * DOOR_BURY, ey - ny * DOOR_BURY],
            "b": [ex + nx * LANDING_DEPTH, ey + ny * LANDING_DEPTH],
            "width": w, "landing_of": bid, "wall": wall}


def snap_to_doors(site_spec, merged):
    """Decide what every path in `site_spec` becomes, in place, and append a
    landing at every door no walk reaches. Returns the findings
    (``{"code", "severity", "category", "message"}``) for spurs left undrawn."""
    bld = {b["id"]: b for b in site_spec.get("buildings", []) or []}
    by_bid = doors(site_spec, merged)
    served = set()
    findings = []
    for i, p in enumerate(site_spec.get("paths", []) or []):
        if p.get("landing_of"):
            continue
        if "from" in p and "to" in p:
            # two neighbours' side doors get a landing each, not a walk
            p["drawn"] = False
            continue
        if p.get("building") not in bld:
            continue
        a, b = endpoints_or_none(p, bld)
        if a is None:
            continue
        bid = p["building"]
        at = bld[bid]["at"]
        near_key = "a" if math.dist(a, at) <= math.dist(b, at) else "b"
        here, there = (a, b) if near_key == "a" else (b, a)
        leaving = _unit(there[0] - here[0], there[1] - here[1])
        door = _facing_door(by_bid.get(bid, []), here, leaving)
        if door is None:
            p["drawn"] = False
            findings.append(_no_door(i, p, bid))
            continue
        (ex, ey), _n, _hw, wall = door
        # slide sideways onto the door's line, then run the near end to it
        vx, vy = ex - here[0], ey - here[1]
        along = vx * leaving[0] + vy * leaving[1]
        sx, sy = vx - along * leaving[0], vy - along * leaving[1]
        near = [ex - leaving[0] * DOOR_BURY, ey - leaving[1] * DOOR_BURY]
        far = [there[0] + sx, there[1] + sy]
        p["a"], p["b"] = (near, far) if near_key == "a" else (far, near)
        p["snapped"] = {near_key: wall}
        served.add((bid, wall, round(ex, 3), round(ey, 3)))
    for bid in sorted(by_bid):
        for d in by_bid[bid]:
            (ex, ey), _n, _hw, wall = d
            if (bid, wall, round(ex, 3), round(ey, 3)) in served:
                continue
            site_spec.setdefault("paths", []).append(landing(d, bid))
    return findings


def _no_door(i, p, bid):
    return {"code": "LOT_PATH_END_OFF_DOOR", "severity": "minor",
            "category": CATEGORY,
            "message": (f"path {i} (spur of {bid}): building '{bid}' has no "
                        "ground door on the face this spur meets; the walk is "
                        "not drawn (its record stays for the street graph).")}
