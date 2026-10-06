"""The fence at the playable edge (Lot 0.97.0).

The walker, 2026-10-04, on the fenced vacant lot in
`docs/findings/backdrop_mock/` at the factory root: "I like the idea of a
fence between playable areas and non playable areas, thats good feedback to
the player" -- a fence wherever playable ground meets an Empty's back, a
vacant lot or the backdrop. Zoo's `chain_link_fence` (1.77.0) is the fence:
posts, a top rail and a see-through fabric, in two draws a run.

PHASE ONE: AN EMPTY ROW'S GAPS. The Empties stand in rows across the street
with their doors shut (Level Factory 0.143.0) and their backs to the plate's
edge. Every gap a body fits through between two of them, and from each end of
a row to the plate's edge, is a way behind the row onto ground nothing was
built for. Cold run 9180's row had three: a 3 m alley between two houses, and
4 m and 12.5 m at its ends. A fence closes each, along the row's front line,
so from the street the row reads as one frontage with its alleys gated.

WHAT A BODY FITS THROUGH is the contract's, and it is the PLAYER's capsule
(`characters.player.radius_m`, twice), the caller's to pass. The navmesh's own
narrowest gap is wider (`site_cover.min_passable_gap`): a gap between the two
is one a player squeezes through and a QA walker cannot, so it is exactly the
one the walk tests would never report.

THE FRONT LINE is the row's long edge nearer a road: Empties face their
street. A row with no road on the site faces the plate's centre.

NEVER ACROSS A WAY. A run is cut back from the open end at the first thing it
would cross -- a road and its sidewalks, a path's corridor, a building -- and
dropped if what is left is narrower than a body or stands on a mission
marker. Each such run is said (`LOT_FENCE_SKIPPED`), never forced.
"""
from __future__ import annotations

import math

import site_extent
import site_streets

SPECIES = "chain_link_fence"
#: Zoo's terminal post (`chain_link_fence_forms.TERMINAL_OD`): the module's
#: depth, so the slot is exactly what stands.
DEPTH = 0.0603
#: 6 ft fabric, the commercial default (the genome's default height).
HEIGHT = 1.83
#: Two Empties whose front lines differ by less than this stand in one row.
ROW_TOL = 0.5
#: A run's length is quantised to the centimetre, the unit Zoo names a module
#: by (`..._w<cm>`), so two gaps a hair apart share one module.
QUANTUM = 0.01


def _say(findings, msg):
    if findings is not None:
        findings.append(msg)


def _overlaps(a, b) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > 1e-6
            and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6)


def empties(site_spec) -> list:
    """``[(id, rect, axis)]`` for every Empty: its plan rect by the ground's
    own rule (`site_extent.content` reads a blocker's `size_x`/`size_y` as
    world extents), and the axis its row runs along -- 0 (x) for a house
    facing +-y, 1 (y) for one facing +-x."""
    out = []
    for i, bk in enumerate(site_spec.get("blockers") or []):
        if not bk.get("empty"):
            continue
        at = bk.get("at")
        if not at:
            continue
        rect = site_extent.rect_of(float(at[0]), float(at[1]),
                                   float(bk.get("size_x", 12.0) or 12.0),
                                   float(bk.get("size_y", 12.0) or 12.0))
        rot = (float(bk.get("rot", 0) or 0) % 360 + 360) % 360
        axis = 1 if int(round(rot)) % 180 == 90 else 0
        out.append((str(bk.get("id", f"blocker_{i}")), rect, axis))
    return out


def rows(site_spec) -> list:
    """The Empties grouped into rows: ``[(axis, [(id, rect), ...])]``, each
    row sorted along its axis. Two Empties are in one row when they run the
    same way and their depth extents agree within `ROW_TOL` at both edges."""
    other = {0: (1, 3), 1: (0, 2)}           # the rect's depth edges per axis
    groups = []
    for eid, rect, axis in sorted(empties(site_spec),
                                  key=lambda e: (e[2], e[1][other[e[2]][0]])):
        lo, hi = other[axis]
        for g in groups:
            if g[0] != axis:
                continue
            ref = g[1][-1][1]
            if abs(ref[lo] - rect[lo]) <= ROW_TOL and abs(ref[hi] - rect[hi]) <= ROW_TOL:
                g[1].append((eid, rect))
                break
        else:
            groups.append((axis, [(eid, rect)]))
    return [(axis, sorted(members, key=lambda m: m[1][axis]))
            for axis, members in groups]


def _seg_dist(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    n = dx * dx + dy * dy
    t = 0.0 if n == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / n))
    return math.hypot(p[0] - (ax + dx * t), p[1] - (ay + dy * t))


def front_line(axis, members, roads_list, ground=None):
    """``(coordinate, sign)``: the row's front edge on the depth axis, and
    +1 when the front faces up that axis (the fence's strip lies below it)."""
    lo_i, hi_i = (1, 3) if axis == 0 else (0, 2)
    lo = min(r[lo_i] for _e, r in members)
    hi = max(r[hi_i] for _e, r in members)
    mid = (min(r[axis] for _e, r in members) + max(r[axis + 2] for _e, r in members)) / 2.0

    def at(depth):
        return (mid, depth) if axis == 0 else (depth, mid)

    if roads_list:
        d_lo = min(_seg_dist(at(lo), r.a, r.b) for r in roads_list)
        d_hi = min(_seg_dist(at(hi), r.a, r.b) for r in roads_list)
    elif ground:
        centre = ((ground[0] + ground[2]) / 2.0, (ground[1] + ground[3]) / 2.0)
        d_lo = math.hypot(at(lo)[0] - centre[0], at(lo)[1] - centre[1])
        d_hi = math.hypot(at(hi)[0] - centre[0], at(hi)[1] - centre[1])
    else:
        return hi, +1
    return (hi, +1) if d_hi <= d_lo else (lo, -1)


