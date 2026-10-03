"""
site_dumpsters.py  --  a dumpster at each building's service side
================================================================
The walker, 2026-10-03: "we should have some trash dumpsters next to
buildings (sides or back where its not in the way of where customers would
naturally walk into the building)". Zoo 1.58.0 builds the container; this
decides where one stands.

ONE A BUILDING, AGAINST A WALL THAT IS NOT A STREET FACE. A commercial
building's dumpster lives where the truck can reach it and the customer
does not look: round the back, or down a side. So:

  * a wall is a STREET FACE when a road's band lies in front of it within
    `FRONT_REACH`, and no dumpster stands against one;
  * the BACK -- the wall opposite the nearest road -- is tried first, then
    the remaining walls in an order the building's own id picks, so a row
    of buildings does not put every dumpster on its east side;
  * along the wall it stands toward a CORNER (which one, the id picks),
    stepping in from it until it is clear: `DOOR_CLEAR` along the wall from
    any way in, `WINDOW_CLEAR` from any other ground opening, a body's
    width from every entry's approach point, off every path and walk, off
    every road band, clear of the other buildings, of what already stands
    and of the mission's markers, and on the plate;
  * its back is `WALL_GAP` off the wall and its front -- the low edge, the
    sticker, the side a body walks up to -- faces away from the building.

A building with no wall that takes one is said (`LOT_DUMPSTER_NO_ROOM`) and
gets none: a dumpster in a doorway is worse than no dumpster.

Site space: plan (x, y), metres; Godot is (x, -y). A piece's ``yaw`` is the
slot's `rot_y`, degrees counter-clockwise in plan, and a Zoo prop's front
(-Y in its own frame) points to plan -y at yaw 0, so the yaw that turns the
front to face a wall's outward normal (nx, ny) is atan2(nx, -ny).
"""
from __future__ import annotations
import math
import zlib

SPECIES = "dumpster"
#: The genome's default: a 3-yard front-load container (Zoo 1.58.0).
DIMS = (1.83, 1.1, 1.3)
#: The haulers Zoo paints (`dumpster_forms.HAULERS`); the building's id picks.
VARIANTS = 4

#: Daylight between the container's back and the wall, in metres: the lids
#: swing up and back, and nothing is built flush to brick.
WALL_GAP = 0.25
#: From the wall's end to the container's near side, and the step it moves
#: in by when a station is not clear.
CORNER_IN = 0.6
STEP = 1.0
#: Along the wall, from the edge of a way in (a door, a garage, a breach) to
#: the container's near side. A body is 0.7 m wide (`agent_contract.json`)
#: and a door swings a metre; 2.5 m leaves the approach and a handcart's
#: turn clear. Chosen, not derived: it has not been walked.
DOOR_CLEAR = 2.5
#: ...and from any other ground opening: enough not to stand under a window.
WINDOW_CLEAR = 0.5
#: From an entry's approach point (`site_enterability`, 1.5 m out from the
#: door) to the container's footprint: the gate's own staging depth.
APPROACH_CLEAR = 1.5
#: A wall is a street face when a road's band lies in front of it within
#: this, in metres. Level Factory stands a face `FRONTAGE` 2 m from its
#: sidewalk and a gas station's forecourt put one 15 m back on cold run
#: 9139; 30 m covers both and stops short of the next block.
FRONT_REACH = 30.0
#: Clearances from what else is on the site.
GAP = 0.3
EDGE = 0.5

_WALLS = (("S", (0.0, -1.0)), ("N", (0.0, 1.0)), ("E", (1.0, 0.0)), ("W", (-1.0, 0.0)))


def _h(*k):
    return zlib.crc32(",".join(str(v) for v in k).encode("utf-8")) & 0xFFFFFFFF


def _overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _grow(r, m):
    return (r[0] - m, r[1] - m, r[2] + m, r[3] + m)


