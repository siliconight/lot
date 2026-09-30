"""
site_enterability.py  --  can you REACH a building's entries once it's placed?
=============================================================================
Deli Counter guarantees each building is enterable ON ITS OWN (its
enterability gate refuses a sealed box). But a building that's fine alone can
become unenterable in a COMPOUND: its only door faces the perimeter wall, or a
neighbour is parked against that face, or it sits in dead space with no path
leading to it. Assembling buildings you can't get into is the site-scale version
of shipping a sealed box -- and only Lot can see it, because only Lot knows the
placements.

This is the approach-side sibling of site_tactical's connectivity gate. Same
rules as the rest of the toolchain: GATE THE CLEAR-CUT CASE, WARN THE REST, and
never auto-fix (we don't move your doors or reroute your paths -- we tell you).

  - HARD GATE: a building has real entries, but EVERY one's approach is blocked
    (buried in a neighbour's footprint, or outside the perimeter). Walled in.
  - WARN: you can reach it, but no authored path/courtyard actually leads to a
    clear entry; or the building's own gameplay.json has no usable entry (a
    Deli Counter problem that slipped through -- fix it there).

What it CANNOT check: the same clearance caveat as Deli Counter -- whether the
swing/vault space is physically clear is a walk-test fact. A clean pass means
"the spec doesn't wall the building in," not "certified walkable."

Operates on the MERGED site data (building records carry at/rot/footprint;
openings carry building/wall/kind/dims + building-local x/y). Pure geometry in
site XY, deterministic.

Body-fit thresholds mirror Deli Counter's enterability.py (the scale
guidelines) -- duplicated because Lot is a standalone repo with no Deli Counter
import. Keep the two in sync if either changes.
"""

from __future__ import annotations
import math

# --- body-fit thresholds (m), mirror Deli Counter enterability.py --------
MIN_PASS_WIDTH = 0.7
MIN_PASS_HEIGHT = 1.1
VAULT_SILL_MAX = 1.2
LOW_WINDOW_SILL = 1.0
_WALK_KINDS = ("door", "garage", "breach")

# how much clear space an entry needs in front of it to be approachable (m).
# 1.5 m ~= the minimum outdoor staging depth in the scale guidelines.
APPROACH_CLEARANCE = 1.5