def _strip(axis, s0, s1, front, sign):
    """The plan rect a run from ``s0`` to ``s1`` along the axis occupies,
    flush with the front line on the row's side of it."""
    d0, d1 = (front - DEPTH, front) if sign > 0 else (front, front + DEPTH)
    return (s0, d0, s1, d1) if axis == 0 else (d0, s0, d1, s1)


def _cut(axis, s0, s1, front, sign, keep_out, toward):
    """Run out from the house and stop at the first rect the run would cross.
    ``toward`` is the open end: -1 when it is ``s0`` (the run starts at the
    house at ``s1``), +1 when it is ``s1``, 0 for a gap between two houses,
    which is dropped whole if anything crosses it. Returns the surviving
    ``(s0, s1)`` or None."""
    hits = [k for k in keep_out if _overlaps(_strip(axis, s0, s1, front, sign), k)]
    if not hits:
        return s0, s1
    if toward == 0:
        return None
    lo_i, hi_i = (0, 2) if axis == 0 else (1, 3)
    if toward > 0:                            # open at s1: stop at the nearest hit
        s1 = min(k[lo_i] for k in hits)
    else:
        s0 = max(k[hi_i] for k in hits)
    if s1 - s0 <= 0:
        return None
    if any(_overlaps(_strip(axis, s0, s1, front, sign), k) for k in keep_out):
        return None
    return s0, s1


def _piece(name, axis, s0, s1, front, sign, breaks):
    length = round(math.floor((s1 - s0) / QUANTUM + 1e-6) * QUANTUM, 2)
    centre = (s0 + s1) / 2.0
    depth = front - sign * DEPTH / 2.0
    x, y = (centre, depth) if axis == 0 else (depth, centre)
    sx, sy = (length, DEPTH) if axis == 0 else (DEPTH, length)
    return {"name": name, "species": SPECIES, "at": [round(x, 3), round(y, 3)],
            "yaw": 0.0 if axis == 0 else 90.0,
            "dims": [length, DEPTH, HEIGHT], "size": [sx, HEIGHT, sy],
            "base": "plate", "source": "site_fences", "breaks": breaks}


def plan_fences(site_spec, roads_list, ground, body, keep_out=(), markers=(),
                findings=None) -> list:
    """The fences that close every Empty row's gaps and ends.

    ``ground`` is the plate's rect (the ends run to it); ``body`` the widest
    gap that is already closed, which the caller reads off the contract;
    ``keep_out`` what a run must never cross (path corridors, footprints:
    the roads' boxes are added here); ``markers`` the mission's points.
    """
    import site_furniture
    keep = list(keep_out) + [site_streets._road_box(r) for r in roads_list or []]
    # every blocker, Empty or not: a row's end run stops at another row's
    # houses. A gap's own two houses only touch its strip, which is no overlap.
    for bk in site_spec.get("blockers") or []:
        at = bk.get("at")
        if at:
            keep.append(site_extent.rect_of(float(at[0]), float(at[1]),
                                            float(bk.get("size_x", 12.0) or 12.0),
                                            float(bk.get("size_y", 12.0) or 12.0)))
    placed = []
    for r_ix, (axis, members) in enumerate(rows(site_spec)):
        front, sign = front_line(axis, members, roads_list, ground)
        # NEVER ENCLOSE A MARKER. Fenced, the band behind the row's front line
        # is shut off from the street; a marker standing there would be a
        # spawn, objective or enemy nobody can reach. Leave the row open and
        # say so rather than strand it.
        if ground:
            lo_i = 1 if axis == 0 else 0
            band = list(ground)
            if sign > 0:
                band[lo_i + 2] = front           # from the plate's edge up to the front
            else:
                band[lo_i] = front
            houses = [r for _e, r in members]
            stranded = [m for m in markers
                        if band[0] < m[0] < band[2] and band[1] < m[1] < band[3]
                        and not any(h[0] <= m[0] <= h[2] and h[1] <= m[1] <= h[3]
                                    for h in houses)]
            if stranded:
                _say(findings, f"LOT_FENCE_SKIPPED: row {r_ix} left open: a mission "
                               f"marker stands behind it at {tuple(stranded[0])}")
                continue
        runs = []
        for (a_id, a), (b_id, b) in zip(members, members[1:]):
            runs.append((a[axis + 2], b[axis], 0, f"between {a_id} and {b_id}"))
        if ground:
            first_id, first = members[0]
            last_id, last = members[-1]
            runs.append((ground[axis], first[axis], -1, f"row {r_ix}'s end beyond {first_id}"))
            runs.append((last[axis + 2], ground[axis + 2], +1, f"row {r_ix}'s end beyond {last_id}"))
        for k, (s0, s1, toward, breaks) in enumerate(runs):
            if s1 - s0 < body:
                continue                      # a body cannot pass: already closed
            kept = _cut(axis, s0, s1, front, sign, keep, toward)
            if kept is None:
                _say(findings, f"LOT_FENCE_SKIPPED: {breaks} would cross a road, a path "
                               f"or a building")
                continue
            s0, s1 = kept
            if s1 - s0 < body:
                continue                      # what is left is closed by the obstacle
            piece = _piece(f"Fence_{r_ix}_{k}", axis, s0, s1, front, sign, breaks)
            if not site_furniture._clear_of_markers(piece, markers):
                _say(findings, f"LOT_FENCE_SKIPPED: {breaks} stands on a mission marker")
                continue
            placed.append(piece)
    return placed
