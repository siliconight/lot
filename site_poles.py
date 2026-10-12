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
    path's or a driveway's cut does not break a run: a pole steps off it.

    THE KERB'S SPAN, NOT THE CUT'S WIDTH (0.118.1). A cut stands on its kerb
    as its width and `site_streets.CUT_MARGIN` either side (`split_span`), and
    `site_furniture._clear_of_cuts` reads that span. 0.118.0 trimmed the runs
    from the width alone, so every run's first station stood inside the span's
    clearance and was refused as a cut: cold run 9262's west side street, its
    span 0.0 to 5.6 for a 10 m crossing at 0, lost its corner pole that way --
    with the 5 m circle a signal kept refusing every step off it."""
    half = POLE_FOOTPRINT[0] / 2.0
    pad = F.CUT_CLEARANCE + END_GAP + half
    crossings = [c.t for c in kerb.cuts if c.kind == "road"]
    edges = [0.0]
    for t0, t1, is_cut in kerb.spans:
        if is_cut and any(t0 - 1e-9 <= ct <= t1 + 1e-9 for ct in crossings):
            edges += [t0, t1]
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


#: A TRAFFIC SIGNAL KEEPS ITS ARMS' BOX (0.118.1). Its module is 8 m of arm
#: along its yaw -- 5 m of mast over the road it meets, 3 m of luminaire arm
#: the other way, at 6 to 6.5 m up -- and 0.62 m across (Zoo `traffic_signal`),
#: so a pole conflicts with it only inside that box. REFUTED, KEPT: 0.118.0
#: kept a 5 m circle round the signal's pole, `SIGNAL_CLEAR`. A signal stands
#: on the furniture line, 1.94 m across the band from the pole line, and the
#: circle refused a corner pole that would have stood 1.63 m clear of the arms
#: (cold run 9262's west side street, `Signal_1L_0` at station 8.40).


def _room(pole, others):
    """Room for ``pole`` among the pieces ``others``, in plan: not the
    along-only `site_furniture._free`, which is right for pieces on one line
    and wrong across two -- the corner's bin and blade stand on the furniture
    line 1.9 m across the band from the pole line, and read along-only they
    refused both ends of the kerb probe's widest cut (the first draft: a
    station lost, measured). A piece's plan box (its ``size``) keeps
    `site_furniture.PIECE_GAP`; a tree keeps its CROWN's spread, so no pole
    stands in a tree; a signal keeps its arms' box, grown by the pole's
    radius and the gap, in its own frame."""
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
            w, d = float(o["dims"][0]), float(o["dims"][1])
            a = math.radians(float(o.get("yaw") or 0.0))
            dx, dy = px - ox, py - oy
            lx = dx * math.cos(a) + dy * math.sin(a)
            ly = -dx * math.sin(a) + dy * math.cos(a)
            if (abs(lx) < w / 2.0 + r + F.PIECE_GAP
                    and abs(ly) < d / 2.0 + r + F.PIECE_GAP):
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


# ---- the wires (0.119.0) ----------------------------------------------------
#
# The walker's call, 2026-10-12: the full wire set, no house drops -- three
# primaries on the crossarm, the neutral, the secondary and two communication
# cables, along every line and across each junction. Drawn as thin tubes
# sagging between the poles' attachments (`WIRES`), one mesh a `WIRE_CELL_M`
# cell of the plan (the paint's partition: a cell culls as a piece), written
# as an OBJ beside the scene. UNSHADED, casting no shadow and out of the
# lightmap: a wire is a dark line against the sky by day and a silhouette
# against a lit facade at night, and unshaded no light ever adds a pass for it
# (GL Compatibility draws a lit mesh once more for every light that reaches
# it). No collision: nothing walks a wire.
#
# ONE PIXEL (0.119.1). A tube a few centimetres across is under a pixel
# from about 15 m (a primary) to 30 m (a cable) at the player's camera and
# 900 lines, and the rasteriser keeps or drops it pixel by pixel: cold run
# 9263's far wires drew as dotted lines. Each vertex carries its wire's
# drawn radius as its UV's u, and `WIRE_SHADER` finds the wire's centre from
# it, widens a wire thinner than `WIRE_MIN_PX` pixel to that, and fades it
# by the share of the widened line the wire really covers: a far wire is a
# faint continuous line, as in a photograph, and a near one looks as it did.

#: Sag at mid-span, a fraction of the span's length: conductors a few percent,
#: the messenger-hung cables pulled tighter. Zoo's
#: `test_the_wires_stack_so_a_span_clears_the_road` holds the lowest cable
#: over 4.7 m at 2 % of a 36 m span.
SAG = {"primary": 0.025, "neutral": 0.025, "secondary": 0.03, "comm": 0.02}
#: The radius each is DRAWN at: about twice a real conductor's, as the fence's
#: tension wire is (Zoo 1.77.0) -- a real 1 cm wire is under a pixel at any
#: distance a player reads it from, and a line that comes and goes between
#: frames is what the walk's shot bot calls jitter.
WIRE_R = {"primary": 0.012, "neutral": 0.012, "secondary": 0.018, "comm": 0.022}
WIRE_SEGMENTS = 12
WIRE_SIDES = 4
#: A line's end pole is tied across a junction to the nearest pole of another
#: road's line within this: a side street's line tapping the main line, which
#: may be a pole in the middle of it rather than its end.
LINK_MAX = 30.0
WIRE_CELL_M = 32.0
WIRE_COLOUR = (0.07, 0.07, 0.07)
#: The narrowest a wire is drawn, in pixels (0.119.1): a thinner one is
#: widened to this and faded by the share of it the wire covers.
WIRE_MIN_PX = 1.0
#: The wires' material (0.119.1). A vertex stands at its wire's centre plus
#: NORMAL times the wire's drawn radius, which its u carries, so the vertex
#: shader can find the centre and widen the tube about it. Half a pixel at a
#: vertex is the clip's w over the projection's y scale and the frame's
#: height -- w is the depth in a perspective view and 1 in an orthographic
#: one, so the elevated shots hold too -- and a four-sided tube is sqrt(2)
#: narrower across a face than across its corners, so the clamp is that much
#: wider. Unshaded: no light adds a pass. Written into the scene as a string,
#: so no double quote and no backslash.
WIRE_SHADER = """shader_type spatial;
render_mode unshaded, cull_back;

