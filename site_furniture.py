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

import math

import site_cover

#: (species, width, depth, height) in the species' own frame, and the rule
#: that places it. Dims are the Zoo genomes' defaults.
#:   streetlight: one every 25 m (IES RP-8 residential spacing is 25-30 m
#:                at 8-9 m mounting; Zoo's lamp is 6 m, so the low end)
#:   fire_hydrant: one at each crossing, 2.5 m past the cut on the far side
#:                 (hydrants stand at corners, clear of the crosswalk)
#:   litter_bin:   one at each crossing, 1.5 m before the cut (where people
#:                 wait to cross)
#:   sign_post:    one at each crossing, at the cut's near edge -- the blank
#:                 blade, never a stop sign: a footpath is not an approach
#:                 (docs/STREET_RULES.md) -- and one before the bus shelter
#:                 (the stop's flag)
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
    # THE 1990s AMERICAN STREET (Zoo 0.72.0). Dims are each genome's
    # defaults; the traffic signal's width is its whole reach, mast arm
    # tip to luminaire tip, with the pole at the middle of it.
    "stop_sign": (0.75, 0.08, 2.85),
    "traffic_signal": (8.0, 0.62, 6.5),
    "mailbox": (0.6, 0.7, 1.15),
    "newspaper_box": (0.42, 0.45, 1.15),
    "parking_meter": (0.22, 0.14, 1.35),
    "payphone": (0.75, 0.5, 2.3),
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
#: The signal is 8 m of arm about one pole, and its slot's box would lie
#: across the carriageway. What a body meets is the pole.
FOOTPRINT["traffic_signal"] = (0.7, 0.7)

#: Where the 1990s kit stands, and why.
#:   traffic_signal: on the corner of a signalised junction (a yielding
#:                   road meets an arterial, `site_streets.approaches`),
#:                   pole on the yielding leg's right-hand kerb, mast arm
#:                   over the road it meets
#:   stop_sign:      one per stop-controlled approach, placed by
#:                   docs/STREET_RULES.md (MUTCD): on the kerb to the
#:                   approaching driver's RIGHT, the plate's near edge at
#:                   least `STOP_LATERAL_MIN` from the pavement edge,
#:                   `STOP_BEFORE_CROSSWALK` before the leg's crosswalk and
#:                   no more than `STOP_MAX_FROM_JUNCTION` from the crossing
#:                   road's travelled way, the plate facing the driver; a
#:                   second on the left only on a multi-lane approach. No
#:                   stop sign stands at a signalised junction, and none at
#:                   a footpath crossing.
#:   parking_meter:  one per parking bay, near the kerb edge -- a row of
#:                   single-space meters is half of what dates a street
#:   mailbox,
#:   newspaper_box,
#:   payphone:       at the bus stop, where people already stand
#: 4 ft before the marked crosswalk's painted near line
#: (`site_streets.Approach.line`); on a leg the paint does not mark, before
#: the junction box's edge.
STOP_BEFORE_CROSSWALK = 1.2
#: 50 ft: the furthest a stop sign stands from the intersecting travelled
#: way. A sign that cannot find room inside it is not placed, and said.
STOP_MAX_FROM_JUNCTION = 15.2
#: 6 ft, from the pavement edge (the kerb face) to the plate's NEAR edge.
#: The plate stands across the road to face the driver, so the post is half
#: a plate further out: a 3 m band holds it on the furniture line; a band
#: narrower than `STOP_LATERAL_MIN` plus a plate cannot, and the sign
#: stands as far out as the band holds and the shortfall is reported.
STOP_LATERAL_MIN = 1.83
STOP_SEARCH_STEP = 0.5    # a blocked station steps back up the leg by this
#: A mast-arm pole stands ON the corner: measured on cold run 9035's site,
#: a 2.2 m setback left the arm's tip over the sidewalk instead of over
#: the near lane, because the arm must cross the setback and the band
#: before it reaches the carriageway at all.
SIGNAL_SETBACK = 0.4
METER_INSET = 0.35        # centre of a meter, in from the band's kerb edge
STOP_PAIR = 1.1           # daylight between two news racks
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


