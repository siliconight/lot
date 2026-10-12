"""The pole line (factory roadmap 240): one kerb of every street carries wooden
utility poles, and the poles carry the street's lamps.

The walker's three Philly photographs (`docs/reference/PHILLY_STREET_COMPS.md`
at the factory root) put the overhead network in two of three frames -- a
wooden pole at the corner carrying a cobra-head, cobra-heads on poles along a
rowhouse street, wires overhead -- and Lot stood a steel lamp on both kerbs
every 25 m and not one pole. The walker's calls of 2026-10-12
(`docs/proposals/POLE_LINE_DESIGN.md`):

  * ONE SIDE, EVERY STREET: one line per street with a sidewalk, on the kerb
    with fewer dropped kerbs and shop bands to dodge (`pole_kerb`); a road's
    hash only breaks a tie;
  * A COBRA-HEAD ON EVERY POLE, and the poles ARE the street's lamps: the
    band roads stand no `streetlight` now, on either kerb. A lane keeps its
    own (`site_furniture.plan_lane_lamps`, 0.116.0) -- it has no band;
  * A TRANSFORMER CAN EVERY THIRD OR FOURTH POLE, on the pole the most
    buildings front (`_transformers`), never by jitter;
  * the full wire set without house drops -- drawn between these poles next.

WHERE A POLE STANDS. On the kerb side of the band: `POLE_INSET` from the kerb
face to its centre, the 18 in (0.46 m) a roadside obstruction keeps from the
face of a curb (AASHTO Roadside Design Guide) plus the pole's 0.15 m radius.
Not on `site_furniture`'s furniture line, 0.45 m from the band's BUILDING
edge: there the crossarm, reaching 1.22 m behind the pole at 10 m up, would
stand in a rowhouse's front wall. Here it stops 1.17 m short of the building
line on a 3 m band, and the cobra-head hangs 1.56 m over the near lane.

WHERE ITS SLOT STANDS. A pole record's ``at`` IS the pole: the greybox box,
the navmesh carve, the markers' clearance and a flyer's sleeve all mean the
column a body meets. Zoo's module is not centred on the pole -- the
cobra-head reaches 2.45 m toward the road and the crossarm 1.22 m away, and
`fit_exact` maps the drawing's bounds onto the slot -- so the record also
carries ``module_at``, the slot's centre, which `lot.write_site_slots` and the
scene writer stand the module at.

THE NUMBERS ZOO OWNS, mirrored: neither repo can import the other, so both pin
them to literals (`tests/test_site_poles.py` here, Zoo's
`test_the_numbers_lot_mirrors_are_these`), the way `site_furniture.BLADE_DIMS`
mirrors the sign blades.
"""
from __future__ import annotations

import math

import site_furniture as F

#: Zoo `core.utility_pole_forms.MODULE_DIMS`: (width, depth, height) in
#: metres, the slot each form asks for. `auto` is the pole as it stands;
#: `transformer` adds a pole-mount can (wider by the can).
POLE_DIMS = {"auto": (0.3, 3.67, 10.4), "transformer": (0.46, 3.67, 10.4)}
#: Zoo `POLE_AT`: where the pole's axis stands in its module, (x, y) from the
#: module's centre at grade, in the module's frame (-Y toward the road).
POLE_AT = {"auto": (0.0, 0.615), "transformer": (0.0, 0.615)}
#: Zoo `LENS_AT`: the cobra-head lens underside's centre, (y, z) about the
#: pole's axis at grade -- where the light hangs.
LENS_AT = (-2.171, 7.401)
#: Zoo `WIRES`: each wire's attachment on the pole, {name: (y, z)} about its
#: axis at grade; a span runs along the module's X, the line's direction.
WIRES = {"primary_0": (-1.07, 10.297), "primary_1": (-0.41, 10.297),
         "primary_2": (1.07, 10.297), "neutral": (0.24, 9.3),
         "secondary": (0.24, 7.95), "comm_0": (0.24, 6.4), "comm_1": (0.24, 6.0)}