// Lot's overhead wires (site_poles.py, 0.119.1): a wire thinner than min_px
// pixels is drawn that wide and faded by the share of it the wire covers.
uniform vec4 colour : source_color = vec4(0.07, 0.07, 0.07, 1.0);
uniform float min_px = 1.0;
varying float coverage;

void vertex() {
    float r = UV.x;
    vec3 centre = VERTEX - NORMAL * r;
    vec4 clip = PROJECTION_MATRIX * (MODELVIEW_MATRIX * vec4(centre, 1.0));
    float half_px = abs(clip.w) / (abs(PROJECTION_MATRIX[1][1]) * VIEWPORT_SIZE.y);
    float drawn = max(r, 1.41421356 * half_px * min_px);
    coverage = r / drawn;
    VERTEX = centre + NORMAL * drawn;
}

void fragment() {
    ALBEDO = colour.rgb;
    ALPHA = colour.a * coverage;
}
"""


def _kind(name):
    return name.split("_")[0]


def spans(cover):
    """``[(a, b)]``: each line's consecutive poles, and each line's end poles
    tied to the nearest pole of another road's line within `LINK_MAX` --
    every pair once."""
    lines = {}
    for p in cover:
        if p.get("species") == "utility_pole" and p.get("line"):
            lines.setdefault(p["line"], []).append(p)
    out, seen = [], set()

    def add(a, b):
        key = frozenset((a["name"], b["name"]))
        if a is not b and key not in seen:
            seen.add(key)
            out.append((a, b))

    ordered = {k: sorted(v, key=lambda p: p["line_i"]) for k, v in sorted(lines.items())}
    for ps in ordered.values():
        for a, b in zip(ps, ps[1:]):
            add(a, b)
    for key, ps in ordered.items():
        for end in {id(ps[0]): ps[0], id(ps[-1]): ps[-1]}.values():
            best = None
            for other, qs in ordered.items():
                if other == key or qs[0]["road"] == end["road"]:
                    continue
                for q in qs:
                    d = math.hypot(q["at"][0] - end["at"][0], q["at"][1] - end["at"][1])
                    if d <= LINK_MAX and (best is None or d < best[0]):
                        best = (d, q)
            if best is not None:
                add(end, best[1])
    return out


def wire_path(a, b, name, base):
    """The points of wire ``name`` from pole ``a`` to pole ``b``: a parabola
    through both attachments sagging `SAG` of the span at its middle."""
    x0, y0, z0 = wire_point(a, name, base)
    x1, y1, z1 = wire_point(b, name, base)
    span = math.hypot(x1 - x0, y1 - y0)
    sag = SAG[_kind(name)] * span
    pts = []
    for i in range(WIRE_SEGMENTS + 1):
        s = i / WIRE_SEGMENTS
        pts.append((x0 + (x1 - x0) * s, y0 + (y1 - y0) * s,
                    z0 + (z1 - z0) * s - 4.0 * sag * s * (1.0 - s)))
    return pts


def _tube(pts, r):
    """``(verts, normals, quads)`` of a `WIRE_SIDES`-sided tube along ``pts``,
    in plan frame (z up); a quad is four indices into ``verts``."""
    verts, norms, quads = [], [], []
    n = len(pts)
    for i, c in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tx, ty, tz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        tl = math.sqrt(tx * tx + ty * ty + tz * tz) or 1.0
        tx, ty, tz = tx / tl, ty / tl, tz / tl
        ux, uy, uz = ty, -tx, 0.0                      # t x up: level, across the wire
        ul = math.hypot(ux, uy)
        ux, uy = (ux / ul, uy / ul) if ul > 1e-9 else (1.0, 0.0)
        wx, wy, wz = uy * tz - uz * ty, uz * tx - ux * tz, ux * ty - uy * tx
        for k in range(WIRE_SIDES):
            ang = 2.0 * math.pi * (k + 0.5) / WIRE_SIDES
            ca, sa = math.cos(ang), math.sin(ang)
            nx, ny, nz = ux * ca + wx * sa, uy * ca + wy * sa, uz * ca + wz * sa
            verts.append((c[0] + r * nx, c[1] + r * ny, c[2] + r * nz))
            norms.append((nx, ny, nz))
    for i in range(n - 1):
        for k in range(WIRE_SIDES):
            k1 = (k + 1) % WIRE_SIDES
            quads.append((i * WIRE_SIDES + k, i * WIRE_SIDES + k1,
                          (i + 1) * WIRE_SIDES + k1, (i + 1) * WIRE_SIDES + k))
    return verts, norms, quads


def wire_meshes(cover, base):
    """``(body_lines, sub_lines, files)`` for the site's wires: every span's
    `WIRES`, one mesh a `WIRE_CELL_M` cell by the span's middle, each an OBJ
    beside the scene (``files``: name -> text) stood by a MeshInstance3D that
    casts no shadow, takes no GI and shares one unshaded material, which holds
    a wire to a pixel (`WIRE_SHADER`, 0.119.1). ``base`` is
    the height a pole stands on (a sidewalk band's top). Nothing when the site
    has no line."""
    cells = {}
    for a, b in spans(cover):
        mx = (a["at"][0] + b["at"][0]) / 2.0
        my = (a["at"][1] + b["at"][1]) / 2.0
        cell = (int(math.floor(mx / WIRE_CELL_M)), int(math.floor(my / WIRE_CELL_M)))
        cells.setdefault(cell, []).append((a, b))
    body, sub, files = [], [], {}
    for cell in sorted(cells):
        cx, cy = cell
        name = f"site_wires_c{cx + 500:03d}_{cy + 500:03d}"
        verts, norms, radii, faces = [], [], [], []
        for a, b in cells[cell]:
            for wire in sorted(WIRES):
                r = WIRE_R[_kind(wire)]
                v, nrm, q = _tube(wire_path(a, b, wire, base), r)
                o = len(verts)
                verts += v
                norms += nrm
                radii += [r] * len(v)
                faces += [(o + i0 + 1, o + i1 + 1, o + i2 + 1, o + i3 + 1) for i0, i1, i2, i3 in q]
        lines = [f"# Lot: the site's overhead wires, cell ({cx}, {cy}) of {WIRE_CELL_M:g} m, "
                 f"{len(cells[cell])} span(s) of {len(WIRES)} wires", f"o {name}"]
        # Godot's frame: plan (x, y, z up) is (x, z, -y), a rotation, so a
        # face's winding survives it. Each vertex's u is its wire's drawn
        # radius, which `WIRE_SHADER` reads (0.119.1).
        lines += [f"v {x:.4f} {z:.4f} {-y:.4f}" for x, y, z in verts]
        lines += [f"vt {r:.4f} 0" for r in radii]
        lines += [f"vn {x:.4f} {z:.4f} {-y:.4f}" for x, y, z in norms]
        # `_tube`'s quads run round the ring against the normals; reversed, a
        # face is counter-clockwise about its outward normal (OBJ's front) and
        # the material culls the back, so one layer of a wire draws and its
        # fade is its coverage (0.119.1; 0.119.0 drew both sides)
        for f0, f1, f2, f3 in faces:
            lines.append(f"f {f0}/{f0}/{f0} {f2}/{f2}/{f2} {f1}/{f1}/{f1}")
            lines.append(f"f {f0}/{f0}/{f0} {f3}/{f3}/{f3} {f2}/{f2}/{f2}")
        files[f"{name}.obj"] = "\n".join(lines) + "\n"
        body += [f'[node name="{name}" type="MeshInstance3D" parent="."]',
                 f'mesh = ExtResource("{name}")',
                 'material_override = SubResource("Mat_site_wires")',
                 "cast_shadow = 0", "gi_mode = 0", ""]
    if cells:
        cr, cg, cb = WIRE_COLOUR
        sub += ['[sub_resource type="Shader" id="Shader_site_wires"]',
                f'code = "{WIRE_SHADER}"', "",
                '[sub_resource type="ShaderMaterial" id="Mat_site_wires"]',
                'shader = SubResource("Shader_site_wires")',
                f"shader_parameter/colour = Color({cr:g}, {cg:g}, {cb:g}, 1)",
                f"shader_parameter/min_px = {WIRE_MIN_PX:g}", ""]
    return body, sub, files