def plate_facing(yaw_deg: float) -> tuple:
    """The plan direction a Zoo blade's face points when its slot carries
    ``yaw_deg``.

    MEASURED, not recalled. `lot._godot_transform` writes the text
    `Transform3D(c, 0, s, 0, 1, 0, -s, 0, c, ...)`, and Godot 4.7 parses those
    twelve numbers as basis ROWS (`str_to_var` on that text, 2026-09-13: at
    30 degrees local +X lands on world (0.866, 0, -0.5) and local +Z on
    (0.5, 0, 0.866)). With plan = Godot (x, -z) that is a counterclockwise
    plan rotation by the yaw. Zoo's `stop_sign` hangs its face toward
    Blender -Y, which the Y-up glTF export makes local +Z, so the face
    points plan `(sin yaw, -cos yaw)`.

    `lot.sign_facing` is a different conversion for a different writer (the
    shop sign's Godot-authored cabinet) and is not this one."""
    r = math.radians(yaw_deg)
    return (math.sin(r), -math.cos(r))


def _facing_driver(travel: int) -> float:
    """The yaw, relative to the road's own angle, that turns a blade's face
    back down the road toward a driver travelling ``travel``: the face must
    point along ``-travel * along``, and `plate_facing(angle - 90)` is
    ``-along`` while `plate_facing(angle + 90)` is ``+along``."""
    return -90.0 if travel > 0 else 90.0


def _say(findings, text):
    if findings is not None:
        findings.append(text)


def _stop_sign(name, road, ap, side, markers, placed, findings):
    """One stop sign for approach ``ap`` on ``side``'s kerb of ``road``, or
    None (and a finding) when no station within the rules holds it."""
    kerb = road.kerb(side)
    w, d, _h = SPECIES["stop_sign"]
    # LATERAL: the post on the furniture line when that keeps the plate's
    # near edge STOP_LATERAL_MIN off the pavement; else as far out as the
    # plate still stands over the band, and the shortfall said
    need = STOP_LATERAL_MIN + w / 2.0
    into = road.sidewalk - BAND_INSET
    if into < need:
        into = max(into, min(need, road.sidewalk - w / 2.0))
    offset = kerb.sign * (road.width / 2.0 + into)
    who = (f"road {road.index}'s {'+t' if ap.travel > 0 else '-t'} approach to "
           f"road {ap.crosser} ({side} kerb)")
    if into - w / 2.0 < STOP_LATERAL_MIN - 1e-9:
        _say(findings,
             f"LOT_STOP_SIGN_OFFSET_SHORT: the stop sign on {who} stands "
             f"{into - w / 2.0:.2f} m from the pavement edge to its plate, "
             f"under the {STOP_LATERAL_MIN} m the rule asks, because the "
             f"sidewalk band is {road.sidewalk:g} m; a band of "
             f"{STOP_LATERAL_MIN + w:.2f} m or more holds it.")
    # ALONG: STOP_BEFORE_CROSSWALK before the leg's crosswalk, stepping back
    # up the leg past a dropped kerb, a painted crosswalk (a sign beside a
    # mid-block crosswalk reads as that crosswalk's), a piece or a marker,
    # never further than STOP_MAX_FROM_JUNCTION from the crossing road's
    # travelled way. The plate is turned across the road, so its along-road
    # half is its depth's.
    import site_streets
    half = d / 2.0
    same_band = [p for p in placed if p["road"] == road.index and p["kerb"] == side]
    walks = site_streets.painted_walks(road)
    t0 = ap.line - ap.travel * STOP_BEFORE_CROSSWALK
    step = 0
    while True:
        t = t0 - ap.travel * step * STOP_SEARCH_STEP
        step += 1
        if ap.travel * (ap.edge - t) > STOP_MAX_FROM_JUNCTION + 1e-9:
            break
        if not road.slab[0] + half <= t <= road.slab[1] - half:
            break
        if any(g0 - half < t < g1 + half for g0, g1 in road.gaps + walks):
            continue
        if not (_clear_of_cuts(t, half, kerb) and _free(t, half, same_band)):
            continue
        piece = _piece(name, "stop_sign", road, kerb, t, offset,
                       _facing_driver(ap.travel), breaks=f"junction@{ap.station:.1f}")
        if _clear_of_markers(piece, markers):
            return piece
    _say(findings,
         f"LOT_STOP_SIGN_NO_ROOM: no station on {who} within "
         f"{STOP_MAX_FROM_JUNCTION} m of the crossing road holds a stop sign "
         f"clear of the dropped kerbs, the pieces and the markers; the "
         f"approach has none.")
    return None