#: What a body meets: the pole's column (Zoo's collision is the pole alone),
#: drawn by the greybox and carved by the navmesh at ``at``.
POLE_FOOTPRINT = (0.3, 0.3)
#: 0.46 m from the curb's face to the pole's face, and its 0.15 m radius.
POLE_INSET = 0.61
#: The longest span: US distribution practice is 100 to 150 ft on a street;
#: 118 ft keeps the lowest cable 5.3 m over a road at mid-span (Zoo's
#: `test_the_wires_stack_so_a_span_clears_the_road`) and the cobra-heads'
#: 14 m pools (Lux) about a span apart, pools with dark between.
POLE_SPAN = 36.0
#: How far a pole steps along its band off a dropped kerb, a marker, a piece,
#: a meter or a shop band: further than a lamp's 4 m, because a pole carries
#: the wires and a skipped pole doubles a span.
POLE_STEPS = (0.0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0, 4.0, -4.0, 5.0, -5.0, 6.0, -6.0)
#: A pole at the end of a run stands this far past the dropped kerb's edge,
#: on top of `site_furniture.CUT_CLEARANCE`: the corner pole.
END_GAP = 0.5
#: A building serves a pole when its centre lies within this of the road's
#: centre line, across, and within half a span along: a building that fronts
#: the street, its setback and its depth included (the kerb probe's stand
#: 42 to 44 m back).
SERVE_ACROSS = 50.0
#: The can goes on the 3rd or 4th pole after the last one that carried one.
CAN_EVERY = (3, 4)


def form_of(piece):
    """The pole's Zoo form: `transformer`, or `auto` for one with no can."""
    return piece.get("form") or "auto"


def _rotate(yaw_deg, mx, my):
    """A module-frame offset (mx, my) in plan metres at ``yaw_deg``: module
    +X along (cos, sin), module +Y along (-sin, cos) -- `lot._godot_transform`'s
    yaw, and the hydrant's measured -Y-is-minus-perp (`site_furniture`)."""
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    return (mx * c - my * s, mx * s + my * c)


def module_at(piece):
    """The slot's centre for a pole record: the pole less `POLE_AT`, turned."""
    px, py = POLE_AT[form_of(piece)]
    dx, dy = _rotate(float(piece["yaw"]), -px, -py)
    x, y = piece["at"]
    return [round(x + dx, 3), round(y + dy, 3)]


def lens_point(piece, base):
    """``(x, y, z)`` of the pole's lens, ``base`` the pole's foot."""
    ly, lz = LENS_AT
    dx, dy = _rotate(float(piece["yaw"]), 0.0, ly)
    x, y = piece["at"]
    return (x + dx, y + dy, base + lz)


def wire_point(piece, name, base):
    """``(x, y, z)`` of wire ``name``'s attachment on this pole."""
    wy, wz = WIRES[name]
    dx, dy = _rotate(float(piece["yaw"]), 0.0, wy)
    x, y = piece["at"]
    return (x + dx, y + dy, base + wz)


def _line_offset(road, kerb):
    """The pole line's offset across the road: `POLE_INSET` in from the kerb
    face, which is the band's road-side edge."""
    return kerb.offset - kerb.sign * (road.sidewalk / 2.0 - POLE_INSET)


