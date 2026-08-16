"""Something to hide behind, so the floor is not open for across-the-site sniping.

Lot's answer to an unfair opening engagement used to be arithmetic on distance:
if an enemy could see the crew, move the enemy. That is the cheapest possible
response and almost never the right one. Push a spawn far enough out and the map
still grades badly -- now for a first contact past the ceiling and a crew that
walks a minute before it meets anything -- and the site is no better than it was.
What made the opening unfair was that two markers could see each other across
ninety metres of empty ground. The distance was the symptom; the empty ground
was the defect, and the fix for empty ground is to put something in it.

Which makes this Lot's job rather than the evaluator's. Laser Tag can say the map
plays badly and it cannot place a crate, because it does not own the geometry.
Lot owns the geometry. So a firefight evaluator's finding is a *soft* gate here:
it never refuses a build, it changes what the build contains.

Two things are measured, in the order they matter:

  * Which pairs of mission markers can see each other across more open ground
    than the engagement opens at. That is the sniping question, asked of the
    floor rather than of the spawns.
  * Where along each of those lines a solid would break it -- and honestly,
    including the case where no solid short enough to call cover will do and the
    answer is that the site needs a building there.

The geometry that makes this less obvious than it looks: a sightline is two
lines, not one. Each side sights from its own eye at the other's chest, so the
crew's outgoing line descends and the enemy's incoming line climbs, and they
cross in the middle. A solid tall enough to break one can sit under the other,
and half a broken sightline is not half a fix -- Laser Tag stamps first contact
on the first shot fired by *either* side, so the free shot that remains starts
the clock exactly where it was. `MIN_COVER_HEIGHT` is where the two lines cross,
which is why it is derived here rather than chosen.

Pure: rects and points in, cover boxes and findings out. No Godot, no Blender,
stdlib only -- the same contract as `site_spawns`, and for the same reason: the
producer emits, this decides.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Where each side's eye and its target sit, from the Laser Tag scripts.
#: ``LT_BotPlayerController`` sights from ``body.global_position + UP * 1.4``
#: and ``LT_LineOfSightTester.CHEST_OFFSET`` is ``UP * 1.0``.
#:
#: A stated assumption in the sense `site_spawns.OPENING_RANGE` is: Lot cannot
#: read the Laser Tag checkout, so it carries the numbers and names where they
#: came from. Level Factory's `packages.validation.lasertag_contract` reads the
#: real files and reports drift against what is written here.
EYE_HEIGHT = 1.4
CHEST_HEIGHT = 1.0

#: The shortest solid that breaks a *mutual* sightline on level ground, and not
#: a round number chosen for looking like cover: it is where the outgoing and
#: incoming lines cross. Below this, one side keeps a free shot at the other and
#: the clock starts anyway.
MIN_COVER_HEIGHT = (EYE_HEIGHT + CHEST_HEIGHT) / 2.0

#: What Lot builds when it builds cover. Taller than the crossing height on
#: purpose: at exactly `MIN_COVER_HEIGHT` there is one position on the line that
#: works, and a solid that has to land within a few centimetres of a computed
#: point is a solid the first constraint will veto. Two metres breaks the line
#: over most of its length, which leaves room to satisfy everything else.
COVER_HEIGHT = 2.0

#: Footprint of one piece. Wide enough to break a line at the ranges that
#: matter, narrow enough that a street keeps a walkable lane either side --
#: Godot bakes this site at a 0.4 m agent radius, so a 3 m block in a 12 m
#: street leaves better than three metres of navmesh on each side.
COVER_SIZE = 3.0

#: Ratified fallbacks, equal to `deli_counter/agent_contract.json`'s
#: ``nav_bake``. Same rule as every other consumer of that contract: carry the
#: values so a missing file degrades instead of breaking, and let Level
#: Factory's `lasertag_contract` report drift.
_NAV_BAKE_FALLBACK = {"agent_radius_m": 0.4, "cell_size_m": 0.15}


def min_passable_gap(nav_bake=None) -> float:
    """The narrowest gap an agent can actually walk through.

    Not a judgement -- the agent contract's own derivation, the same one that
    sets `clearances.min_door_width_m`:

        2*ceil(agent_radius/cell_size)*cell_size + 2*cell_size

    Navmesh erosion removes whole voxels per side, `ceil(radius/cell)` of them,
    so a gap is either wide enough after erosion or it is not there at all.
    At the ratified 0.4 m radius and 0.15 m cells that is 1.2 m, which is why
    the ratified door is 1.25.

    `AGENT_CONTRACT.md` says door width, agent radius and bake cell size are
    ONE decision rather than three. A cover piece standing beside a wall is a
    doorway made of street furniture, and nothing was applying the rule to it.
    """
    nav = dict(_NAV_BAKE_FALLBACK)
    for key, value in (nav_bake or {}).items():
        if key in nav and isinstance(value, (int, float)) and not isinstance(value, bool):
            nav[key] = float(value)
    radius, cell = nav["agent_radius_m"], nav["cell_size_m"]
    if cell <= 0.0:
        return 2.0 * radius
    return 2.0 * math.ceil(radius / cell) * cell + 2.0 * cell


def building_clearance(size: float = COVER_SIZE, nav_bake=None) -> float:
    """Centre-to-wall clearance for a piece with a ``size`` footprint.

    Derived, not chosen. It was a flat 2.0 measured to the piece's CENTRE, and
    a piece is `COVER_SIZE` wide -- so its edge could sit 0.5 m off a wall
    against a gap the bake needs 1.2 m for. Every run then produced a lane that
    looked walkable in the scene and was not in the navmesh, which is a stuck
    bot rather than a visible defect: seed 5118 went from zero stuck events to
    one player and one enemy stuck in all 25 runs the moment cover density rose
    enough to hit the case.
    """
    return min_passable_gap(nav_bake) + size / 2.0


#: Kept as the ratified default for callers that pass no contract; the derived
#: value is what `plan_cover` actually uses.
BUILDING_CLEARANCE = building_clearance()

#: Clearance from any mission marker. A crate on a spawn is a spawn inside a
#: solid, which is `UNREACHABLE_SPAWN` and a refused map -- the exact failure
#: `site_spawns` exists to prevent, re-introduced by the fix for a different one.
MARKER_CLEARANCE = 3.0

#: Clearance between pieces. Two crates in contact are one wall, and a wall
#: across a street is a route that no longer exists.
COVER_SEPARATION = 6.0

#: Where in the usable interval to sit, 0 being the crew's end. A third of the
#: way from the crew is deliberate: it gives the crew something to move between
#: on its approach rather than handing the far end a wall to hold. Same
#: reasoning that puts a ladder's slab-hole on the approach side.
APPROACH_BIAS = 0.35

#: How finely to walk a line looking for a position that satisfies everything.
SEARCH_STEP = 0.02


@dataclass
class Cover:
    """One piece of cover: a solid on the ground, and the line it was for."""

    name: str
    x: float
    y: float
    size: float = COVER_SIZE
    height: float = COVER_HEIGHT
    breaks: str = ""
    span: float = 0.0

    @property
    def rect(self):
        half = self.size / 2.0
        return (self.x - half, self.y - half, self.x + half, self.y + half)

    def as_dict(self) -> dict:
        return {"name": self.name, "x": round(self.x, 3), "y": round(self.y, 3),
                "size": self.size, "height": self.height,
                "breaks": self.breaks, "span": round(self.span, 1)}

    def as_site_cover(self) -> dict:
        """The same piece as a site spec ``cover`` record.

        ``size`` in a cover record is ``(x, height, y)`` and not ``(x, y,
        height)``: it is written in the Godot frame, where the second component
        is up. The emitter reads it that way, and a reader that takes the first
        two components as a footprint builds a rect the wrong shape -- invisible
        while every cover record on a site was a 1 m cube, and wrong the moment
        one of them is not.

        `breaks` and `span` ride along so a piece in a written spec can still be
        traced back to the sightline it was placed for. Nothing in the emitter
        reads them; a person looking at why a crate is standing in the street
        does.
        """
        return {"at": [round(self.x, 3), round(self.y, 3)],
                "size": [self.size, self.height, self.size],
                "source": "site_cover",
                "breaks": self.breaks, "span": round(self.span, 1)}


@dataclass
class CoverPlan:
    """What was placed, and which sightlines are still open after it."""

    cover: list = field(default_factory=list)
    open_lines: list = field(default_factory=list)
    unbreakable: list = field(default_factory=list)
    #: Gaps this plan's own pieces left too narrow for an agent to walk. Read
    #: back from the emitted geometry rather than trusted from the search --
    #: `_usable` deciding a piece MAY stand somewhere and the navmesh actually
    #: baking a lane past it are two different claims, and only the second one
    #: is what a bot walks.
    pinches: list = field(default_factory=list)
    #: Stretches of the crew's route left inside an enemy's reach with nothing
    #: to hide behind. Kept apart from `open_lines` because the two mean
    #: opposite things -- that one is "too far and open", this one is "close
    #: and open" -- and one finding cannot say both without lying about one.
    route_open: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# measuring the floor
# ---------------------------------------------------------------------------
def required_height(t: float) -> float:
    """How tall a solid at ``t`` along a level sightline must be to stop both sides.

    The outgoing line runs eye-to-chest and descends; the incoming line runs the
    other way and climbs. The requirement is the higher of the two, so it is
    lowest where they cross and rises towards both ends -- which is why cover
    works over an interval rather than everywhere, and why the interval shrinks
    to a point as the solid approaches `MIN_COVER_HEIGHT`.

    Level ground only. Lot seats every mission marker on the street at
    ``site_spawns.GROUND_Z``, so the two ends of every line this module measures
    are at the same height; a site with a rooftop marker would need the floor
    under each sample read from the geometry, and would get a different module.
    """
    return max(EYE_HEIGHT + (CHEST_HEIGHT - EYE_HEIGHT) * t,
               CHEST_HEIGHT + (EYE_HEIGHT - CHEST_HEIGHT) * t)


def break_interval(height: float = COVER_HEIGHT):
    """The ``t`` range along a level line where a solid ``height`` tall occludes it.

    ``None`` when no position works. That is the honest answer to "where should
    the crate go" when the answer is that a crate will not do, and returning a
    midpoint instead would hand the producer a coordinate it could satisfy and
    a sightline that stayed open.
    """
    if height < MIN_COVER_HEIGHT:
        return None
    drop = EYE_HEIGHT - CHEST_HEIGHT
    if drop <= 0.0:                       # both sides sight from the same height
        return (0.0, 1.0)
    # Each branch of `required_height` is linear, so the feasible set is where
    # both are satisfied: past the descending line and short of the climbing one.
    lo = max(0.0, (EYE_HEIGHT - height) / drop)
    hi = min(1.0, (height - CHEST_HEIGHT) / drop)
    return (lo, hi) if lo <= hi else None


def open_span(a, b, rects) -> float:
    """How much of the line ``a``-``b`` no building interrupts, in metres.

    A rect containing either endpoint is skipped, for the reason `site_spawns`
    skips it: the building you are standing in is not cover from the building
    you are standing in, and counting it lets a marker that landed indoors pass
    every sightline test on the site.
    """
    length = math.dist(a, b)
    if length < 1e-9:
        return 0.0
    spans = []
    for rect in rects:
        if _inside(a, rect) or _inside(b, rect):
            continue
        span = _crossing(a, b, rect)
        if span is not None and span[1] - span[0] > 1e-9:
            spans.append(span)
    covered, cursor = 0.0, 0.0
    for lo, hi in sorted(spans):
        if hi <= cursor:
            continue
        covered += hi - max(lo, cursor)
        cursor = hi
    return max(0.0, length * (1.0 - covered))


def _inside(point, rect) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def _crossing(a, b, rect):
    """The ``t`` interval of ``a``->``b`` inside ``rect``, or ``None``.

    Liang-Barsky, the same clip `site_spawns._segment_crosses` runs. This one
    keeps the interval because the interval is what says how much of the line
    was blocked; the boolean there is only ever "was it non-empty".
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, a[0] - rect[0]), (dx, rect[2] - a[0]),
                 (-dy, a[1] - rect[1]), (dy, rect[3] - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
        if lo > hi:
            return None
    return (lo, hi)


def open_sightlines(points: dict, rects, *, limit: float):
    """Marker pairs that can see each other across more than ``limit`` metres.

    ``limit`` is the range at which the engagement opens, so what comes back is
    the set of lines along which somebody can fire the moment the run starts.
    Longest first: the worst line on a site is usually the one whose fix also
    shortens three others.
    """
    names = sorted(points)
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_name, b_name = names[i], names[j]
            a, b = points[a_name], points[b_name]
            length = math.dist(a, b)
            if length <= limit:
                continue
            if open_span(a, b, rects) < length - 1e-6:
                continue
            out.append((a_name, b_name, a, b, length))
    out.sort(key=lambda line: -line[4])
    return out


# ---------------------------------------------------------------------------
# placing something in it
# ---------------------------------------------------------------------------
def _point_at(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _piece_rect(candidate, size: float):
    half = size / 2.0
    return (candidate[0] - half, candidate[1] - half,
            candidate[0] + half, candidate[1] + half)


def _overlaps(one, other) -> bool:
    return not (one[2] <= other[0] or other[2] <= one[0]
                or one[3] <= other[1] or other[3] <= one[1])


#: Float slack on the lane comparison. A gap derived to be exactly passable
#: must not report as impassable because the arithmetic that produced it and
#: the arithmetic that checks it disagree in the last bit.
GAP_TOLERANCE = 1e-6


def _lane_gap(a, b):
    """Width of the corridor between two rects, or ``None`` if there isn't one.

    Two rects form a lane when they overlap on one axis and are separated on
    the other: that separation IS the corridor an agent has to fit down.
    Overlapping on both axes is not a lane, it is a collision; touching on both
    is a wall, which is solid and honest. Only the in-between case can look
    walkable in the scene and be missing from the navmesh.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    x_overlap = min(ax1, bx1) - max(ax0, bx0)
    y_overlap = min(ay1, by1) - max(ay0, by0)
    if x_overlap > 0.0 and y_overlap <= 0.0:
        return -y_overlap
    if y_overlap > 0.0 and x_overlap <= 0.0:
        return -x_overlap
    return None


#: Thickness of the perimeter walls `lot._outdoor_nodes` lays around the ground
#: rect, mirrored from `lot.WALL_THICK`. Carried rather than imported for the
#: same reason as every other cross-tool constant here.
PERIMETER_THICKNESS = 0.3


def perimeter_rects(ground, thickness: float = PERIMETER_THICKNESS) -> list:
    """The four walls `_outdoor_nodes` builds around the site's ground rect.

    Cover is placed on open ground, and the edge of open ground is a wall. The
    pinch check originally measured against building footprints only, so a piece
    parked near the site boundary could close the lane along it and nothing
    upstream noticed -- which is the shape of defect that produces a bot stuck
    in a corner with every offline check green.
    """
    if not ground:
        return []
    x0, y0, x1, y1 = ground
    half = thickness / 2.0
    return [
        (x0 - half, y1 - half, x1 + half, y1 + half),   # north
        (x0 - half, y0 - half, x1 + half, y0 + half),   # south
        (x1 - half, y0 - half, x1 + half, y1 + half),   # east
        (x0 - half, y0 - half, x0 + half, y1 + half),   # west
    ]


def pinches(pieces, rects, *, nav_bake=None) -> list:
    """Lanes this cover closed to something narrower than an agent can pass.

    The read-back. `site_spawns._opening_findings` established the shape: the
    search decides where a thing MAY go and the report describes the search, so
    a defect in the search reports itself as fine. Measuring the emitted
    rectangles is the only check that can disagree with the placer.

    A gap of zero is not reported. A piece flush against a wall is a wall --
    solid, visible, and nothing tries to walk it. What strands a bot is the
    lane that survives in the scene and not in the bake.

    A lane of exactly the minimum is the contract MET, not broken, so the
    comparison carries a tolerance. Without it `building_clearance` -- which is
    derived to produce exactly that width -- lands a hair under it in floating
    point and reports every piece it places as a defect.
    """
    minimum = min_passable_gap(nav_bake) - GAP_TOLERANCE
    out = []
    for piece in pieces:
        for other, label in ([(r, "a building") for r in rects] +
                             [(p.rect, p.name) for p in pieces if p is not piece]):
            gap = _lane_gap(piece.rect, other)
            if gap is not None and 1e-9 < gap < minimum:
                out.append((piece.name, label, round(gap, 3)))
    return out


def _grow(rect, margin: float):
    """A rect with ``margin`` added on every side."""
    if not margin:
        return tuple(rect)
    x0, y0, x1, y1 = rect
    return (x0 - margin, y0 - margin, x1 + margin, y1 + margin)


def _usable(candidate, *, ground, rects, markers, placed, size: float) -> bool:
    """Every reason a geometrically-correct position is still the wrong one.

    Tested as a footprint rather than as a point, which is not a refinement: a
    three-metre crate whose centre sits at the edge of a building's clearance
    still puts its face half a metre from the wall, and half a metre is less
    than the 0.4 m radius Godot erodes the navmesh by -- so the lane beside it
    bakes as unwalkable and the piece Lot placed for tactics has taken away a
    route. Since ``rects`` arrive already grown by `BUILDING_CLEARANCE`, an
    overlap test against them is the whole guarantee that cover can never seal
    an alley: a lane too narrow to hold a piece with room either side refuses
    one instead, and refusing is the right answer.

    The rest: on the site, off the markers, and clear of the other pieces --
    because two crates in contact are a wall, and a wall across a street is a
    route the crew no longer has.
    """
    piece = _piece_rect(candidate, size)
    if ground is not None and not (
            _inside((piece[0], piece[1]), ground)
            and _inside((piece[2], piece[3]), ground)):
        return False
    if any(_overlaps(piece, rect) for rect in rects):
        return False
    if any(math.dist(candidate, m) < MARKER_CLEARANCE for m in markers):
        return False
    return all(math.dist(candidate, (c.x, c.y)) >= COVER_SEPARATION
               for c in placed)


def _place_on(line, *, ground, rects, markers, placed, height, bias, size,
              crew=None):
    """A position on ``line`` that breaks it and offends nothing, nearest ``bias``.

    ``bias`` is measured from the crew's end, which has to be established rather
    than assumed: `open_sightlines` names its pairs in a stable order and that
    order is alphabetical, so on the site this was written for the "crew end"
    of ``Enemy_0 -> LT_PlayerSpawn`` was the enemy. A bias applied to the wrong
    end is worse than none -- it hands the enemy the wall to hold and leaves the
    crew crossing the open part.

    Searching outward from the preferred position rather than scanning from one
    end keeps the bias meaningful when the preferred spot is taken: the piece
    moves as little as it has to, and a street with three lines crossing it ends
    up with three pieces spread along it rather than three clustered at one end.
    """
    interval = break_interval(height)
    if interval is None:
        return None
    lo, hi = interval
    if crew is not None and line[1] == crew:
        bias = 1.0 - bias
    elif crew is not None and line[0] != crew:
        bias = 0.5           # neither end is the crew: no approach to bias to
    target = lo + (hi - lo) * bias
    steps = int((hi - lo) / SEARCH_STEP) + 1
    for step in range(steps + 1):
        for direction in (1, -1):
            t = target + direction * step * SEARCH_STEP
            if not (lo <= t <= hi):
                continue
            candidate = _point_at(line[2], line[3], t)
            if _usable(candidate, ground=ground, rects=rects, markers=markers,
                       placed=placed, size=size):
                return candidate
            if step == 0:
                break
    return None


#: The marker `site_spawns` writes the crew's spawn as, and the end cover is
#: biased towards. Named rather than positional because the caller passes a
#: dict and the name is the only thing that says which end walks.
CREW_MARKER = "LT_PlayerSpawn"

#: Marker-name prefix for an enemy spawn, as `lot.py` builds `cover_points`.
ENEMY_PREFIX = "Enemy_"

#: How far apart to sample the crew's route when asking what can shoot it while
#: it walks. The crew moves at 4.5 m/s, so 15 m is about three seconds of
#: walking: fine enough that no meaningful stretch of the approach goes unasked,
#: coarse enough that a 200 m route does not produce a hundred lines.
ROUTE_SAMPLE_SPACING = 15.0

#: Metres of route per piece of route cover. The budget has to scale with the
#: site or it is a constant pretending to be a rule: twelve pieces is generous
#: on a 40 m approach and nothing at all on a 250 m one.
ROUTE_METRES_PER_PIECE = 25.0


def route_samples(route, *, spacing: float = ROUTE_SAMPLE_SPACING):
    """Points along the crew's path, every ``spacing`` metres.

    Endpoints are omitted: they are already markers in ``points`` and the
    marker pass has asked about them. What this adds is the ground BETWEEN
    them, which nothing was asking about before.
    """
    out = []
    if not route or len(route) < 2:
        return out
    for a, b in zip(route, route[1:]):
        leg = math.dist(a, b)
        if leg <= spacing:
            continue
        step = 1
        while step * spacing < leg - 1e-6:
            f = (step * spacing) / leg
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            step += 1
    return out


def route_sightlines(samples, points: dict, rects, *, envelope: float):
    """Where an enemy can see and shoot the crew's route as it walks it.

    Complementary to `open_sightlines`, and filtered the opposite way on
    purpose. That function asks about the OPENING: pairs of markers further
    apart than the range at which the fight starts, because a long open line
    between two spawns means somebody fires at t=0. This one asks about
    TRANSIT: stretches of the crew's path that lie WITHIN an enemy's reach with
    nothing in between. A route point 20 m from an enemy with clear ground
    between them is not a standoff problem, it is the crew walking through
    somebody's field of fire, and the answer to it is the same -- something to
    hide behind -- but no marker pair describes it.

    Measured on `category5_baie_dore_001` seed 5017: the crew crossed 74 m from
    spawn to objective with all four pieces of cover clustered at the far end,
    10.8-19.3 m from an enemy spawn. Every marker pair was answered and the
    approach was still bare, because no marker pair was ever on it.
    """
    out = []
    enemies = [n for n in sorted(points) if n.startswith(ENEMY_PREFIX)]
    for index, sample in enumerate(samples):
        for name in enemies:
            other = points[name]
            length = math.dist(sample, other)
            if length > envelope:
                continue
            if open_span(sample, other, rects) < length - 1e-6:
                continue
            out.append((f"route@{index}", name, sample, other, length))
    out.sort(key=lambda line: -line[4])
    return out


def plan_cover(points: dict, rects, ground, *, opening_range: float,
               height: float = COVER_HEIGHT, size: float = COVER_SIZE,
               bias: float = APPROACH_BIAS, limit: int = 12,
               clearance: float = None,
               nav_bake=None,
               perimeter_thickness: float = PERIMETER_THICKNESS,
               crew: str = CREW_MARKER,
               route=None,
               route_spacing: float = ROUTE_SAMPLE_SPACING,
               route_metres_per_piece: float = ROUTE_METRES_PER_PIECE) -> CoverPlan:
    """Cover for every open sightline this site opens fire along.

    ``points`` is the mission markers by name -- crew spawn, enemies,
    objective, extraction -- in site space. ``rects`` are the building
    footprints *as built*, and ``ground`` is the walkable extent; the room a
    piece needs beside a wall is added here rather than by the caller.

    Placed one line at a time, longest first, re-measuring after each: a piece
    put on the worst sightline frequently breaks two others as a side effect,
    and a producer that placed one per line would litter the street with
    redundant crates and narrow every route on the site for nothing.

    ``route`` is the crew's path -- spawn, objective, extraction -- and when it
    is given a second pass covers the ground BETWEEN those markers. Marker pairs
    alone answer the opening and nothing else: on seed 5017 every pair was
    answered and the crew still crossed 74 m of bare approach, because the
    approach is not a marker pair. Its budget scales with the route's length
    rather than sharing the flat ``limit``, so a long walk is not left bare by a
    short one having spent the allowance.
    """
    plan = CoverPlan()
    # Derived from the agent contract unless a caller overrides it, so the room
    # a piece needs beside a wall follows the bake rather than a constant that
    # was right for one footprint.
    if clearance is None:
        clearance = building_clearance(size, nav_bake)
    markers = list(points.values())
    # Two different questions, so two different sets of rects, and asking both
    # of one set is how this module first came back with nothing to place on a
    # site that was almost entirely empty ground.
    #
    # "Can these two see each other" is asked of the walls as built. "Where can
    # a crate stand" is asked of the walls plus the room a crate needs beside
    # them. Growing the footprints once and using them for both looks tidier and
    # is wrong in a way that hides: `open_span` deliberately ignores a rect that
    # contains an endpoint, because a marker indoors can see out of its own
    # building -- and a spawn placed a metre clear of a wall is *inside* that
    # wall's rect once the rect has been grown by two. So the building stopped
    # counting as an occluder, a line running through two of them measured as
    # seventy metres of open ground, and every position along it was then
    # correctly refused for standing in a building. Nine sightlines, no cover,
    # and a finding blaming the site's massing for the module's arithmetic.
    #
    # Growing here rather than at the call site means a caller passes the
    # footprints it has and cannot get this wrong on Lot's behalf.
    measured = list(rects)
    placeable = [_grow(rect, clearance) for rect in rects]
    # A line nothing could stand on stays refused. Re-measuring after each
    # placement would otherwise hand it straight back, and the loop would spend
    # its whole budget failing to break the same lane.
    refused: set = set()

    def outstanding():
        lines = [line for line in open_sightlines(points, measured,
                                                  limit=opening_range)
                 if (line[0], line[1]) not in refused]
        # THE CREW'S LINES FIRST. `open_sightlines` returns longest first, on
        # the reasoning that the worst line's fix usually shortens three
        # others -- which is sound and is kept, INSIDE each group, because
        # sorting stably on one boolean leaves the existing order alone.
        #
        # Longest-first ALONE spent this site's whole 12-piece opening budget
        # without placing one piece on a line the crew stands on. Measured on
        # the `test_site_cover` yard: 12 pieces, 0 involving the crew, 6 of
        # them breaking enemy-to-enemy lines -- cover so one enemy cannot see
        # another, which says nothing about who opens fire on the crew -- and
        # the shipped scene left a clear 51.9 m lane from the crew spawn to
        # the nearest enemy. `unbreakable` was 0 the whole time, so a spot
        # existed and the budget had simply gone elsewhere.
        #
        # The opening engagement is who can shoot the CREW at t=0. With the
        # same budget, three pieces now close all seven of its lines.
        return sorted(lines, key=lambda line: crew not in (line[0], line[1]))

    remaining = outstanding()
    while remaining and len(plan.cover) < limit:
        line = remaining[0]
        spot = _place_on(line, ground=ground, rects=placeable, markers=markers,
                         placed=plan.cover, height=height, bias=bias,
                         size=size, crew=crew)
        if spot is None:
            plan.unbreakable.append(line)
            refused.add((line[0], line[1]))
            remaining = [other for other in remaining
                         if (other[0], other[1]) not in refused]
            continue
        piece = Cover(name=f"Cover_{len(plan.cover)}", x=spot[0], y=spot[1],
                      size=size, height=height,
                      breaks=f"{line[0]} -> {line[1]}", span=line[4])
        plan.cover.append(piece)
        # A placed piece is a wall for the next measurement and an obstacle for
        # the next placement, and it needs its own separation rather than the
        # buildings' -- which `_usable` applies from `placed`, so the rect goes
        # in unchanged.
        measured = measured + [piece.rect]
        placeable = placeable + [piece.rect]
        remaining = outstanding()
    plan.open_lines = remaining

    # Second pass: the walk, not the opening.
    #
    # Deliberately after the marker pass and on its own budget. The marker
    # lines describe who can shoot whom at t=0 and are the more urgent
    # statement; sharing one allowance would let a site with nine long spawn
    # lines spend everything before reaching the approach, which is exactly how
    # a 74 m walk ended up with four pieces of cover at the far end of it.
    samples = route_samples(route, spacing=route_spacing) if route else []
    if samples:
        route_length = sum(math.dist(a, b) for a, b in zip(route, route[1:]))
        budget = max(1, int(math.ceil(route_length / route_metres_per_piece)))
        # The samples join the markers a piece has to stand clear of, so cover
        # lands beside the lane instead of in it. Cover the crew has to walk
        # around is an obstacle; cover it can walk behind is cover.
        markers = markers + samples
        refused_route: set = set()

        def outstanding_route():
            return [line for line in route_sightlines(
                        samples, points, measured, envelope=opening_range)
                    if (line[0], line[1]) not in refused_route]

        pending = outstanding_route()
        placed_here = 0
        while pending and placed_here < budget:
            line = pending[0]
            spot = _place_on(line, ground=ground, rects=placeable,
                             markers=markers, placed=plan.cover, height=height,
                             bias=bias, size=size, crew=line[0])
            if spot is None:
                refused_route.add((line[0], line[1]))
                pending = [other for other in pending
                           if (other[0], other[1]) not in refused_route]
                continue
            plan.cover.append(Cover(
                name=f"Cover_{len(plan.cover)}", x=spot[0], y=spot[1],
                size=size, height=height,
                breaks=f"{line[0]} -> {line[1]}", span=line[4]))
            measured = measured + [plan.cover[-1].rect]
            placeable = placeable + [plan.cover[-1].rect]
            placed_here += 1
            pending = outstanding_route()
        plan.route_open = pending

    # Read back what was emitted. Everything above is the search's account of
    # itself; this is the geometry.
    #
    # Measured against every solid the site has, not just the buildings. The
    # first version of this check used `rects` alone and reported ZERO pinches
    # on seed 5320 while Laser Tag counted 835 player-stuck events across 25
    # runs -- the guardrail was not wrong, it was blind to three quarters of
    # what a piece can pinch against. The perimeter is computed here rather
    # than asked of the caller for the same reason the building rects are grown
    # here: a caller passes what it has and cannot get this wrong on Lot's
    # behalf.
    plan.pinches = pinches(
        plan.cover, list(rects) + perimeter_rects(ground, perimeter_thickness),
        nav_bake=nav_bake)
    return plan


def findings(plan: CoverPlan, *, opening_range: float) -> list:
    """What the producer should say about the cover it just placed.

    All advisory. A site with an open sightline is a site Laser Tag will play
    and mark down, which is a design signal and not a build failure -- the same
    split the evaluator's own findings are read under. The one thing worth
    saying loudly is a line nothing could break, because that is a request for a
    building and no amount of street furniture will answer it.
    """
    out = []
    if plan.cover:
        worst = max(c.span for c in plan.cover)
        out.append({
            "code": "LOT_COVER_PLACED",
            "severity": "minor",
            "category": "cover",
            "message": (
                f"{len(plan.cover)} piece(s) of {plan.cover[0].height:g} m cover "
                f"were placed to break sightlines the site left open past the "
                f"{opening_range:g} m at which Laser Tag opens fire (longest "
                f"{worst:.1f} m). Without them the crew and the enemies can "
                f"shoot each other from their spawns, which stamps first "
                f"contact at zero and stops the crew's bot walking its route."),
        })
    if plan.unbreakable:
        worst = max(line[4] for line in plan.unbreakable)
        pairs = ", ".join(f"{a} -> {b}" for a, b, _pa, _pb, _d in
                          plan.unbreakable[:3])
        out.append({
            "code": "LOT_SIGHTLINE_UNBREAKABLE",
            "severity": "moderate",
            "category": "cover",
            "message": (
                f"{len(plan.unbreakable)} sightline(s) over {opening_range:g} m "
                f"had nowhere on open ground to stand cover that would break "
                f"them ({pairs}; longest {worst:.1f} m). This is a request for a "
                f"building rather than street furniture -- the site's massing "
                f"leaves a lane with no room in it for a solid that is clear of "
                f"the walls, the markers and the other pieces."),
        })
    if plan.pinches:
        worst = min(gap for _n, _w, gap in plan.pinches)
        where = ", ".join(f"{n} vs {w} ({gap:g} m)" for n, w, gap in plan.pinches[:3])
        out.append({
            "code": "LOT_COVER_PINCH",
            "severity": "moderate",
            "category": "navigation",
            "message": (
                f"{len(plan.pinches)} lane(s) were closed by this site's own "
                f"cover to less than the {min_passable_gap():g} m an agent can "
                f"walk through ({where}; narrowest {worst:g} m). The scene will "
                f"show a gap and the navmesh will not have one: erosion removes "
                f"ceil(agent_radius/cell_size) whole voxels per side, so a lane "
                f"under that width is not narrow, it is absent. This is the "
                f"agent contract's own door-width derivation applied to street "
                f"furniture, and a bot meeting one of these reads as stuck."),
        })
    route_pieces = [c for c in plan.cover if c.breaks.startswith("route@")]
    if route_pieces:
        out.append({
            "code": "LOT_ROUTE_COVER_PLACED",
            "severity": "minor",
            "category": "cover",
            "message": (
                f"{len(route_pieces)} of the {len(plan.cover)} piece(s) were "
                f"placed along the crew's route rather than on a marker pair. "
                f"Marker pairs describe the opening; they say nothing about the "
                f"ground the crew crosses afterwards, and cover budgeted only "
                f"against them lands at the objective where the enemies already "
                f"are."),
        })
    if plan.route_open:
        worst = max(line[4] for line in plan.route_open)
        where = ", ".join(f"{a} -> {b}" for a, b, _pa, _pb, _d in
                          plan.route_open[:3])
        out.append({
            "code": "LOT_ROUTE_EXPOSED",
            "severity": "moderate",
            "category": "cover",
            "message": (
                f"{len(plan.route_open)} stretch(es) of the crew's route lie "
                f"within {opening_range:g} m of an enemy spawn across open "
                f"ground with nothing to hide behind ({where}; longest "
                f"{worst:.1f} m). This is not a standoff problem -- the crew is "
                f"inside the firing envelope while it walks, so the bot takes "
                f"hits it cannot answer and its cover-seek has nothing in reach "
                f"to break for."),
        })
    if plan.open_lines:
        worst = max(line[4] for line in plan.open_lines)
        out.append({
            "code": "LOT_SIGHTLINE_OPEN",
            "severity": "minor",
            "category": "cover",
            "message": (
                f"{len(plan.open_lines)} sightline(s) remain open past "
                f"{opening_range:g} m after cover was placed (longest "
                f"{worst:.1f} m) -- the cover budget of this site was spent on "
                f"the worse ones. Laser Tag will play the map and grade the "
                f"exposure; it is a design note, not a broken level."),
        })
    return out
