"""The kerb line: what stands on a sidewalk between the crossings.

Roadmap 153, the second layer. A street reads as ordered when its furniture
says where cars and people go: a lamp at a spacing, a hydrant and a sign at
the corner, a bin where people wait. This module places them along each
sidewalk band of every road in `site_streets`, between the kerb cuts, as
PROP SLOTS -- the same record the cover planner writes, so the site kit
builds them, the themed site stands the modules where the boxes stood, and
the honesty rule is kept by construction: every piece is taller than the
step limit and carries collision.

The waiting places (roadmap 153, third layer): a tree in a grate halfway
between every two lamps, and one bus stop per road -- a shelter with a
bench inside it and a stop sign before it -- on the kerb the buildings
face, in the longest stretch between two crossings.

Placement is along the band's outer half (away from the road) so the kerb
edge stays clear for a body stepping off at a cut, and nothing is placed
inside a cut's span plus a clearance. Spacings are from practice, cited in
the table, and derived from nothing here -- they are what a Delco sidewalk
carries, not what a lane needs.

Frame: spec/Blender Z-up plan coordinates, like `site_streets`. Pure.
"""
from __future__ import annotations

import site_cover

#: (species, width, depth, height) in the species' own frame, and the rule
#: that places it. Dims are the Zoo genomes' defaults.
#:   streetlight: one every 25 m (IES RP-8 residential spacing is 25-30 m
#:                at 8-9 m mounting; Zoo's lamp is 6 m, so the low end)
#:   fire_hydrant: one at each crossing, 2.5 m past the cut on the far side
#:                 (hydrants stand at corners, clear of the crosswalk)
#:   litter_bin:   one at each crossing, 1.5 m before the cut (where people
#:                 wait to cross)
#:   sign_post:    one at each crossing, at the cut's near edge, facing the
#:                 road (a stop sign for the spur); and one before the bus
#:                 shelter (the stop's flag)
#:   the trees:    one halfway between each pair of lamps, in a grate on
#:                 the outer half of the band; its slot is the crown, and
#:                 WHICH tree is a property of the road (`tree_for`)
#:   bus_shelter:  one per road, on the kerb the buildings face, open side
#:                 to the road, in the longest stretch between crossings
#:   bench:        inside the shelter, against its back
SPECIES = {
    "streetlight": (0.7, 0.3, 6.0),
    "fire_hydrant": (0.35, 0.35, 0.75),
    "litter_bin": (0.6, 0.6, 1.0),
    "sign_post": (0.1, 0.1, 2.4),
    "bus_shelter": (3.0, 1.5, 2.5),
    "bench": (1.8, 0.5, 0.45),
    # THE FIVE STREET TREES (Zoo 0.71.0). Dims are each genome's defaults:
    # a young planting as a nursery lists it, so a callery pear is 3 m
    # across and a London plane 5 m. `street_tree` stays the generic one a
    # spec may still name.
    "street_tree": (4.0, 4.0, 6.0),
    "red_maple": (4.0, 4.0, 6.0),
    "pin_oak": (4.0, 4.0, 6.5),
    "honey_locust": (4.5, 4.5, 6.0),
    "london_plane": (5.0, 5.0, 6.5),
    "callery_pear": (3.0, 3.0, 5.5),
}

#: The trees a road may be planted with, in the order a hash picks from.
#: A street that plants one species per road reads as a street somebody
#: planned; five species scattered tree by tree reads as an arboretum.
TREES = ("red_maple", "pin_oak", "honey_locust", "london_plane", "callery_pear")
#: The plan footprint the GREYBOX box takes, where it is not the slot's.
#: A tree's slot is its crown -- the space it takes, and what Zoo builds
#: to -- but what a body meets is a trunk in a 1.2 m grate, so the box the
#: greybox draws and the navmesh carves is the grate's column. The greybox
#: over-blocks the trunk by the grate's margin and never under-blocks it;
#: the themed module's own collision is the trunk (Zoo `street_tree`).
FOOTPRINT = {t: (1.2, 1.2) for t in
             ("street_tree", "red_maple", "pin_oak", "honey_locust",
              "london_plane", "callery_pear")}
LAMP_SPACING = 25.0
LAMP_START = 5.0
TREE_OFFSET = LAMP_SPACING / 2.0    # a tree halfway between two lamps
CUT_CLEARANCE = 0.8       # a piece stays this far from a dropped kerb's span
BAND_INSET = 0.45         # centre of a piece, in from the band's outer edge
TREE_INSET = 0.7          # the grate's half plus a hand, so it sits on the band
SHELTER_INSET = 0.85      # the shelter's half depth plus a hand
BENCH_TOWARD_BACK = 0.35  # the bench's centre, from the shelter's, toward its back
SIGN_BEFORE_SHELTER = 1.0
PIECE_GAP = 0.3           # daylight between two pieces along the band
NUDGES = (0.0, 2.0, -2.0, 4.0, -4.0)   # a lamp or a tree steps along its band