def _openings(site_spec, merged):
    """{building id: [((x, y), (nx, ny), half width, is a way in)]} for every
    storey-0 exterior opening, in site space."""
    import site_enterability as SE
    placements = {b["id"]: b for b in merged.get("buildings", []) or []}
    out = {bid: [] for bid in placements}
    for op in merged.get("openings", []) or []:
        bid = op.get("building")
        if bid not in placements:
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
        out[bid].append(((ex + at[0], ey + at[1]), (nx, ny),
                         float(op.get("width") or 1.0) / 2.0, bool(SE._opening_is_entry(op))))
    return out


def _wall_line(rect, side):
    """(start (x, y), along (ux, uy), length) of a footprint rect's wall."""
    x0, y0, x1, y1 = rect
    if side == "S":
        return (x0, y0), (1.0, 0.0), x1 - x0
    if side == "N":
        return (x0, y1), (1.0, 0.0), x1 - x0
    if side == "E":
        return (x1, y0), (0.0, 1.0), y1 - y0
    return (x0, y0), (0.0, 1.0), y1 - y0


def _road_side(rect, n, road):
    """How far in front of the wall with outward normal `n` this road's band
    begins, or None when the road is not in front of that wall."""
    cx, cy = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
    hx, hy = (rect[2] - rect[0]) / 2.0, (rect[3] - rect[1]) / 2.0
    vx, vy = cx - road.a[0], cy - road.a[1]
    t = vx * road.along[0] + vy * road.along[1]
    off = vx * road.perp[0] + vy * road.perp[1]
    half_along = abs(hx * road.along[0]) + abs(hy * road.along[1])
    if t < -half_along or t > road.length + half_along:
        return None                                 # the road ends before the building
    to_road = (-road.perp[0], -road.perp[1]) if off > 0 else road.perp
    if n[0] * to_road[0] + n[1] * to_road[1] < 0.7:
        return None
    half_across = abs(hx * road.perp[0]) + abs(hy * road.perp[1])
    return abs(off) - half_across - (road.width / 2.0 + float(road.sidewalk or 0.0))


def _in_band(rect, road, margin=GAP):
    half = road.width / 2.0 + float(road.sidewalk or 0.0) + margin
    for x, y in ((rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3]),
                 ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0)):
        vx, vy = x - road.a[0], y - road.a[1]
        t = vx * road.along[0] + vy * road.along[1]
        off = vx * road.perp[0] + vy * road.perp[1]
        if -margin <= t <= road.length + margin and abs(off) <= half:
            return True
    return False


def wall_order(bid, rect, roads_list):
    """The walls a dumpster may stand against, best first: the back, then
    the others, never a street face. ``[]`` when every wall is one."""
    street, nearest = set(), None
    for side, n in _WALLS:
        for road in roads_list:
            gap = _road_side(rect, n, road)
            if gap is None or gap > FRONT_REACH:
                continue
            street.add(side)
            if nearest is None or gap < nearest[0]:
                nearest = (gap, side)
    opposite = {"S": "N", "N": "S", "E": "W", "W": "E"}
    rest = [s for s, _n in _WALLS if s not in street]
    rest.sort(key=lambda s: _h("wall", bid, s))
    if nearest is not None and opposite[nearest[1]] in rest:
        back = opposite[nearest[1]]
        rest = [back] + [s for s in rest if s != back]
    return rest


