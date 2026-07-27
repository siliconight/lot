"""How big the ground is, and where it sits.

Five places in Lot answered that question, and all five answered it the same
wrong way::

    hx, hy = g["size_x"] / 2, g["size_y"] / 2

That reads the declared *size* of the ground plate and assumes the plate is
centred on the site origin. Nothing in the site spec says it is. A spec is free
to place its buildings anywhere, and the one that produced this module placed
four 44 m shells at x = -6, 39, 93 and 138 -- a row spanning x -28 to 160 --
under a ground plate declared 232 x 100, which the centred reading laid down
across x -116 to 116.

The plate was wide enough. It was in the wrong place. The last building in the
row hung 44 m off the +x edge, and `_ground_tiles` clipped that building's
ground hole to the plate instead of saying so, which turned the defect into
silence: a hole clipped out of existence produces exactly the tile list a hole
that fitted produces. The crew spawn sat one metre above that building's own
interior floor with no site ground anywhere near it, so the crew started on an
island. Every enemy spawn, the objective and the extraction were on the plate
and correctly reported unreachable, and the map came back BROKEN with zero
completed runs -- for a plate offset, on a site whose geometry was fine.

So the extent is decided once, here, from the content rather than from an
assumption, and everything that needs to know reads it:

  * `resolve(site_spec)` -> the rect the ground will actually be built as,
    plus findings describing anything it had to do to get there.
  * The plate grows when it does not contain the site. Extra ground can never
    create a fall -- the worst case is ground under a building that floored
    itself already, and the hole policy in `site_ground` decides that
    separately. A plate too small, by contrast, is a void.
  * Growth is never quiet. `LOT_GROUND_EXTENDED` says how far and on which
    edge, and when the declared plate had the area but not the position,
    `LOT_GROUND_OFF_CENTRE` names the offset so the defect can be fixed in
    whatever wrote the spec instead of absorbed here forever.
  * A hole that is not contained by the final rect is a blocking finding, not
    a clip. That is the specific silence this module exists to end.

Pure: dicts in, a rect and findings out. Stdlib only, no Godot, no Blender.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Ground kept outside the outermost solid, in metres. Not styling: Godot
#: erodes the navmesh by the 0.4 m agent radius at every geometry edge, from
#: the plate rim as much as from a wall, so a plate that stops flush with a
#: building leaves a walkable strip of nothing and the building is an island
#: again by a narrower route. Four metres leaves ~3.2 m of navmesh to walk.
CLEARANCE = 4.0

#: Grown edges land on whole metres. A plate whose extent is a rounded number
#: is one a human can check against the spec by eye.
SNAP = 1.0

#: Past this span a site is not a site, it is a placement bug that would
#: otherwise be honoured with a kilometre of ground. Still grown -- a blocking
#: finding is more use than a void -- but reported as a blocker.
MAX_SPAN = 2000.0

CODE_EXTENDED = "LOT_GROUND_EXTENDED"
CODE_OFF_CENTRE = "LOT_GROUND_OFF_CENTRE"
CODE_UNKNOWN_EXTENT = "LOT_GROUND_EXTENT_UNKNOWN"
CODE_UNREASONABLE = "LOT_GROUND_UNREASONABLE"
CODE_HOLE_OUTSIDE = "LOT_GROUND_HOLE_OUTSIDE"
CODE_OVERLAP = "LOT_BUILDINGS_OVERLAP"

#: How far two shells may reach into each other before it is broken geometry
#: rather than a tight row, in metres. Deli Counter's exterior walls are 0.25 m,
#: so half a metre is "the cladding is kissing" and anything past it is a wall
#: standing inside somebody's living room.
OVERLAP_TOLERANCE = 0.5

CATEGORY = "site_ground"


# ---------------------------------------------------------------------------
# rects
# ---------------------------------------------------------------------------
def rect_of(cx, cy, size_x, size_y):
    """A rect centred on ``(cx, cy)``."""
    return (cx - size_x / 2.0, cy - size_y / 2.0,
            cx + size_x / 2.0, cy + size_y / 2.0)


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def grow(rect, by):
    return (rect[0] - by, rect[1] - by, rect[2] + by, rect[3] + by)


def contains(rect, point) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def contains_rect(outer, inner) -> bool:
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def size(rect):
    return (rect[2] - rect[0], rect[3] - rect[1])


def centre(rect):
    return ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0)


def _snap_out(rect, step=SNAP):
    """Round a rect outwards to whole ``step`` metres. Outwards only: rounding
    an edge inwards is how you lose the last 40 cm of a footprint."""
    if step <= 0:
        return rect
    return (math.floor(rect[0] / step) * step, math.floor(rect[1] / step) * step,
            math.ceil(rect[2] / step) * step, math.ceil(rect[3] / step) * step)


# ---------------------------------------------------------------------------
# what the site is made of
# ---------------------------------------------------------------------------
def _footprint_of(bdef):
    """``(size_x, size_y)`` for a placed building, or None when unreadable.

    ``_footprint`` is the annotation `merge_gameplay` writes onto the spec from
    the building's gameplay JSON; ``footprint`` is the same number as it appears
    on a site record. Either is a reading; neither present is not zero.
    """
    for key in ("_footprint", "footprint"):
        fp = bdef.get(key)
        if fp:
            try:
                return float(fp[0]), float(fp[1])
            except (TypeError, ValueError, IndexError):
                return None
    return None


def rotated_footprint(bdef):
    """Axis-aligned footprint rect in site space, or None when unreadable.

    Same rotation handling as `site_spawns.footprint_rect` and the ground-hole
    cut in `lot._outdoor_nodes`: right angles swap the axes exactly, anything
    else is bounded by its enclosing box rather than approximated, so the rect
    is never smaller than the building.
    """
    fp = _footprint_of(bdef)
    if fp is None:
        return None
    fx, fy = fp
    rot = (float(bdef.get("rot", 0) or 0) % 360 + 360) % 360
    if rot % 180 == 90:
        fx, fy = fy, fx
    elif rot % 90 != 0:
        th = math.radians(rot)
        fx, fy = (abs(fx * math.cos(th)) + abs(fy * math.sin(th)),
                  abs(fx * math.sin(th)) + abs(fy * math.cos(th)))
    at = bdef.get("at") or (0.0, 0.0)
    return rect_of(float(at[0]), float(at[1]), fx, fy)


def _point(value):
    if not value:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError, IndexError):
        return None


def content(site_spec):
    """``(labelled_rects, unknown_ids)`` -- everything the ground must carry.

    A labelled rect is ``(label, (x0, y0, x1, y1))``. ``unknown_ids`` names the
    buildings whose footprint could not be read, because a building of unknown
    size is not a building of no size and the caller has to be able to say so.
    """
    rects = []
    unknown = []

    for bdef in site_spec.get("buildings") or []:
        bid = str(bdef.get("id", "?"))
        rect = rotated_footprint(bdef)
        if rect is None:
            at = _point(bdef.get("at"))
            if at is not None:
                rects.append((bid, (at[0], at[1], at[0], at[1])))
            unknown.append(bid)
            continue
        rects.append((bid, rect))

    for i, bk in enumerate(site_spec.get("blockers") or []):
        at = _point(bk.get("at"))
        if at is None:
            continue
        sx = float(bk.get("size_x", 12.0) or 12.0)
        sy = float(bk.get("size_y", 12.0) or 12.0)
        rects.append((str(bk.get("id", f"blocker_{i}")),
                      rect_of(at[0], at[1], sx, sy)))

    for i, cdef in enumerate(site_spec.get("courtyards") or []):
        at = _point(cdef.get("at"))
        if at is None:
            continue
        rects.append((f"courtyard_{i}",
                      rect_of(at[0], at[1], float(cdef.get("size_x", 10)),
                              float(cdef.get("size_y", 10)))))

    for i, cv in enumerate(site_spec.get("cover") or []):
        at = _point(cv.get("at"))
        if at is None:
            continue
        sz = cv.get("size") or (1.0, 1.0, 1.0)
        rects.append((f"cover_{i}", rect_of(at[0], at[1], float(sz[0]),
                                            float(sz[2] if len(sz) > 2 else sz[1]))))

    at_of = {str(b.get("id")): _point(b.get("at"))
             for b in site_spec.get("buildings") or []}

    def _ends(defn):
        a = at_of.get(defn.get("from")) if "from" in defn else _point(defn.get("a"))
        b = at_of.get(defn.get("to")) if "to" in defn else _point(defn.get("b"))
        return a, b

    for kind, width_key, default_w in (("paths", "width", 3.0),
                                       ("roads", "width", 9.0)):
        for i, defn in enumerate(site_spec.get(kind) or []):
            a, b = _ends(defn)
            if a is None or b is None:
                continue
            half = float(defn.get(width_key, default_w) or default_w) / 2.0
            rects.append((f"{kind[:-1]}_{i}",
                          grow((min(a[0], b[0]), min(a[1], b[1]),
                                max(a[0], b[0]), max(a[1], b[1])), half)))

    for i, m in enumerate(site_spec.get("site_markers") or []):
        at = _point(m.get("at"))
        if at is None:
            continue
        label = str(m.get("type", f"marker_{i}"))
        rects.append((label, (at[0], at[1], at[0], at[1])))

    return rects, unknown


def required_rect(site_spec, *, clearance=CLEARANCE):
    """The smallest ground rect that carries this site, or None when the spec
    describes nothing to stand on."""
    rects, _unknown = content(site_spec)
    if not rects:
        return None
    out = None
    for _label, rect in rects:
        out = union(out, rect)
    return grow(out, clearance)


def declared_rect(site_spec):
    """The plate the spec asked for, or None when it declares no ground.

    ``ground.at`` is honoured when present so a spec can say where its plate
    sits instead of relying on a convention. Absent, the plate is centred on
    the origin -- which is what every existing spec means.
    """
    g = site_spec.get("ground")
    if not g:
        return None
    try:
        sx, sy = float(g["size_x"]), float(g["size_y"])
    except (KeyError, TypeError, ValueError):
        return None
    if sx <= 0 or sy <= 0:
        return None
    at = _point(g.get("at")) or (0.0, 0.0)
    return rect_of(at[0], at[1], sx, sy)


# ---------------------------------------------------------------------------
# the answer
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Ground:
    """The resolved ground extent.

    ``rect`` is None only when the spec declares no ground at all, which is a
    legitimate all-interior site and not an error. ``findings`` are Lot's
    standard finding dicts, ready to extend a tactical report with.
    """
    rect: tuple | None
    declared: tuple | None
    required: tuple | None
    findings: list = field(default_factory=list)

    @property
    def extended(self) -> bool:
        return (self.rect is not None and self.declared is not None
                and self.rect != self.declared)

    @property
    def size(self):
        return None if self.rect is None else size(self.rect)

    def contains(self, point) -> bool:
        return self.rect is not None and contains(self.rect, point)


def _finding(code, severity, message):
    return {"code": code, "severity": severity, "category": CATEGORY,
            "message": message}


def _edge_report(declared, final):
    """Human-readable per-edge growth, e.g. ``+44 m east, +2 m north``."""
    parts = []
    for amount, name in ((declared[0] - final[0], "west"),
                         (final[2] - declared[2], "east"),
                         (declared[1] - final[1], "south"),
                         (final[3] - declared[3], "north")):
        if amount > 1e-6:
            parts.append(f"+{amount:g} m {name}")
    return ", ".join(parts)


def resolve(site_spec, *, clearance=CLEARANCE, snap=SNAP) -> Ground:
    """Decide the ground rect this site will actually be built with."""
    declared = declared_rect(site_spec)
    required = required_rect(site_spec, clearance=clearance)
    _rects, unknown = content(site_spec)
    findings = []

    if declared is None:
        return Ground(None, None, required, findings)
    if required is None:
        return Ground(declared, declared, None, findings)

    final = declared
    if not contains_rect(declared, required):
        final = _snap_out(union(declared, required), snap)

    if final != declared:
        outside = [label for label, rect in _rects
                   if not contains_rect(declared, rect)]
        dw, dd = size(declared)
        rw, rd = size(required)
        message = (f"the declared {dw:g} x {dd:g} m ground plate does not cover "
                   f"the site it was built for; extended to "
                   f"{size(final)[0]:g} x {size(final)[1]:g} m "
                   f"({_edge_report(declared, final)}) so "
                   f"{', '.join(outside[:6])} "
                   f"{'stands' if len(outside) == 1 else 'stand'} on ground")
        findings.append(_finding(CODE_EXTENDED, "moderate", message))

        # The plate had the area and not the position. Worth its own finding:
        # this one is fixable where the spec is written, and a plate that is
        # only ever grown here stays wrong at the source forever.
        if rw <= dw + 1e-6 and rd <= dd + 1e-6:
            ox, oy = centre(required)
            dx, dy = centre(declared)
            findings.append(_finding(
                CODE_OFF_CENTRE, "minor",
                f"the {dw:g} x {dd:g} m plate is large enough for this site "
                f"({rw:g} x {rd:g} m) but centred at ({dx:g}, {dy:g}) while the "
                f"site is centred at ({ox:g}, {oy:g}) -- whatever wrote this "
                f"spec sized the ground from the building count and then "
                f"assumed the row was centred on the origin"))

    if unknown:
        findings.append(_finding(
            CODE_UNKNOWN_EXTENT, "moderate",
            f"{len(unknown)} building(s) have no readable footprint "
            f"({', '.join(unknown[:6])}), so the ground extent was decided "
            f"from their origins only and may not reach their walls"))

    span_x, span_y = size(final)
    if span_x > MAX_SPAN or span_y > MAX_SPAN:
        findings.append(_finding(
            CODE_UNREASONABLE, "blocker",
            f"this site spans {span_x:g} x {span_y:g} m, past the {MAX_SPAN:g} m "
            f"limit; the ground was still built to cover it, but a site this "
            f"size is a placement error rather than a level"))

    return Ground(final, declared, required, findings)


def overlap_findings(site_spec, *, tolerance=OVERLAP_TOLERANCE):
    """Findings for buildings placed on top of each other.

    Nothing in Lot asked this. The site audit checked markers against footprints
    and the layout lint checked markers against bounds, but no check compared two
    footprints to each other, so a row whose spacing was narrower than its shells
    assembled two interpenetrating buildings and reported a clean site. What the
    player finds there is a wall through a room, a doorway into solid geometry,
    and a navmesh with a hole in it where the two floors fight.

    Depth is the shallower of the two axis overlaps -- how far one shell reaches
    into the other. Past `tolerance` that is broken geometry and blocks; under it
    the shells are touching, which is a terrace rather than a fault, and is
    reported as minor so the row can still be tightened deliberately.
    """
    rects = []
    for bdef in site_spec.get("buildings") or []:
        rect = rotated_footprint(bdef)
        if rect is not None:
            rects.append((str(bdef.get("id", "?")), rect))

    out = []
    for i, (aid, a) in enumerate(rects):
        for bid, b in rects[i + 1:]:
            wide = min(a[2], b[2]) - max(a[0], b[0])
            deep = min(a[3], b[3]) - max(a[1], b[1])
            if wide <= 0.0 or deep <= 0.0:
                continue
            depth = min(wide, deep)
            if depth > tolerance:
                out.append(_finding(
                    CODE_OVERLAP, "blocker",
                    f"buildings {aid} and {bid} occupy the same ground: "
                    f"{aid} spans x {a[0]:g}..{a[2]:g}, y {a[1]:g}..{a[3]:g} and "
                    f"{bid} spans x {b[0]:g}..{b[2]:g}, y {b[1]:g}..{b[3]:g}, "
                    f"reaching {depth:.1f} m into each other. Widen the row "
                    f"spacing or shrink the shells -- one of these walls is "
                    f"standing inside the other's rooms"))
            else:
                out.append(_finding(
                    CODE_OVERLAP, "minor",
                    f"buildings {aid} and {bid} touch ({depth:.2f} m of "
                    f"overlap); intentional terracing reads this way, so it is "
                    f"reported rather than gated"))
    return out


def hole_findings(rect, holes):
    """Findings for ground holes the plate does not contain.

    `_ground_tiles` used to intersect each hole with the plate, so a hole
    entirely outside vanished and a hole half outside came back half the size,
    both without a word. After `resolve` this list is empty; it stays a gate
    because the alternative is trusting that it is.
    """
    out = []
    for i, hole in enumerate(holes or []):
        if rect is None or not contains_rect(rect, hole):
            out.append(_finding(
                CODE_HOLE_OUTSIDE, "blocker",
                f"ground hole {i} at ({hole[0]:g}, {hole[1]:g})-"
                f"({hole[2]:g}, {hole[3]:g}) is not inside the ground plate; "
                f"cutting it would open a void the site never fills"))
    return out