def plan_traffic_control(road, roads_list, markers=(), findings=None,
                         placed=()) -> list:
    """The signal or the stop signs on every approach ``road`` makes to a
    junction (`site_streets.approaches`). ``placed`` are pieces already
    standing, which a stop sign keeps clear of; ``findings`` (a list of
    strings) hears about an approach whose control could not be stood by
    the rules."""
    import site_streets
    out = []
    mine = [ap for ap in site_streets.approaches(roads_list) if ap.road == road.index]
    for j, ap in enumerate(mine):
        if ap.control == "through" or (ap.control == "signal" and not ap.minor):
            # the through road keeps its right of way; at a signal, the
            # pole on the yielding leg's corner carries the arm over it
            continue
        side = site_streets.right_side(ap.travel)
        tag = "" if len(mine) == 1 else f"_{j}"
        if not road.sidewalk:
            _say(findings,
                 f"LOT_TRAFFIC_CONTROL_NO_BAND: road {road.index}'s "
                 f"{'+t' if ap.travel > 0 else '-t'} approach to road "
                 f"{ap.crosser} is under a {ap.control} and has no sidewalk "
                 f"band to stand it on; nothing is placed.")
            continue
        kerb = road.kerb(side)
        if ap.control == "signal":
            # the pole on the corner, the mast arm reaching over the road
            # it meets -- which is the direction of the mouth
            pole_t = ap.mouth - ap.travel * SIGNAL_SETBACK
            offset = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - BAND_INSET)
            yaw_extra = 0.0 if ap.travel > 0 else 180.0
            piece = _piece(f"Signal_{road.index}{side}{tag}", "traffic_signal", road,
                           kerb, pole_t, offset, yaw_extra,
                           breaks=f"junction@{ap.station:.1f}")
            if _clear_of_markers(piece, markers):
                out.append(piece)
            continue
        # a stop: the right-hand sign, and a left-hand one on a multi-lane
        # approach, where a driver in the far lane could miss the right
        sides = [side]
        if site_streets.approach_lanes(road) >= 2:
            sides.append("L" if side == "R" else "R")
        for s in sides:
            piece = _stop_sign(f"Stop_{road.index}{s}{tag}", road, ap, s, markers,
                               list(placed) + out, findings)
            if piece is not None:
                out.append(piece)
    return out


def plan_meters(road, markers=()) -> list:
    """A single-space meter at every parking bay, near the kerb edge."""
    import site_streets
    out = []
    for bay in site_streets.bays(road):
        kerb = road.kerb(bay["side"])
        w, d, h = SPECIES["parking_meter"]
        t = (bay["t0"] + bay["t1"]) / 2.0
        offset = kerb.offset - kerb.sign * (road.sidewalk / 2.0 - METER_INSET)
        piece = _piece(f"Meter_{road.index}{bay['side']}{bay['index']}",
                       "parking_meter", road, kerb, t, offset, 90.0,
                       breaks=f"bay {bay['side']}{bay['index']}")
        if _clear_of_markers(piece, markers):
            out.append(piece)
    return out


