"""The street as a model, not a strip: roads, their kerbs, the cuts in them,
and the markings that assign the ground to a use.

Until 0.61.0 a road lived inline in `lot._outdoor_nodes`: one yawed box, two
sidewalk bands split at the crossings, and the crossing arithmetic beside
them. Every next step of roadmap 153 -- crosswalk stripes at the cuts, a
centre line, stop bars, parking bays, furniture along the kerb, sidewalk
zones for dressing -- asks the same questions of the same geometry, so the
geometry is answered once, here, and the writer draws what this says.

Frame: spec/Blender Z-up plan coordinates, metres, exactly as the spec is
written. A road runs from ``a`` to ``b``; ``t`` is metres along it from
``a``; an offset is metres across it, positive to the LEFT of travel (the
``L`` kerb), the convention `_kerb_crossings` has always used.

Pure: dicts in, records out. No Godot, no Blender, stdlib only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

#: A crossing's dropped kerb is widened by this on each side so a body
#: approaching off-centre meets the drop and not its corner -- the same reason
#: a real dropped kerb is wider than the crossing painted on it.
CUT_MARGIN = 0.6

#: What the paint looks like. Widths from the MUTCD's normal line (4 in ~ 0.1
#: m, rounded up so a 512 px tile reads it) and its continental crosswalk
#: (bars 0.3-0.6 m wide, spaced their own width). Colours are the greybox's
#: flat reads, and the tint of the road-paint pack when the site carries
#: one (`lot.SKIN_FAMILIES`, family `paint`).
LINE_WIDTH = 0.12
EDGE_INSET = 0.30          # edge line, in from the kerb face
DASH_ON = 3.0
DASH_OFF = 9.0
BAR_WIDTH = 0.5            # a crosswalk bar, measured along the road
BAR_GAP = 0.5
STOP_BAR_DEPTH = 0.4       # a stop bar, measured along the road
STOP_BAR_SETBACK = 1.0     # from the crosswalk's edge
WHITE = (0.90, 0.90, 0.88)
YELLOW = (0.90, 0.75, 0.20)

#: Parking along the kerb (roadmap 153): bay length and lane depth at the
#: low end of parallel-parking practice (20-22 ft bays, 7-8 ft lanes), so a
#: 10 m road keeps two 2.8 m driving lanes; no bay within the setback of a
#: crossing (the 20 ft no-parking rule at a crosswalk). A road with
#: sidewalks has parking lanes; its edge lines mark the driving lanes' edge,
#: inside the parking lane.
BAY_LENGTH = 6.0
LANE_DEPTH = 2.2
CROSSING_SETBACK = 6.0

#: TRAFFIC KEEPS RIGHT: the level is an American street. A driver travelling
#: +t (a -> b) drives the R half of the carriageway (negative offset) and has
#: the R kerb on the right; a driver travelling -t drives the L half with the
#: L kerb on the right. Every question of "which lane" and "which kerb" in
#: the street model reads this, so a left-hand site is one table away.
KEEP_RIGHT = True
#: The narrowest lane a driving half counts as a second lane at: 10 ft, the
#: urban minimum in AASHTO and NACTO practice. It decides only whether an
#: approach is multi-lane (a second stop sign on the left).
LANE_MIN = 3.0


def has_parking(road) -> bool:
    return bool(road.sidewalk) and road.width >= 2.0 * LANE_DEPTH + 5.0


def right_side(travel: int) -> str:
    """The side ("L"/"R") of the road a driver travelling ``travel`` (+1:
    +t, -1: -t) drives on, which is also the kerb on the right."""
    plus = "R" if KEEP_RIGHT else "L"
    minus = "L" if KEEP_RIGHT else "R"
    return plus if travel > 0 else minus


def approach_lanes(road) -> int:
    """Driving lanes one direction of ``road`` carries: its driving half
    (the carriageway less any parking lane) in `LANE_MIN` lanes, at least 1."""
    driving = road.width - (2.0 * LANE_DEPTH if has_parking(road) else 0.0)
    return max(1, int((driving / 2.0) // LANE_MIN))


def bays(road) -> list:
    """Every parking bay on ``road``: dicts of side, index, t0, t1 (along)
    and offset (across, to the lane's centre). Bays step from the road's
    start; a stretch within `CROSSING_SETBACK` of a centre-line crossing, or
    over a kerb cut, holds none."""
    if not has_parking(road):
        return []
    out = []
    keep_out = [(crossing_box(c)[0] - CROSSING_SETBACK,
                 crossing_box(c)[1] + CROSSING_SETBACK) for c in road.crossings]
    for kerb in road.kerbs:
        cuts = [(t0, t1) for t0, t1, is_cut in kerb.spans if is_cut]
        offset = kerb.sign * (road.width / 2.0 - LANE_DEPTH / 2.0)
        for i in range(int(road.length // BAY_LENGTH)):
            t0, t1 = i * BAY_LENGTH, (i + 1) * BAY_LENGTH
            if any(not (t1 <= a or t0 >= b) for a, b in keep_out + cuts):
                continue
            out.append({"side": kerb.side, "index": i, "t0": t0, "t1": t1,
                        "offset": offset})
    return out


@dataclass
class Cut:
    """A crossing dropped into a kerb: where along the kerb, how wide.

    A ROAD crossing carries the crosser's sidewalk too, because the box a
    junction takes is the crosser's width plus both its bands; and whether
    the crosser ENDS here (a T: its endpoint lies on this road's line),
    because the leg that ends is the one that stops."""
    t: float
    span: float
    width: float        # the crossing's own width (the path's)
    kind: str           # "path" or "road"
    sidewalk: float = 0.0
    terminal: bool = False
    crosser: int = -1   # the crossing road's index in the spec (-1: a path)


@dataclass
class Kerb:
    side: str                       # "L" or "R"
    sign: int                       # +1 left of travel, -1 right
    offset: float                   # metres across, to the band's centre line
    cuts: list = field(default_factory=list)
    spans: list = field(default_factory=list)   # [(t0, t1, is_cut)]


@dataclass
class Road:
    index: int
    a: tuple
    b: tuple
    width: float
    sidewalk: float
    length: float
    angle_deg: float
    along: tuple
    perp: tuple
    kerbs: list = field(default_factory=list)
    crossings: list = field(default_factory=list)   # Cuts against the CENTRE line
    #: The slab's extent along ``t``: the whole road, unless an end lies on
    #: another road, where the slab begins at the far edge of that road's
    #: band and the other road's dropped kerb carries the mouth (a T).
    slab: tuple = (0.0, 0.0)
    #: Boxes along ``t`` this road does NOT draw: where a lower-index road
    #: crosses THROUGH it (an X), that road's carriageway and bands own the
    #: junction's surface, and this road's slab and band pieces stop at the
    #: box's edges and resume past them. Without this two slabs and two
    #: dropped kerbs lay coplanar over every X.
    gaps: list = field(default_factory=list)

    @property
    def centre(self):
        return ((self.a[0] + self.b[0]) / 2.0, (self.a[1] + self.b[1]) / 2.0)

    @property
    def slab_centre(self):
        return self.point((self.slab[0] + self.slab[1]) / 2.0)

    @property
    def slab_length(self):
        return self.slab[1] - self.slab[0]

    def point(self, t: float, offset: float = 0.0):
        """Plan point ``t`` metres along, ``offset`` metres across (left +)."""
        return (self.a[0] + self.along[0] * t + self.perp[0] * offset,
                self.a[1] + self.along[1] * t + self.perp[1] * offset)

    def kerb(self, side: str):
        return next(k for k in self.kerbs if k.side == side)


def _endpoints(rec, bld):
    a = bld[rec["from"]]["at"] if "from" in rec else rec["a"]
    b = bld[rec["to"]]["at"] if "to" in rec else rec["b"]
    return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


def kerb_crossings(site_spec, bld, origin, along, perp, offset, length, width,
                   findings=None):
    """(Cut, ...) per crossing of one kerb: where a path OR another road
    crosses it, and how much kerb that crossing consumes measured along it.
    Anything that runs parallel, or crosses beyond either end, contributes
    nothing -- there is no crossing to drop. ``width`` is the kerb band's
    depth. A crossing shallower than the arithmetic likes is reported into
    ``findings`` (a list of strings) rather than printed."""
    ox, oy = origin
    ux, uy = along
    px, py = perp
    kx, ky = ox + px * offset, oy + py * offset
    out = []
    crossers = [(p, float(p.get("width", 6.0)), "path", 0.0, -1)
                for p in site_spec.get("paths", []) or []]
    crossers += [(r, float(r.get("width", 9.0)), "road", float(r.get("sidewalk") or 0.0), ri)
                 for ri, r in enumerate(site_spec.get("roads", []) or [])]
    for p, pw, kind, psw, crosser in crossers:
        try:
            (pax, pay), (pbx, pby) = _endpoints(p, bld)
        except (KeyError, TypeError):
            continue
        vx, vy = pbx - pax, pby - pay
        den = ux * (-vy) - uy * (-vx)
        if abs(den) < 1e-9:
            continue                      # parallel: never crosses
        rx, ry = pax - kx, pay - ky
        t = (rx * (-vy) - ry * (-vx)) / den
        s = (ux * ry - uy * rx) / den
        if not (-0.05 <= s <= 1.05):
            continue                      # crosses the LINE, not the path
        # where the crosser meets the road's CENTRE line, not this kerb's:
        # a road that ends on the centre line (a T) is terminal whichever
        # kerb is being asked, and its parameter at the kerb is not 0
        rx0, ry0 = pax - ox, pay - oy
        s_c = (ux * ry0 - uy * rx0) / den
        if t < 0.0 or t > length:
            continue                      # past the end of this kerb
        vl = math.hypot(vx, vy) or 1e-9
        cos_t = abs(vx * ux + vy * uy) / vl
        sin_t = abs(vx * px + vy * py) / vl
        span = (pw + float(width) * cos_t) / max(sin_t, 1e-6)
        if span > 3.0 * pw and findings is not None:
            findings.append(
                f"LOT_KERB_CROSSED_SHALLOW: a {pw} m {kind} meets this kerb at "
                f"{math.degrees(math.asin(min(1.0, sin_t))):.0f} deg {t:.1f} m "
                f"along it, so {span:.1f} m of kerb is dropped to keep the "
                f"crossing walkable. Re-route it closer to square, or run it "
                f"along the sidewalk rather than across it.")
        out.append(Cut(t=t, span=span, width=pw, kind=kind, sidewalk=psw,
                       terminal=(s_c < 0.05 or s_c > 0.95), crosser=crosser))
    return out


def drawn_spans(road) -> list:
    """[(t0, t1)] of the slab this road draws: its slab less its gaps."""
    return [(a, b) for a, b in _outside(road.slab[0], road.slab[1], road.gaps)
            if b - a > 0.05]


def crossing_box(cut) -> tuple:
    """(lo, hi) along the road that a crossing takes: a path's own width; a
    road's width plus its sidewalk band each side -- the junction box."""
    half = cut.width / 2.0 + (cut.sidewalk if cut.kind == "road" else 0.0)
    return (cut.t - half, cut.t + half)


def crossing_walks(road, cut) -> list:
    """[(centre, width)] along ``road`` of the crosswalks a crossing marks.
    A path's crosswalk is its own width. A road's box carries one at EACH
    end in line with the crosser's sidewalk (where people crossing the
    junction walk), so every leg of the junction is marked; an end past
    this road's own extent is dropped, so a T leg gets the one crosswalk
    across its mouth and the through road one each side of the mouth."""
    lo, hi = crossing_box(cut)
    if cut.kind == "road" and cut.sidewalk > 0.0:
        walks = [(lo + cut.sidewalk / 2.0, cut.sidewalk),
                 (hi - cut.sidewalk / 2.0, cut.sidewalk)]
    else:
        walks = [(cut.t, cut.width)]
    # kept within the ROAD's extent, not its slab: a T leg's mouth
    # crosswalk lies on the through road's dropped kerb, between the slab
    # and the centre line, and that is where it belongs
    return [(tc, wc) for tc, wc in walks
            if tc - wc / 2.0 >= -1e-6 and tc + wc / 2.0 <= road.length + 1e-6]


def walk_paint(centre, width) -> tuple:
    """(t0, t1) of the bars a crosswalk of ``centre`` and ``width`` paints:
    whole bars and gaps, centred, so the painted near line can stand up to
    a bar's width inside the walk's nominal edge."""
    n = max(1, int(width // (BAR_WIDTH + BAR_GAP)))
    span = n * (BAR_WIDTH + BAR_GAP) - BAR_GAP
    return (centre - span / 2.0, centre + span / 2.0)


def painted_walks(road) -> list:
    """[(t0, t1)] of every crosswalk ``road`` paints, in bars."""
    return sorted(walk_paint(tc, wc) for c in road.crossings
                  for tc, wc in crossing_walks(road, c))


def _ends_on(road, other) -> bool:
    """An end of ``road`` lies on ``other``'s centre line, within a metre
    across and within its extent: ``road`` is a leg that ENDS at ``other``."""
    for end in (road.a, road.b):
        dx, dy = end[0] - other.a[0], end[1] - other.a[1]
        across = dx * other.perp[0] + dy * other.perp[1]
        along = dx * other.along[0] + dy * other.along[1]
        if abs(across) <= 1.0 and -1.0 <= along <= other.length + 1.0:
            return True
    return False


def is_arterial(road) -> bool:
    """Sidewalks and parking lanes both: a Delco commercial strip."""
    return bool(road.sidewalk) and has_parking(road)


@dataclass
class Approach:
    """One leg of a road-road junction, as the driver arriving on it sees it.

    ``travel`` is the direction of that driver along ``road`` (+1: +t);
    ``mouth`` the station of the junction box's edge the driver meets first;
    ``line`` the painted near line of the leg's crosswalk when it is marked,
    else the mouth;
    ``edge`` the station of the crosser's travelled-way edge (its kerb face)
    the driver meets; ``control`` is "signal", "stop" or "through" (the
    through road of a stop-controlled junction keeps its right of way);
    ``minor`` whether this road is the one that yields at the junction."""
    road: int
    crosser: int
    travel: int
    station: float
    mouth: float
    line: float
    edge: float
    control: str
    minor: bool
    marked: bool
    ped_access: bool


def approaches(roads_list) -> list:
    """Every approach to every road-road junction, and its control.

    WHICH ROAD YIELDS. A road that ends on another (a T's stem) yields to the
    one it ends on. Where neither or both end (an X, or an L corner) the
    lower-ranked road yields -- rank is arterial first, then carriageway
    width -- and two roads of equal rank both yield (an all-way stop).

    SIGNAL OR STOP. A junction is signalised when a yielding road meets an
    arterial: a Delco side street meeting a commercial strip has a signal;
    two side streets have stop signs. At a signalised junction every leg is
    under the signal and none carries a stop sign.

    A leg exists where the road carries pavement upstream of the box -- a
    T's stem has one, a through road two, an X four."""
    out = []
    by_index = {r.index: r for r in roads_list}

    def rank(r):
        return (1 if is_arterial(r) else 0, r.width)

    for road in roads_list:
        for c in road.crossings:
            if c.kind != "road" or c.crosser not in by_index:
                continue
            other = by_index[c.crosser]
            road_ends, other_ends = _ends_on(road, other), _ends_on(other, road)
            if road_ends != other_ends:
                minor, other_minor = road_ends, other_ends
            else:
                minor = rank(road) <= rank(other)
                other_minor = rank(other) <= rank(road)
            signalised = ((minor and is_arterial(other))
                          or (other_minor and is_arterial(road)))
            lo, hi = crossing_box(c)
            walks = crossing_walks(road, c)
            for travel in (1, -1):
                mouth = lo if travel > 0 else hi
                if travel > 0 and mouth <= road.slab[0] + 0.5:
                    continue
                if travel < 0 and mouth >= road.slab[1] - 0.5:
                    continue
                mine = [walk_paint(tc, wc) for tc, wc in walks
                        if (tc < c.t) == (travel > 0) and abs(tc - c.t) > 1e-6]
                marked = bool(mine)
                line = (mine[0][0] if travel > 0 else mine[0][1]) if mine else mouth
                control = ("signal" if signalised
                           else "stop" if minor else "through")
                out.append(Approach(
                    road=road.index, crosser=c.crosser, travel=travel,
                    station=c.t, mouth=mouth, line=line,
                    edge=c.t - travel * c.width / 2.0,
                    control=control, minor=minor, marked=marked,
                    ped_access=bool(c.sidewalk)))
    return out


def _slab(road, others) -> tuple:
    """Where the slab runs: trimmed at an end that lies on another road's
    centre line (within a metre, within that road's extent) by the far edge
    of that road's band, so the two slabs never lie coplanar over the mouth
    and the other road's dropped kerb is the mouth's surface."""
    t0, t1 = 0.0, road.length
    for other in others:
        if other is road:
            continue
        for end, which in ((road.a, 0), (road.b, 1)):
            dx, dy = end[0] - other.a[0], end[1] - other.a[1]
            along = dx * other.along[0] + dy * other.along[1]
            across = dx * other.perp[0] + dy * other.perp[1]
            if abs(across) > 1.0 or along < -1.0 or along > other.length + 1.0:
                continue
            trim = other.width / 2.0 + other.sidewalk
            if which == 0:
                t0 = max(t0, trim)
            else:
                t1 = min(t1, road.length - trim)
    return (t0, max(t0, t1))


def split_span(length, cuts, margin: float = CUT_MARGIN):
    """[(t0, t1, is_cut)] along a kerb: crossings, and the kerb between them."""
    bands = []
    for c in sorted(cuts, key=lambda c: c.t):
        half = c.span / 2.0 + margin
        bands.append((max(0.0, c.t - half), min(length, c.t + half)))
    merged = []
    for b in bands:
        if merged and b[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b[1]))
        else:
            merged.append(b)
    spans, cursor = [], 0.0
    for b0, b1 in merged:
        if b0 > cursor:
            spans.append((cursor, b0, False))
        spans.append((b0, b1, True))
        cursor = b1
    if cursor < length:
        spans.append((cursor, length, False))
    return spans


def roads(site_spec, findings=None) -> list:
    """Every road in the spec as a `Road`, kerbs and cuts resolved."""
    bld = {b["id"]: b for b in site_spec.get("buildings", []) or []}
    out = []
    for i, rd in enumerate(site_spec.get("roads", []) or []):
        a, b = _endpoints(rd, bld)
        w = float(rd.get("width", 9.0))
        sw = float(rd.get("sidewalk") or 0.0)
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 0.001
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        road = Road(index=i, a=a, b=b, width=w, sidewalk=sw, length=length,
                    angle_deg=math.degrees(math.atan2(dy, dx)),
                    along=(ux, uy), perp=(px, py))
        # Where each crosser meets the road's CENTRE line: one station per
        # crossing, whichever kerbs it cuts. A diagonal path meets the two
        # kerbs metres apart, and a crosswalk painted at each kerb's own
        # station is two crosswalks for one crossing (measured on the kerb
        # probe: 14 stations for 8 crossings).
        road.crossings = kerb_crossings(site_spec, bld, a, (ux, uy), (px, py),
                                        0.0, length, w)
        if sw:
            off = w / 2.0 + sw / 2.0
            for side, sgn in (("L", 1), ("R", -1)):
                cuts = kerb_crossings(site_spec, bld, a, (ux, uy), (px, py),
                                      off * sgn, length, sw, findings)
                road.kerbs.append(Kerb(side=side, sign=sgn, offset=off * sgn,
                                       cuts=cuts, spans=split_span(length, cuts)))
        out.append(road)
    for road in out:
        road.slab = _slab(road, out)
        # an X: a lower-index road crossing through owns the junction box
        road.gaps = [crossing_box(c) for c in road.crossings
                     if c.kind == "road" and not c.terminal
                     and 0 <= c.crosser < road.index]
    return out


#: THE FRONTAGE. A building standing a few metres back from a sidewalk's
#: back edge left that strip as bare plate, and the plate wears the lot's
#: asphalt -- so the only light surface between the wall and the walk was a
#: door spur, 4 m wide, standing 1.0 m (bank) or 3.0 m (strip retail) proud
#: of the walk and stopping a metre short of the wall. Seen from the
#: sidewalk at eye height its side edges read as diagonals and
#: the paved edge as a dogleg (the walker, cold run 9052: "pathing here seems
#: kind of random?"). The art direction's point 4 is that commercial
#: buildings MEET the sidewalk, with parking beside or behind them.
#:
#: So the walk is paved to the face, across the building's width, wherever
#: the strip between them is too shallow to be a lot. How shallow: a car
#: parked nose-in needs its own length, and `BAY_LENGTH` is Lot's length of
#: a parked car's space. A strip under that holds no car and is residue; a
#: deeper one can be the lot in front of a building, and its door path
#: keeps meeting the sidewalk square.
FRONTAGE_MAX = BAY_LENGTH

#: A strip thinner than this is a seam between two surfaces, not a strip.
FRONTAGE_MIN = 0.05

#: A building's rotation and a road's heading are both allowed this much
#: slop, in degrees, when deciding a face runs parallel to the road. The
#: footprint of a building at any other angle is its enclosing box
#: (`site_extent.rotated_footprint`), which is not a face.
PARALLEL_TOL_DEG = 0.01


@dataclass
class Frontage:
    """The walk carried from a sidewalk's back edge to a building's face.

    ``t0..t1`` metres along ``road``; ``back`` and ``face`` are signed
    offsets across it (left +), the band's back edge and the wall."""
    road: int
    side: str
    building: str
    t0: float
    t1: float
    back: float
    face: float

    @property
    def depth(self) -> float:
        return abs(self.face - self.back)

    @property
    def length(self) -> float:
        return self.t1 - self.t0

    def centre(self, road):
        return road.point((self.t0 + self.t1) / 2.0, (self.back + self.face) / 2.0)

    def rect(self, road) -> tuple:
        """(x0, y0, x1, y1): the plan AABB. Exact, since a frontage exists
        only where the road runs along a plan axis."""
        pts = [road.point(t, o) for t in (self.t0, self.t1)
               for o in (self.back, self.face)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))


def _on_axis(deg: float) -> bool:
    r = deg % 90.0
    return min(r, 90.0 - r) <= PARALLEL_TOL_DEG


def _overlap(a, b) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > 1e-6
            and min(a[3], b[3]) - max(a[1], b[1]) > 1e-6)


def _road_box(road) -> tuple:
    """Plan AABB of a road's carriageway and both bands, end to end."""
    half = road.width / 2.0 + road.sidewalk
    pts = [road.point(t, o) for t in (0.0, road.length) for o in (-half, half)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def frontages(site_spec, roads_list, findings=None) -> list:
    """Every `Frontage` on the site: a building face parallel to a sidewalk,
    behind its back edge, less than `FRONTAGE_MAX` from it.

    Along the road it spans the building, within the stretch the band is
    drawn over (the slab, less its gaps and the junction boxes of roads
    crossing that kerb), so it never paves a junction's mouth. A piece that
    would overlap another building or another road's carriageway or bands is
    dropped and said into ``findings``: that ground belongs to something
    else, and deciding whose is not a paving question."""
    import site_extent
    rects = {}
    for b in site_spec.get("buildings", []) or []:
        rect = site_extent.rotated_footprint(b)
        if rect is None or not _on_axis(float(b.get("rot", 0) or 0)):
            continue
        rects[str(b.get("id", "?"))] = rect
    out = []
    for road in roads_list:
        if not road.sidewalk or not _on_axis(road.angle_deg):
            continue
        others = [_road_box(r) for r in roads_list if r is not road]
        for kerb in road.kerbs:
            back = kerb.sign * (road.width / 2.0 + road.sidewalk)
            holes = list(road.gaps) + [crossing_box(c) for c in kerb.cuts
                                       if c.kind == "road"]
            for bid, (x0, y0, x1, y1) in rects.items():
                ts, offs = [], []
                for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                    dx, dy = x - road.a[0], y - road.a[1]
                    ts.append(dx * road.along[0] + dy * road.along[1])
                    offs.append(dx * road.perp[0] + dy * road.perp[1])
                near = min(offs) if kerb.sign > 0 else max(offs)
                gap = (near - back) * kerb.sign
                if not (FRONTAGE_MIN < gap < FRONTAGE_MAX):
                    continue
                t0 = max(min(ts), road.slab[0])
                t1 = min(max(ts), road.slab[1])
                if t1 - t0 <= FRONTAGE_MIN:
                    continue
                for p0, p1 in _outside(t0, t1, holes):
                    if p1 - p0 <= FRONTAGE_MIN:
                        continue
                    fr = Frontage(road=road.index, side=kerb.side, building=bid,
                                  t0=p0, t1=p1, back=back, face=near)
                    box = fr.rect(road)
                    blocked = [o for o, r in rects.items()
                               if o != bid and _overlap(box, r)]
                    if blocked or any(_overlap(box, r) for r in others):
                        if findings is not None:
                            findings.append(
                                f"LOT_FRONTAGE_BLOCKED: the {fr.depth:.2f} m "
                                f"strip between {bid}'s face and road "
                                f"{road.index}'s {kerb.side} sidewalk "
                                f"({p0:.1f}-{p1:.1f} m along it) overlaps "
                                + (", ".join(blocked) if blocked
                                   else "another road")
                                + "; left unpaved.")
                        continue
                    out.append(fr)
    _turn_corners(out, roads_list, rects, others_of={
        r.index: [_road_box(o) for o in roads_list if o is not r]
        for r in roads_list})
    return out


def _turn_corners(frs, roads_list, rects, others_of):
    """Where one building has a frontage on each of two crossing roads, the
    walk wraps its corner: the square between the two strips, behind both
    bands, is paved too. Left out, a corner building meets both sidewalks
    and keeps a notch of lot at the corner -- the same dogleg, turned 90
    degrees. The square is added by running one strip on along its road to
    the other road's band; it is kept only if it still overlaps nothing."""
    by_index = {r.index: r for r in roads_list}

    def along(road, p):
        return ((p[0] - road.a[0]) * road.along[0]
                + (p[1] - road.a[1]) * road.along[1])

    for fa in frs:
        ra = by_index[fa.road]
        for fb in frs:
            rb = by_index[fb.road]
            if fb is fa or fb.building != fa.building or rb is ra:
                continue
            if abs(ra.along[0] * rb.along[0] + ra.along[1] * rb.along[1]) > 1e-6:
                continue                                  # not crossing square
            # fb's face and back edge, as stations along fa's road
            face_a = along(ra, rb.point(fb.t0, fb.face))
            back_a = along(ra, rb.point(fb.t0, fb.back))
            # fa's face, as a station along fb's road: fb must reach it
            face_b = along(rb, ra.point(fa.t0, fa.face))
            if min(abs(fb.t0 - face_b), abs(fb.t1 - face_b)) > 1e-6:
                continue
            if abs(fa.t0 - face_a) <= 1e-6 and back_a < fa.t0:
                t0, t1 = back_a, fa.t1
            elif abs(fa.t1 - face_a) <= 1e-6 and back_a > fa.t1:
                t0, t1 = fa.t0, back_a
            else:
                continue
            grown = Frontage(road=fa.road, side=fa.side, building=fa.building,
                             t0=t0, t1=t1, back=fa.back, face=fa.face)
            box = grown.rect(ra)
            if any(_overlap(box, r) for o, r in rects.items() if o != fa.building):
                continue
            if any(_overlap(box, r) for r in others_of[fa.road]):
                continue
            fa.t0, fa.t1 = t0, t1


def _marking(kind, road, t, offset, along, across, color, **extra):
    x, y = road.point(t, offset)
    m = {"kind": kind, "road": road.index, "at": [round(x, 4), round(y, 4)],
         "yaw": round(road.angle_deg, 4), "size": [round(along, 4), round(across, 4)],
         "color": list(color)}
    m.update(extra)
    return m


def markings(roads_list) -> list:
    """The paint a road carries, as plan rectangles: an edge line each side,
    a dashed centre line, a continental crosswalk at every kerb cut, and a
    stop bar per lane before each crosswalk. Rectangles are centred at
    ``at``, turned by ``yaw``, ``size`` [along the road, across it]. A
    crosswalk is stationed where the crossing meets the road's centre
    line, one per crossing, whichever kerbs it cuts."""
    out = []
    for road in roads_list:
        half = road.width / 2.0
        # edge lines, full length: at the driving lane's edge, which is
        # inside the parking lane on a road that has one, else in from the
        # kerb face
        edge = (half - LANE_DEPTH) if has_parking(road) else (half - EDGE_INSET)
        for sgn in (1, -1):
            side = "L" if sgn > 0 else "R"
            # broken over a road's mouth on that kerb -- the edge line
            # stops where the other road begins -- and whole over a path's
            # dropped kerb, which keeps the lane's edge
            mouths = [(c.t - c.span / 2.0, c.t + c.span / 2.0)
                      for k in road.kerbs if k.side == side
                      for c in k.cuts if c.kind == "road"]
            for e0, e1 in _outside(road.slab[0], road.slab[1], mouths):
                if e1 - e0 > 0.5:
                    out.append(_marking("edge_line", road, (e0 + e1) / 2.0,
                                        sgn * edge, e1 - e0, LINE_WIDTH, WHITE,
                                        side=side))
        # bay ticks: a short line across the parking lane at every bay edge
        seen = set()
        for bay in bays(road):
            for t in (bay["t0"], bay["t1"]):
                key = (bay["side"], round(t, 3))
                if key in seen or t <= 0.0 or t >= road.length:
                    continue
                seen.add(key)
                out.append(_marking("bay_tick", road, t, bay["offset"],
                                    LINE_WIDTH, LANE_DEPTH, WHITE, side=bay["side"]))
        # THE CROSSINGS, each as a box along the road with crosswalks at
        # its ends. A path's box is its own width and its crosswalk is
        # the box. A road's box is its width plus its sidewalk bands, and
        # a crosswalk lies at EACH end in line with the crosser's
        # sidewalk (that is where people crossing the junction walk); an
        # end past this road's own extent is dropped, so a T leg gets the
        # one crosswalk across its mouth and the through road gets one
        # each side of the mouth.
        boxes = []                    # (lo, hi, walks[(centre, width)], stops)
        for c in sorted(road.crossings, key=lambda c: c.t):
            lo, hi = crossing_box(c)
            walks = crossing_walks(road, c)
            # the leg that ENDS at a junction is the one that stops: a
            # road crosser whose end lies on this road makes this the
            # through road, which keeps its right of way. A path crossing
            # keeps its stop bars (a marked crosswalk).
            stops = not (c.kind == "road" and c.terminal)
            boxes.append((lo, hi, walks, stops, round(c.t, 3)))
        # the crosswalks plus the stop bars either side: no dash runs
        # into a stop bar
        clear = STOP_BAR_SETBACK + STOP_BAR_DEPTH
        bands = [(lo - clear, hi + clear) for lo, hi, _w, _s, _t in boxes]

        def _in_band(t0, t1):
            return any(not (t1 <= b0 or t0 >= b1) for b0, b1 in bands)

        # centre line, dashed, within the slab, skipping the boxes
        t = road.slab[0]
        while t < road.slab[1]:
            t1 = min(t + DASH_ON, road.slab[1])
            if t1 - t > 0.5 and not _in_band(t, t1):
                out.append(_marking("centre_line", road, (t + t1) / 2.0, 0.0,
                                    t1 - t, LINE_WIDTH, YELLOW))
            t += DASH_ON + DASH_OFF
        # crosswalk bars and stop bars
        lane = half - EDGE_INSET
        for lo, hi, walks, stops, station in boxes:
            for t_c, w_c in walks:
                n = max(1, int(w_c // (BAR_WIDTH + BAR_GAP)))
                start = walk_paint(t_c, w_c)[0]
                for j in range(n):
                    tb = start + j * (BAR_WIDTH + BAR_GAP) + BAR_WIDTH / 2.0
                    out.append(_marking("crosswalk_bar", road, tb, 0.0, BAR_WIDTH,
                                        road.width - 2.0 * EDGE_INSET, WHITE,
                                        station=station))
            if not stops:
                continue
            # a stop bar on the approach lane each way. Traffic keeps right
            # (`right_side`): a driver travelling +t is on the R half and
            # stops before the box; one travelling -t is on the L half and
            # stops after it. Until 0.69.4 the bars were painted on the
            # opposite halves -- the lanes LEAVING the box -- while the stop
            # signs stood on the right-hand kerb, so the sign and its line
            # were on two different lanes.
            t_lo = lo - STOP_BAR_SETBACK - STOP_BAR_DEPTH / 2.0
            t_hi = hi + STOP_BAR_SETBACK + STOP_BAR_DEPTH / 2.0
            sgn_in = {s: (1.0 if right_side(s) == "L" else -1.0) for s in (1, -1)}
            if t_lo - STOP_BAR_DEPTH / 2.0 > road.slab[0]:
                out.append(_marking("stop_bar", road, t_lo, sgn_in[1] * lane / 2.0,
                                    STOP_BAR_DEPTH, lane, WHITE, station=station))
            if t_hi + STOP_BAR_DEPTH / 2.0 < road.slab[1]:
                out.append(_marking("stop_bar", road, t_hi, sgn_in[-1] * lane / 2.0,
                                    STOP_BAR_DEPTH, lane, WHITE, station=station))
    return out


def _outside(t0, t1, holes):
    """[(a, b)] -- the parts of t0..t1 outside every hole."""
    spans, cursor = [], t0
    for h0, h1 in sorted(holes):
        if h1 <= cursor or h0 >= t1:
            continue
        if h0 > cursor:
            spans.append((cursor, h0))
        cursor = max(cursor, h1)
    if cursor < t1:
        spans.append((cursor, t1))
    return spans


def manifest(site_spec, roads_list=None, findings=None) -> dict:
    """`<site>.markings.json`: the roads and their paint, in spec space."""
    rl = roads_list if roads_list is not None else roads(site_spec, findings)
    return {
        "schema": "site-markings/1",
        "space": "spec/Blender Z-up raw coords; yaw = degrees about up",
        "roads": [{"index": r.index, "a": list(r.a), "b": list(r.b),
                   "width": r.width, "sidewalk": r.sidewalk,
                   "length": round(r.length, 4),
                   "slab": [round(r.slab[0], 4), round(r.slab[1], 4)],
                   "gaps": [[round(a, 4), round(b, 4)] for a, b in r.gaps],
                   "kerbs": [{"side": k.side, "offset": round(k.offset, 4),
                              "cuts": [{"t": round(c.t, 4), "span": round(c.span, 4),
                                        "width": c.width, "kind": c.kind,
                                        "sidewalk": c.sidewalk, "terminal": c.terminal}
                                       for c in k.cuts]} for k in r.kerbs]}
                  for r in rl],
        "markings": markings(rl),
        "frontages": [{"road": f.road, "side": f.side, "building": f.building,
                       "t": [round(f.t0, 4), round(f.t1, 4)],
                       "depth": round(f.depth, 4),
                       "rect": [round(v, 4) for v in f.rect(by_index[f.road])]}
                      for by_index in [{r.index: r for r in rl}]
                      for f in frontages(site_spec, rl, findings)],
    }