def pole_kerb(road, sign_bands=(), roads_list=()):
    """The kerb this road's line stands on, by what it has to dodge: the
    fewer dropped kerbs and shop bands, the better. A tie goes by a stable
    hash of the road's ends, so a spec puts its line on the same side every
    run, and two streets do not all lean the same way."""
    if not road.kerbs:
        return None
    scored = []
    for kerb in road.kerbs:
        cuts = len(kerb.cuts)
        bands = len(F._sign_spans(road, kerb, sign_bands, roads_list)) if sign_bands else 0
        scored.append((cuts + bands, kerb))
    best = min(s for s, _k in scored)
    tied = [k for s, k in scored if s == best]
    if len(tied) == 1:
        return tied[0]
    h = 2166136261
    for v in (road.a[0], road.a[1], road.b[0], road.b[1]):
        h = ((h ^ (int(round(float(v))) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return sorted(tied, key=lambda k: k.side)[h % len(tied)]


def _runs(road, kerb):
    """``[(t0, t1)]``: the stretches of this kerb a line runs along, broken
    at each ROAD crossing (a junction mouth, which a span crosses between the
    corner poles each side of it) and trimmed back from every cut's edge. A
    path's or a driveway's cut does not break a run: a pole steps off it."""
    half = POLE_FOOTPRINT[0] / 2.0
    pad = F.CUT_CLEARANCE + END_GAP + half
    edges = [0.0]
    for c in sorted(kerb.cuts, key=lambda c: c.t):
        if c.kind == "road":
            edges += [c.t - c.span / 2.0, c.t + c.span / 2.0]
    edges.append(road.length)
    runs = []
    for i in range(0, len(edges), 2):
        a, b = edges[i], edges[i + 1]
        a = a + pad if i > 0 else max(a, F.LAMP_START)
        b = b - pad if i + 2 < len(edges) else min(b, road.length - F.LAMP_START)
        if b >= a:
            runs.append((a, b))
    return runs


def _meters_on(road, kerb):
    """The parking meters this kerb will carry, as `site_furniture.plan_meters`
    will stand them after the band -- one at every bay's centre, its inset from
    the kerb edge -- so a pole never stands on one."""
    import site_streets
    offset = kerb.offset - kerb.sign * (road.sidewalk / 2.0 - F.METER_INSET)
    return [F._piece("Meter", "parking_meter", road, kerb, (b["t0"] + b["t1"]) / 2.0, offset)
            for b in site_streets.bays(road) if b["side"] == kerb.side]


#: A traffic signal's arms reach 5 m over the road one way and 3 m the other
#: at 6 to 6.5 m up (Zoo `traffic_signal`, 8 m tip to tip); a pole stands
#: clear of the whole reach, so no cobra-head crosses a mast arm.
SIGNAL_CLEAR = 5.0


def _room(pole, others):
    """Room for ``pole`` among the pieces ``others``, in plan: not the
    along-only `site_furniture._free`, which is right for pieces on one line
    and wrong across two -- the corner's bin and blade stand on the furniture
    line 1.9 m across the band from the pole line, and read along-only they
    refused both ends of the kerb probe's widest cut (the first draft: a
    station lost, measured). A piece's plan box (its ``size``) keeps
    `site_furniture.PIECE_GAP`; a tree keeps its CROWN's spread, so no pole
    stands in a tree; a signal keeps `SIGNAL_CLEAR`."""
    px, py = pole["at"]
    r = POLE_FOOTPRINT[0] / 2.0
    for o in others:
        ox, oy = o["at"]
        sp = o.get("species")
        if sp in F.TREES or sp == "street_tree":
            if math.hypot(px - ox, py - oy) < float(o["dims"][0]) / 2.0 + r + F.PIECE_GAP:
                return False
            continue
        if sp == "traffic_signal":
            if math.hypot(px - ox, py - oy) < SIGNAL_CLEAR:
                return False
            continue
        sx, _h, sy = o["size"]
        if (abs(px - ox) < sx / 2.0 + r + F.PIECE_GAP
                and abs(py - oy) < sy / 2.0 + r + F.PIECE_GAP):
            return False
    return True


def stations(road, kerb):
    """``[(t, r0, r1)]``: the line's stations before anything steps them --
    per run (`_runs`), evenly spaced no more than `POLE_SPAN` apart, each with
    the run it may step within. Pure, so a reader can ask where a pole was
    meant to stand."""
    out = []
    for r0, r1 in _runs(road, kerb):
        if r1 - r0 < 1e-6:
            out.append((r0, r0, r1))
            continue
        n = max(1, math.ceil((r1 - r0) / POLE_SPAN - 1e-9))
        out += [(r0 + (r1 - r0) * i / n, r0, r1) for i in range(n + 1)]
    return out


def _steps(t, kerb, spans, half):
    """`POLE_STEPS`, then -- for a station inside a dropped kerb or a shop band
    -- that span's nearer and farther end, as `site_furniture._nudged` steps a
    lamp to a band's end. A footpath's cut on the kerb probe is 20 m wide, wider
    than any step: without its ends the station is lost and its two spans
    become one, 75 m on the probe's left kerb (the first draft, measured)."""
    ends = []
    pad = F.CUT_CLEARANCE + half + 0.01
    for t0, t1, is_cut in kerb.spans:
        if is_cut and t0 - pad < t < t1 + pad:
            ends += [(t0 - pad) - t, (t1 + pad) - t]
    for t0, t1 in spans:
        if t0 - half < t < t1 + half:
            ends += [(t0 - half - F.PIECE_GAP) - t, (t1 + half + F.PIECE_GAP) - t]
    return list(POLE_STEPS) + sorted(ends, key=abs)


def plan_line(road, kerb, placed, markers, spans, n, buildings=(), kept_clear=None):
    """The poles of one road's line on ``kerb``: at its `stations`, each
    stepped along `POLE_STEPS` off a dropped kerb, a piece already on the band,
    a meter, a shop band or a marker -- within its run -- and the cans placed.
    Returns the pole records (``n`` numbers their names)."""
    offset = _line_offset(road, kerb)
    yaw_extra = 0.0 if kerb.sign > 0 else 180.0
    half = POLE_FOOTPRINT[0] / 2.0
    others = list(placed) + _meters_on(road, kerb)
    poles = []
    for t, r0, r1 in stations(road, kerb):
        got = None
        for dt in _steps(t, kerb, spans, half):
            s = t + dt
            if not (r0 - 1e-9 <= s <= r1 + 1e-9):
                continue
            if not (F._clear_of_cuts(s, half, kerb) and F._clear_of_spans(s, half, spans)):
                continue
            piece = _pole(f"Pole_{n + len(poles)}", road, kerb, s, offset, yaw_extra)
            if F._clear_of_markers(piece, markers) and _room(piece, others + poles):
                got = piece
                break
        # said as a lamp's was (0.106.0): only when the band, not a cut, moved it
        if (kept_clear is not None and spans and not F._clear_of_spans(t, half, spans)
                and F._clear_of_cuts(t, half, kerb)):
            kept_clear.append((f"Pole_{n + len(poles)}", t, got["t"] if got else None))
        if got is not None:
            poles.append(got)
    poles.sort(key=lambda p: p["t"])
    for i, p in enumerate(poles):
        p["line"] = f"{road.index}{kerb.side}"
        p["line_i"] = i
    _transformers(road, poles, buildings)
    for p in poles:
        p["module_at"] = module_at(p)
    return poles


def _pole(name, road, kerb, t, offset, yaw_extra):
    x, y = road.point(t, offset)
    yaw = (road.angle_deg + yaw_extra) % 360.0
    w, d, h = POLE_DIMS["auto"]
    fw, fd = POLE_FOOTPRINT
    return {"name": name, "species": "utility_pole", "at": [round(x, 3), round(y, 3)],
            "yaw": round(yaw, 3), "dims": [w, d, h], "size": [fw, h, fd],
            "base": "sidewalk", "road": road.index, "kerb": kerb.side,
            "t": round(t, 3), "along": fw, "source": "site_furniture", "breaks": ""}


def _served(road, pole, buildings):
    """How many buildings this pole serves: their centres within half a
    span along the road of its station, and `SERVE_ACROSS` of the road."""
    n = 0
    ax, ay = road.a
    for b in buildings or ():
        bx, by = b.get("at", (None, None))
        if bx is None:
            continue
        along = (float(bx) - ax) * road.along[0] + (float(by) - ay) * road.along[1]
        across = (float(bx) - ax) * road.perp[0] + (float(by) - ay) * road.perp[1]
        if abs(across) <= SERVE_ACROSS and abs(along - pole["t"]) <= POLE_SPAN / 2.0:
            n += 1
    return n


def _transformers(road, poles, buildings):
    """A can every third or fourth pole, by cause: the first on whichever of
    the first four poles the most buildings front, each next on the better
    served of the 3rd and 4th pole after it -- the nearer when they tie. A
    window whose poles serve nothing carries no can, and the count steps on
    from its end. A line of one or two poles carries one where they serve."""
    if not poles:
        return
    weight = [_served(road, p, buildings) for p in poles]

    def pick(lo, hi):
        best = None
        for i in range(lo, min(hi, len(poles))):
            if weight[i] > 0 and (best is None or weight[i] > weight[best]):
                best = i
        return best

    i = pick(0, CAN_EVERY[1])
    nxt = CAN_EVERY[1] if i is None else None
    while True:
        if i is not None:
            poles[i]["form"] = "transformer"
            w, d, h = POLE_DIMS["transformer"]
            poles[i]["dims"] = [w, d, h]
            lo = i + CAN_EVERY[0]
        else:
            lo = nxt
        if lo >= len(poles):
            break
        i = pick(lo, lo + (CAN_EVERY[1] - CAN_EVERY[0]) + 1)
        nxt = lo + (CAN_EVERY[1] - CAN_EVERY[0]) + 1