def plan_dumpsters(site_spec, merged, roads_list, markers=(), standing=(), keep_out=(),
                   ground=None, findings=None):
    """One `dumpster` per building, as cover pieces. ``standing`` and
    ``keep_out`` are plan rects (what already stands; paths and walks),
    ``ground`` the plate's rect, ``markers`` the mission's points. A building
    with no clear station is said into ``findings``."""
    import site_enterability as SE
    import site_extent
    import site_furniture
    w, d, h = DIMS
    openings = _openings(site_spec, merged)
    approaches = [ap for rows in SE._approach_points(site_spec, merged).values() for (_e, ap, _w) in rows]
    rects = {}
    for b in site_spec.get("buildings", []) or []:
        r = site_extent.rotated_footprint(b)
        if r is not None:
            rects[b["id"]] = r
    placed, taken = [], list(standing)
    for b in site_spec.get("buildings", []) or []:
        bid = b["id"]
        rect = rects.get(bid)
        if rect is None or float(b.get("rot", 0) or 0) % 90 != 0:
            _say(findings, f"LOT_DUMPSTER_NO_ROOM: {bid} has no footprint this can read, or stands "
                           "off the right angles; no dumpster")
            continue
        piece = None
        for side in wall_order(bid, rect, roads_list):
            n = dict(_WALLS)[side]
            (sx0, sy0), (ux, uy), length = _wall_line(rect, side)
            lo, hi = CORNER_IN + w / 2.0, length - CORNER_IN - w / 2.0
            if hi < lo:
                continue
            steps = int((hi - lo) / STEP) + 1
            from_start = [lo + k * STEP for k in range(steps)]
            from_end = [hi - k * STEP for k in range(steps)]
            first, second = (from_start, from_end) if _h("end", bid, side) % 2 == 0 else (from_end, from_start)
            # nearest a corner first, either corner, the id's corner leading
            stations = [s for pair in zip(first, second) for s in pair][:steps]
            on_wall = [(((ox - sx0) * ux + (oy - sy0) * uy), hw, entry)
                       for (ox, oy), (onx, ony), hw, entry in openings.get(bid, [])
                       if onx * n[0] + ony * n[1] > 0.9]
            for s in stations:
                if any(abs(s - u) - w / 2.0 - hw < (DOOR_CLEAR if entry else WINDOW_CLEAR)
                       for u, hw, entry in on_wall):
                    continue
                cx = sx0 + ux * s + n[0] * (WALL_GAP + d / 2.0)
                cy = sy0 + uy * s + n[1] * (WALL_GAP + d / 2.0)
                px, py = (w, d) if side in ("S", "N") else (d, w)
                r = (cx - px / 2.0, cy - py / 2.0, cx + px / 2.0, cy + py / 2.0)
                if ground is not None and not (ground[0] + EDGE <= r[0] and r[2] <= ground[2] - EDGE
                                               and ground[1] + EDGE <= r[1] and r[3] <= ground[3] - EDGE):
                    continue
                if any(_overlap(r, _grow(o, GAP)) for oid, o in rects.items() if oid != bid):
                    continue
                if any(_overlap(r, k) for k in keep_out):
                    continue
                if any(_overlap(r, _grow(t, GAP)) for t in taken):
                    continue
                if any(_in_band(r, road) for road in roads_list):
                    continue
                grown = _grow(r, APPROACH_CLEAR)
                if any(grown[0] <= ax <= grown[2] and grown[1] <= ay <= grown[3] for ax, ay in approaches):
                    continue
                cand = {"name": f"Dumpster_{bid}", "species": SPECIES,
                        "at": [round(cx, 3), round(cy, 3)],
                        "yaw": round(math.degrees(math.atan2(n[0], -n[1])) % 360.0, 3),
                        "dims": [w, d, h], "size": [px, h, py], "base": "plate",
                        "variant": _h("hauler", bid) % VARIANTS,
                        "building": bid, "wall": side,
                        "source": "site_dumpsters", "breaks": f"service side of {bid}"}
                if not site_furniture._clear_of_markers(cand, markers):
                    continue
                piece = cand
                break
            if piece is not None:
                break
        if piece is None:
            _say(findings, f"LOT_DUMPSTER_NO_ROOM: no clear station for a dumpster against {bid}'s "
                           "back or sides")
            continue
        placed.append(piece)
        px, _h_, py = piece["size"]
        taken.append((piece["at"][0] - px / 2.0, piece["at"][1] - py / 2.0,
                      piece["at"][0] + px / 2.0, piece["at"][1] + py / 2.0))
    return placed


def _say(findings, text):
    if findings is not None:
        findings.append(text)