def plan_furniture(roads_list, buildings=(), markers=(), findings=None) -> list:
    """Pieces along every sidewalk band, as site-cover-shaped records with a
    ``base`` of ``sidewalk`` (the module stands on the band's top, not the
    plate; the caller resolves the height). ``buildings`` are the spec's,
    read only for which kerb they face; ``markers`` the mission points
    every piece keeps clear of (a lamp or a tree steps along its band, a
    corner piece or a bus stop is skipped); ``findings`` (a list of
    strings) hears about a junction approach whose control could not be
    stood by the rules. Returns the list; the caller extends the spec and
    the slots."""
    out = []
    n = 0
    markers = [tuple(m) for m in markers]
    # A STREET PLANTS A DIFFERENT TREE ON THE CROSS STREET. `tree_for` is
    # a hash of one road, so on a two-road site it draws the same species
    # about one time in five -- cold run 9035 was one of those, and a
    # junction where the avenue and the side street are the same tree is
    # the one place the difference would be seen. Each road takes its own
    # hash unless a road already planted has it, and then the next
    # unplanted species along.
    planted, species_for = [], {}
    for road in roads_list:
        pick = tree_for(road)
        if pick in planted and len(planted) < len(TREES):
            i = TREES.index(pick)
            for step in range(1, len(TREES)):
                nxt = TREES[(i + step) % len(TREES)]
                if nxt not in planted:
                    pick = nxt
                    break
        planted.append(pick)
        species_for[road.index] = pick
    for road in roads_list:
        # THE JUNCTION'S CONTROL FIRST. A stop sign's station is set by the
        # rules to within a metre or two, and a lamp's is not: the lamp
        # steps along its band, so it is the lamp that steps. Asked before
        # the band test so a road with no band says what it could not stand.
        control = plan_traffic_control(road, roads_list, markers, findings)
        if not road.sidewalk:
            continue
        species_tree = species_for[road.index]
        for kerb in road.kerbs:
            # this band's pieces, for `_free`, starting with its control
            placed = [p for p in control if p["kerb"] == kerb.side]
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
                # A CUT IS NEVER AN APPROACH. From 0.68.1 to 0.69.3 a cut
                # 3.5 m or wider was read as a driveway and given a stop
                # sign, and Level Factory's door spurs are 4 m: every door
                # path on cold runs 9046, 9048 and 9049 carried one, a path
                # crossing both kerbs carried a pair, and the side street's
                # own kerbs, cut by the road it meets, carried a pair inside
                # a signalised junction. Measured with
                # tools/probe_street_control.py. A stop sign belongs to a
                # junction approach (`plan_traffic_control`); the corner of
                # a cut keeps the blank blade, whatever its width.
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
                out.extend(_stop_corner(road, kerb, stop, placed, markers))
        # a meter at every bay
        out.extend(plan_meters(road, markers))
    return out


def _stop_corner(road, kerb, stop, placed, markers=()):
    """The mailbox, the news racks and the payphone, at the bus stop --
    where a 1990s street put them because it is where people already
    stand. Nothing is placed when there is no stop."""
    if not stop:
        return []
    shelter = stop[0]
    outer = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - BAND_INSET)
    base = shelter["t"] - SPECIES["bus_shelter"][0] / 2.0
    out = []
    for species, dt, yaw_extra in (("mailbox", -2.6, 0.0),
                                   ("newspaper_box", -4.0, 0.0),
                                   ("newspaper_box", -4.0 - STOP_PAIR, 0.0),
                                   ("payphone", -6.4, 180.0)):
        w, d, h = SPECIES[species]
        t = base + dt
        if not 0.5 < t < road.length - 0.5:
            continue
        # stepped along the band like a lamp: a corner where a lamp or a
        # tree already stands should move the mailbox, not delete it
        piece = _nudged(
            lambda s, species=species, yaw_extra=yaw_extra: _piece(
                f"{species}_{road.index}{kerb.side}{len(out)}", species, road,
                kerb, s, outer, yaw_extra, breaks=f"stop@{shelter['t']:.1f}"),
            t, max(w, d) / 2.0, kerb, placed, markers)
        if piece is not None:
            placed.append(piece)
            out.append(piece)
    return out