def tree_for(road) -> str:
    """The species this road is planted with: a stable hash of its own
    endpoints, rounded to the metre. Keyed on the ROAD and not on its index
    so the avenue of one mission and the avenue of the next are not always
    the same tree, and keyed on nothing random so a spec plants the same
    street every run."""
    h = 2166136261
    for v in (road.a[0], road.a[1], road.b[0], road.b[1]):
        h = ((h ^ (int(round(float(v))) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return TREES[h % len(TREES)]


def _clear_of_cuts(t, half_along, kerb, clearance=CUT_CLEARANCE):
    lo, hi = t - half_along - clearance, t + half_along + clearance
    for t0, t1, is_cut in kerb.spans:
        if is_cut and not (hi <= t0 or lo >= t1):
            return False
    return True


def _free(t, half_along, placed, gap=PIECE_GAP):
    """No piece already on this band within ``gap`` along the road."""
    for p in placed:
        if abs(p["t"] - t) < half_along + p["along"] / 2.0 + gap:
            return False
    return True


def _nudged(make, t, half_along, kerb, placed, markers):
    """The piece ``make(t)`` at its station, or stepped along the band by
    `NUDGES` when a MARKER is in the way. A station over a dropped kerb is
    skipped, not nudged -- the spacing rule stays the spacing rule, and a
    marker is the one thing worth a step."""
    if not _clear_of_cuts(t, half_along, kerb):
        return None
    for dt in NUDGES:
        s = t + dt
        if not (_clear_of_cuts(s, half_along, kerb) and _free(s, half_along, placed)):
            continue
        piece = make(s)
        if _clear_of_markers(piece, markers):
            return piece
    return None


def _clear_of_markers(piece, markers) -> bool:
    """No mission marker within `site_cover.MARKER_CLEARANCE` of the piece's
    footprint edge -- the rule cover and the cars keep. Cold run 9030's
    third seed stood a lamp ON Enemy_4, and the preflight refused the
    candidate for an enemy inside solid geometry: the kerb line had never
    looked at the markers."""
    x, y = piece["at"]
    sx, _h, sy = piece["size"]
    rect = site_cover._grow((x - sx / 2.0, y - sy / 2.0, x + sx / 2.0, y + sy / 2.0),
                            site_cover.MARKER_CLEARANCE)
    return not any(site_cover._inside(tuple(m), rect) for m in markers)


def _piece(name, species, road, kerb, t, offset, yaw_extra=0.0, breaks=""):
    w, d, h = SPECIES[species]
    fw, fd = FOOTPRINT.get(species, (w, d))
    x, y = road.point(t, offset)
    yaw = (road.angle_deg + yaw_extra) % 360.0
    turned = int(round(yaw_extra)) % 180 == 90
    # plan footprint after the yaw, quantised the way cover is
    sx, sy = (fd, fw) if int(round(yaw)) % 180 == 90 else (fw, fd)
    return {"name": name, "species": species, "at": [round(x, 3), round(y, 3)],
            "yaw": round(yaw, 3), "dims": [w, d, h], "size": [sx, h, sy],
            "base": "sidewalk", "road": road.index, "kerb": kerb.side,
            "t": round(t, 3), "along": fd if turned else fw,
            "source": "site_furniture", "breaks": breaks}


def _facing_kerb(road, buildings):
    """The kerb on the side of the road the buildings stand on: the sign of
    the mean building offset from the centre line, in the road's frame.
    None when the spec has no buildings, or the road no kerbs."""
    if not buildings or not road.kerbs:
        return None
    px, py = road.perp
    ax, ay = road.a
    side = 0.0
    for b in buildings:
        bx, by = b.get("at", (0.0, 0.0))
        side += (float(bx) - ax) * px + (float(by) - ay) * py
    sign = 1 if side >= 0 else -1
    return next((k for k in road.kerbs if k.sign == sign), None)


def _bus_stop(road, kerb, placed, n, markers=()):
    """The stop as a set -- shelter, bench inside it, sign before it -- at
    the midpoint of the longest free stretch of ``kerb`` that holds it clear
    of the cuts and of what already stands; nudged along in 3 m steps when
    a lamp or a tree is in the way. Returns the pieces (possibly none)."""
    sw, sd, _sh = SPECIES["bus_shelter"]
    sign_w, sign_d, _ = SPECIES["sign_post"]
    outer = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - BAND_INSET)
    shelter_off = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - SHELTER_INSET)
    bench_off = shelter_off + kerb.sign * BENCH_TOWARD_BACK
    # the shelter's back (+y in its frame) toward the buildings: +perp on
    # the L kerb is the module's +y at yaw = the road's angle; the R kerb
    # turns it round
    back = 0.0 if kerb.sign > 0 else 180.0
    need = sw + SIGN_BEFORE_SHELTER + sign_d + 2.0 * CUT_CLEARANCE
    stretches = sorted(((t1 - t0, t0, t1) for t0, t1, is_cut in kerb.spans if not is_cut),
                       reverse=True)
    for span, t0, t1 in stretches:
        if span < need:
            continue
        mid = (t0 + t1) / 2.0
        for dt in (0.0, 3.0, -3.0, 6.0, -6.0, 9.0, -9.0):
            t = mid + dt
            sign_t = t - sw / 2.0 - SIGN_BEFORE_SHELTER
            lo, hi = sign_t - sign_d / 2.0, t + sw / 2.0
            if lo - CUT_CLEARANCE < t0 or hi + CUT_CLEARANCE > t1:
                continue
            if not (_free(t, sw / 2.0, placed) and _free(sign_t, sign_d / 2.0, placed)):
                continue
            tag = f"stop@{t:.1f}"
            pieces = [_piece(f"BusShelter_{n}", "bus_shelter", road, kerb, t, shelter_off,
                             back, breaks=tag),
                      _piece(f"Bench_{n + 1}", "bench", road, kerb, t, bench_off, back,
                             breaks=tag),
                      _piece(f"StopSign_{n + 2}", "sign_post", road, kerb, sign_t, outer,
                             90.0, breaks=tag)]
            if all(_clear_of_markers(p, markers) for p in pieces):
                return pieces
    return []


def plan_furniture(roads_list, buildings=(), markers=()) -> list:
    """Pieces along every sidewalk band, as site-cover-shaped records with a
    ``base`` of ``sidewalk`` (the module stands on the band's top, not the
    plate; the caller resolves the height). ``buildings`` are the spec's,
    read only for which kerb they face; ``markers`` the mission points
    every piece keeps clear of (a lamp or a tree steps along its band, a
    corner piece or a bus stop is skipped). Returns the list; the caller
    extends the spec and the slots."""
    out = []
    n = 0
    markers = [tuple(m) for m in markers]
    for road in roads_list:
        if not road.sidewalk:
            continue
        species_tree = tree_for(road)
        for kerb in road.kerbs:
            placed = []          # this band's pieces, for `_free`
            outer = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - BAND_INSET)
            tree_off = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - TREE_INSET)
            # lamps at a spacing, skipping the cuts, and a tree between each pair
            t = LAMP_START
            while t < road.length - LAMP_START:
                w, d, h = SPECIES["streetlight"]
                lamp = _nudged(lambda s: _piece(f"Lamp_{n}", "streetlight", road, kerb, s, outer),
                               t, d / 2.0, kerb, placed, markers)
                if lamp:
                    placed.append(lamp)
                    n += 1
                tt = t + TREE_OFFSET
                gw, gd = FOOTPRINT[species_tree]
                if tt < road.length - LAMP_START:
                    tree = _nudged(lambda s: _piece(f"Tree_{n}", species_tree, road, kerb, s, tree_off),
                                   tt, gw / 2.0, kerb, placed, markers)
                    if tree:
                        placed.append(tree)
                        n += 1
                t += LAMP_SPACING
            # per cut: a hydrant past it, a bin before it, a sign at its edge
            for c in sorted(kerb.cuts, key=lambda c: c.t):
                half = c.span / 2.0 + CUT_CLEARANCE
                # offsets are from the dropped kerb's EDGE, which already
                # carries CUT_CLEARANCE; `_clear_of_cuts` adds it again, so a
                # piece nearer than that to the edge is refused by design
                for species, dt, yaw_extra in (("fire_hydrant", half + 2.5, 0.0),
                                               ("litter_bin", -(half + 1.5), 0.0),
                                               ("sign_post", half + 1.0, 90.0)):
                    w, d, h = SPECIES[species]
                    tt = c.t + dt
                    if 0.5 < tt < road.length - 0.5 and _clear_of_cuts(tt, d / 2.0, kerb) \
                            and _free(tt, max(w, d) / 2.0, placed):
                        piece = _piece(f"{species}_{n}", species, road, kerb, tt,
                                       outer, yaw_extra, breaks=f"crossing@{c.t:.1f}")
                        if _clear_of_markers(piece, markers):
                            placed.append(piece)
                            n += 1
            out.extend(placed)
            # the bus stop, on the kerb the buildings face
            if kerb is _facing_kerb(road, buildings):
                stop = _bus_stop(road, kerb, placed, n, markers)
                n += len(stop)
                out.extend(stop)
    return out