# local outward normals for each wall (building space, before yaw)
_WALL_NORMAL = {"N": (0.0, 1.0), "S": (0.0, -1.0),
                "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def wall_of(label, story=None):
    """``(exterior, story, side)`` for an opening's ``wall`` label, or None
    when the label is not one this module can read.

    THE LABELS THERE ARE, read off every gameplay.json under this repo when
    this was written (86 files, 1,253 openings): Deli Counter's build writes
    ``ext_<story>_<side>`` (738) and ``int_<story>_<n>`` for a partition
    (430, storey -1 among them); `preview.py` synthesizes the bare side,
    ``N``/``S``/``E``/``W`` (85), with the storey in the opening's own
    ``story``. Until Lot 0.83.0 only the bare side was looked up, so every
    BUILT entry's outward normal was (0, 0): its approach point was the
    doorway itself, and an interior door -- whose doorway is inside its own
    building, which the neighbour test skips -- always read as clear."""
    s = str(label or "")
    if s in _WALL_NORMAL:
        return True, int(story or 0), s
    parts = s.split("_")
    if len(parts) == 3 and parts[0] in ("ext", "int"):
        try:
            st = int(parts[1])
        except ValueError:
            return None
        if parts[0] == "int":
            return False, st, None
        if parts[2] in _WALL_NORMAL:
            return True, st, parts[2]
    return None


def _rot(x, y, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (x * c - y * s, x * s + y * c)


def _opening_is_entry(op):
    """Same classification as Deli Counter: a body-sized, ground-reachable,
    intentional entry."""
    w = op.get("width") or 0.0
    h = op.get("height") or 0.0
    sill = op.get("sill")
    sill = 0.0 if sill is None else sill
    if op.get("width") is None or op.get("height") is None:
        return False  # merged opening should carry dims; if not, can't judge
    fits = w >= MIN_PASS_WIDTH and h >= MIN_PASS_HEIGHT and sill <= VAULT_SILL_MAX
    kind = op.get("kind")
    if kind in _WALK_KINDS:
        designated = True
    elif kind == "window":
        designated = bool(op.get("vaultable")) or sill <= LOW_WINDOW_SILL
    else:
        designated = False
    return designated and fits


def _point_in_footprint(px, py, b):
    """Is world point (px,py) inside building b's footprint rectangle?"""
    fp = b.get("footprint")
    if not fp:
        return False
    fx, fy = fp
    at = b["at"]
    rot = b.get("rot", 0)
    # world -> building local: translate, then un-rotate
    lx, ly = _rot(px - at[0], py - at[1], -rot)
    return abs(lx) <= fx / 2 and abs(ly) <= fy / 2


def _seg_dist(px, py, ax, ay, bx, by):
    """Distance from point to segment AB (site XY)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _approach_points(site_spec, merged, unread=None):
    """Per building: list of (entry_world_xy, approach_world_xy, wall) for every
    valid entry. Uses merged openings (building-local x/y) + placements.

    An entry is a storey-0 EXTERIOR opening, as Deli Counter's
    enterability.py counts one (`ground_entries`: "All ground-floor (story 0)
    exterior openings"). An opening whose wall label `wall_of` cannot read is not
    guessed at: it is appended to ``unread`` so `analyze` can say so."""
    placements = {b["id"]: b for b in merged["buildings"]}
    out = {bid: [] for bid in placements}
    for op in merged.get("openings", []):
        bid = op.get("building")
        if bid not in placements or not _opening_is_entry(op):
            continue
        where = wall_of(op.get("wall"), op.get("story"))
        if where is None:
            if unread is not None:
                unread.append((bid, op.get("wall")))
            continue
        exterior, story, side = where
        if not exterior or story != 0:
            continue
        b = placements[bid]
        at, rot = b["at"], b.get("rot", 0)
        # entry world position (opening x/y are building-local)
        ex, ey = _rot(op.get("x", 0.0), op.get("y", 0.0), rot)
        ex, ey = ex + at[0], ey + at[1]
        # outward normal in world
        nx, ny = _WALL_NORMAL[side]
        wnx, wny = _rot(nx, ny, rot)
        ax = ex + wnx * APPROACH_CLEARANCE
        ay = ey + wny * APPROACH_CLEARANCE
        out[bid].append(((ex, ey), (ax, ay), op.get("wall")))
    return out


def _perimeter_bounds(site_spec):
    """The rect the perimeter wall rings, or None when the site is open.

    Reads the resolved ground extent rather than halving the declared size:
    the wall is built around the plate Lot actually lays down, and on an
    extended plate the two are not the same rect.
    """
    if not site_spec.get("perimeter"):
        return None
    import site_extent
    return site_extent.resolve(site_spec).rect


def _near_route(site_spec, merged, px, py):
    """Is (px,py) on/near an authored path or courtyard? True if none declared
    (open ground = approachable everywhere)."""
    paths = site_spec.get("paths", [])
    courts = site_spec.get("courtyards", [])
    if not paths and not courts:
        return True
    bld = {b["id"]: b for b in merged["buildings"]}
    for p in paths:
        a = bld[p["from"]]["at"] if "from" in p else p.get("a")
        b2 = bld[p["to"]]["at"] if "to" in p else p.get("b")
        if a is None or b2 is None:
            continue
        if _seg_dist(px, py, a[0], a[1], b2[0], b2[1]) <= p.get("width", 3.0) / 2 + 1.0:
            return True
    for c in courts:
        cx, cy = c["at"]
        sx, sy = c.get("size_x", 10), c.get("size_y", 10)
        if abs(px - cx) <= sx / 2 + 1.0 and abs(py - cy) <= sy / 2 + 1.0:
            return True
    return False


def analyze(site_spec, merged):
    """Return a report dict: per-building approach status + errors/warnings.
    Never raises. `gate` raises on the errors this collects."""
    unread = []
    approaches = _approach_points(site_spec, merged, unread)
    bounds = _perimeter_bounds(site_spec)
    others = {b["id"]: b for b in merged["buildings"]}
    buildings, errors, warnings = [], [], []
    for bid, label in sorted(set((b, str(w)) for b, w in unread)):
        warnings.append(
            f"building '{bid}' has an opening on wall '{label}', a label this "
            "gate cannot read -- it was not counted as an entry.")

    for bid, entries in approaches.items():
        if not entries:
            warnings.append(
                f"building '{bid}' has no usable entry in its own gameplay.json "
                "— fix it in Deli Counter (it shouldn't have built).")
            buildings.append({"id": bid, "valid_entries": 0,
                              "clear_entries": 0, "walled_in": False})
            continue
        clear = 0
        routed = 0
        for (ex, ey), (ax, ay), wall in entries:
            blocked = False
            if bounds and not (bounds[0] <= ax <= bounds[2]
                               and bounds[1] <= ay <= bounds[3]):
                blocked = True  # approach falls outside the perimeter wall
            if not blocked:
                for oid, ob in others.items():
                    if oid != bid and _point_in_footprint(ax, ay, ob):
                        blocked = True
                        break
            if not blocked:
                clear += 1
                if _near_route(site_spec, merged, ax, ay):
                    routed += 1
        walled = clear == 0
        if walled:
            errors.append(
                f"building '{bid}' is walled in: all {len(entries)} entrance(s) "
                "are blocked by a neighbour's footprint or the perimeter. Move "
                "the building, rotate it so an entry faces open ground, or clear "
                "the approach.")
        elif routed == 0:
            warnings.append(
                f"building '{bid}' is reachable but no authored path/courtyard "
                "leads to a clear entry — add an approach route so players (and "
                "AI) have a way to it.")
        buildings.append({"id": bid, "valid_entries": len(entries),
                          "clear_entries": clear, "routed_entries": routed,
                          "walled_in": walled})
    return {"buildings": buildings, "errors": errors, "warnings": warnings,
            "note": ("entry swing/vault clearance is a walk-test fact; this "
                     "checks approach space only.")}


class SiteEnterabilityError(Exception):
    pass


def gate(site_spec, merged):
    """Hard gate: raise if any building is walled in. Clear-cut cases only;
    everything softer comes back as warnings via analyze()."""
    report = analyze(site_spec, merged)
    if report["errors"]:
        raise SiteEnterabilityError(
            "site enterability gate failed:\n  - "
            + "\n  - ".join(report["errors"]))
    return report
