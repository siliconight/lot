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


def has_parking(road) -> bool:
    return bool(road.sidewalk) and road.width >= 2.0 * LANE_DEPTH + 5.0


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
    crossers = [(p, float(p.get("width", 6.0)), "path", 0.0)
                for p in site_spec.get("paths", []) or []]
    crossers += [(r, float(r.get("width", 9.0)), "road", float(r.get("sidewalk") or 0.0))
                 for r in site_spec.get("roads", []) or []]
    for p, pw, kind, psw in crossers:
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
                       terminal=(s_c < 0.05 or s_c > 0.95)))
    return out


def crossing_box(cut) -> tuple:
    """(lo, hi) along the road that a crossing takes: a path's own width; a
    road's width plus its sidewalk band each side -- the junction box."""
    half = cut.width / 2.0 + (cut.sidewalk if cut.kind == "road" else 0.0)
    return (cut.t - half, cut.t + half)


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
    return out


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
            if c.kind == "road" and c.sidewalk > 0.0:
                walks = [(lo + c.sidewalk / 2.0, c.sidewalk),
                         (hi - c.sidewalk / 2.0, c.sidewalk)]
            else:
                walks = [(c.t, c.width)]
            # kept within the ROAD's extent, not its slab: a T leg's mouth
            # crosswalk lies on the through road's dropped kerb, between
            # the slab and the centre line, and that is where it belongs
            walks = [(tc, wc) for tc, wc in walks
                     if tc - wc / 2.0 >= -1e-6 and tc + wc / 2.0 <= road.length + 1e-6]
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
                start = t_c - (n * (BAR_WIDTH + BAR_GAP) - BAR_GAP) / 2.0
                for j in range(n):
                    tb = start + j * (BAR_WIDTH + BAR_GAP) + BAR_WIDTH / 2.0
                    out.append(_marking("crosswalk_bar", road, tb, 0.0, BAR_WIDTH,
                                        road.width - 2.0 * EDGE_INSET, WHITE,
                                        station=station))
            if not stops:
                continue
            # a stop bar on the approach lane each way: traffic on the L
            # lane travels +t and stops before the box; on the R lane it
            # travels -t and stops after it
            t_lo = lo - STOP_BAR_SETBACK - STOP_BAR_DEPTH / 2.0
            t_hi = hi + STOP_BAR_SETBACK + STOP_BAR_DEPTH / 2.0
            if t_lo - STOP_BAR_DEPTH / 2.0 > road.slab[0]:
                out.append(_marking("stop_bar", road, t_lo, lane / 2.0,
                                    STOP_BAR_DEPTH, lane, WHITE, station=station))
            if t_hi + STOP_BAR_DEPTH / 2.0 < road.slab[1]:
                out.append(_marking("stop_bar", road, t_hi, -lane / 2.0,
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
                   "kerbs": [{"side": k.side, "offset": round(k.offset, 4),
                              "cuts": [{"t": round(c.t, 4), "span": round(c.span, 4),
                                        "width": c.width, "kind": c.kind,
                                        "sidewalk": c.sidewalk, "terminal": c.terminal}
                                       for c in k.cuts]} for k in r.kerbs]}
                  for r in rl],
        "markings": markings(rl),
    }
