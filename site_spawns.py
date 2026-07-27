"""Where the enemies stand, and whether the crew can get to them.

Lot's half of the Laser Tag map contract (LaserTag TDD 8) used to place enemy
spawns by sampling the straight line crew-spawn -> objective -> extraction,
kicking each sample a metre and a half to one side, and lifting it a metre
above a height interpolated between the two ends of the segment it fell on. On
an empty field that is a reasonable engagement sequence. On a site, it runs the
whole sequence through the middle of whatever buildings the route passes.

The site that produced this module has four 44 m shells strung along its main
axis. All six enemies landed inside two of them, every one of them with a slab
beneath it -- so nothing downstream that asked "is this point floored" objected.
Laser Tag then asked the question that matters, which is whether each enemy can
*path* to the crew, refused the map with UNREACHABLE_SPAWN, and reported zero
runs after the full timeout. The map was graded BROKEN on account of six markers
placed by arithmetic that had never heard of the buildings.

So placement is done against the geometry Lot has already decided on. A spawn
goes on the street: outside every footprint, inside the ground rect, far enough
from the crew that first contact is not immediate, and at the ground plane
rather than at an interpolated height. Where no such position exists the enemy
is not emitted and Lot says which one and why -- a spawn Lot cannot defend is
worse than a spawn Lot does not write, because the first one costs a full
evaluation to discover.

Pure: dicts in, positions and findings out. No Godot, no Blender, stdlib only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Clearance kept between a spawn and a building wall. Godot bakes this site's
#: navmesh with a 0.4 m agent radius, which erodes the walkable surface by that
#: much from every solid; a spawn inside the eroded band has a floor and no
#: navmesh polygon, which is UNREACHABLE_SPAWN again by a narrower route.
WALL_MARGIN = 1.0

#: Same idea at the outside edge of the site.
EDGE_MARGIN = 1.0

#: Nearer than this and the crew is in contact before it has moved. Laser Tag
#: grades that as INSTANT_CONTACT and NO_REACTION_TIME.
#:
#: A floor, not the rule. It was written as the rule, and it was chosen by
#: eye -- see `OPENING_RANGE` for what the number needed to be measured
#: against, and `site_cover` for what is actually done about the ground in
#: between.
MIN_STANDOFF = 8.0

#: How far apart the two sides have to be before neither can open fire, which
#: is not the same number as the enemy's sight range and was written here as if
#: it were.
#:
#: ``enemy_sight_range = 35.0`` in ``default_laser_tag_scenario.tres``, and that
#: is a real number correctly read from the scenario Level Factory runs. It is
#: also only half the engagement. ``LT_BotPlayerController`` carries
#: ``@export var sight_range: float = 45.0`` -- ten metres further than the
#: enemy it is hunting -- and nothing overrides it: ``LT_MapEvalHarness``
#: assigns ``brain.sight_range`` from the scenario and has no matching line for
#: the bot, and the scenario resource has no player sight field at all. So the
#: crew sees first, its ``_fire_timer`` starts at zero, and
#: ``LT_MetricsCollector.record_shot`` stamps ``time_to_first_contact`` on the
#: first shot fired by *either* side. An enemy 39 m from the crew spawn is
#: outside every number Lot was checking and inside the only one that decides
#: the clock.
#:
#: The second half is worse than a mis-stamped clock. The bot's route only
#: advances in the ``else`` of "can I see an enemy", and ``LT_EnemyBrain`` has
#: no range gate at all, so a crew that can see one enemy never walks again and
#: the sightline never clears. One visible enemy is 0% route completion by
#: construction, on every seed.
#:
#: A stated assumption in the sense `DEFAULT_FOOTPRINT` is: Lot cannot read the
#: Laser Tag checkout, so it carries the number and names where it came from.
#: Level Factory's `packages.validation.lasertag_contract` reads the real files
#: and reports drift against what is written here, so this going stale is a
#: finding rather than a silent five-seed run.
#:
#: The distance was never the mechanism though -- an enemy 20 m away around a
#: corner is a fair fight and an enemy 30 m away down an open street is not --
#: so distance alone is not what the search below tests, and `site_cover` is
#: what does something about the open street.
OPENING_RANGE = 45.0

#: The name this carried when it was believed to be the enemy's sight range.
#: Kept so a caller that reads it gets the number that decides the fight rather
#: than the one that used to be here.
SIGHT_RANGE = OPENING_RANGE

#: What the crew walks at: ``LT_BotPlayerController.move_speed = 4.5``.
CREW_SPEED = 4.5

#: How long the crew gets before anybody can fire.
#:
#: `OPENING_RANGE` on its own says "neither side can open fire from here", and
#: an enemy standing at exactly that distance satisfies it while buying the crew
#: nothing: both sides acquire on the same frame the map starts, because the
#: distance is the acquisition threshold rather than something short of it. The
#: crew needs the fight to start after it has had a chance to move, so the
#: standoff is the range plus the ground the crew covers in the time it is being
#: given.
#:
#: One second is the floor, not a target. It is roughly a human reaction plus a
#: step, and it is what separates "the map opened with a shot" from "the map
#: opened".
REACTION_SECONDS = 1.0

#: The daylight that buys, kept beyond `OPENING_RANGE` before an enemy in the
#: open counts as a fair opening.
OPENING_CLEARANCE = CREW_SPEED * REACTION_SECONDS

#: How far a sample may be pushed off its route before the search gives up and
#: reports. Generous on purpose: on a site whose buildings are 44 m across, the
#: nearest street can be twenty-odd metres from the line through the middle.
MAX_PUSH = 80.0
PUSH_STEP = 0.5

#: Enemies closer together than this are one encounter wearing six hats.
MIN_SEPARATION = 4.0

#: How far along the route a sample may be slid when no perpendicular offset
#: satisfies the constraints. Perpendicular search alone cannot fix an opening
#: engagement: pushing sideways off a straight street keeps the enemy in the
#: same open sightline, only further out. Sliding the sample down the route
#: moves it towards the next block, which is where the cover is. A twentieth of
#: the route at a time, and never past the end of it.
SLIDE_STEP = 0.05

#: The site ground's walking surface. Lot seats its ground slabs so the top
#: face is exactly z = 0 in site space (`GROUND_THICK` below the plane), so a
#: spawn standing on the street stands here -- not at a height interpolated
#: between two markers that happen to be on furniture.
GROUND_Z = 0.0

#: What a Laser Tag agent can step up without a ladder or a stair. A marker
#: this far above the floor or less is standing on a kerb; further, and the
#: route to it has to exist as geometry.
AGENT_CLIMB = 0.5

#: The tallest thing Lot is willing to call furniture. Between `AGENT_CLIMB`
#: and this, a marker above the floor is on a counter, a crate or a desk, and
#: seating its nav hook on the floor is the right reading. Above it, the drop
#: is a storey -- and Lot has no storey model, so it says so and moves nothing
#: rather than dropping a nav hook through a floor into the room below.
FURNITURE_MAX = 2.0

#: The pill Laser Tag walks, and Lot's own authored navmesh agent height.
AGENT_HEIGHT = 1.8

#: How far a nav hook may be moved sideways to get off a prop. A hook names a
#: spot in a particular room; walking it across the site to find open floor
#: would trade a blocker for a mission that no longer happens where it was
#: designed to happen. Six metres clears the deepest counter Deli Counter bakes
#: and still lands inside the room that counter is in.
RESOLVE_RADIUS = 6.0

#: Lattice spacing for that search. Fine enough to find the gap beside a 1 m
#: deep counter, coarse enough that a 6 m disc is a few thousand tests.
RESOLVE_STEP = 0.25


@dataclass
class Placement:
    """Where the enemies went, and what could not be honoured."""

    positions: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    pushed: list = field(default_factory=list)
    #: ``(index, distance_from_crew_spawn)`` for enemies that had to be moved
    #: further along the route because their designed position had the crew in
    #: the open at spawn time.
    slid: list = field(default_factory=list)
    findings: list = field(default_factory=list)


def footprint_rect(bdef, margin: float = 0.0):
    """A building's axis-aligned footprint in site space, or ``None``.

    One reader, shared with the ground: `site_extent.rotated_footprint` is what
    sizes the plate and what cuts the hole, so the rect a spawn is kept out of
    is the same rect the building stands on. This function used to carry its own
    copy of the rotation arithmetic and its own idea of where a footprint comes
    from -- it read ``_footprint`` only, while `site_extent` also accepts the
    ``footprint`` key a site record uses -- so a building described the second
    way was invisible here and enemies could be placed inside it.
    """
    import site_extent
    rect = site_extent.rotated_footprint(bdef)
    if rect is None:
        return None
    return site_extent.grow(rect, margin) if margin else rect


def footprints(site_spec, margin: float = WALL_MARGIN) -> list:
    rects = []
    for bdef in site_spec.get("buildings", []) or []:
        rect = footprint_rect(bdef, margin)
        if rect:
            rects.append(rect)
    return rects


def ground_rect(site_spec, margin: float = EDGE_MARGIN):
    """The walkable extent of the site, inset by ``margin``, or ``None``.

    ``None`` means this site declares no ground. That is not an error here --
    a site can be all interior -- but it does mean this module has nothing to
    place against, and the caller is told rather than handed guesses.

    The extent comes from `site_extent.resolve`, which is the same rect
    `lot._outdoor_nodes` lays the tiles down as. This module used to derive it
    from the declared size on the assumption the plate was centred on the
    origin; on a site whose row is not centred that put every enemy spawn on a
    plate 66 m from where the ground actually was.
    """
    import site_extent
    rect = site_extent.resolve(site_spec).rect
    if rect is None:
        return None
    x0, y0, x1, y1 = rect
    if (x1 - x0) <= 2 * margin or (y1 - y0) <= 2 * margin:
        return None
    return (x0 + margin, y0 + margin, x1 - margin, y1 - margin)


def _inside(point, rect) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def outdoors(point, ground, rects) -> bool:
    """True when a standing agent at ``point`` is on open site ground."""
    if ground is not None and not _inside(point, ground):
        return False
    return not any(_inside(point, r) for r in rects)


def _segment_crosses(a, b, rect) -> bool:
    """True when the segment ``a``-``b`` passes through the axis-aligned rect.

    Liang-Barsky slab clipping. Touching a corner counts as crossing, which is
    the conservative direction here: it says a wall blocks sight when it barely
    does, and the cost of that is an enemy placed further from the crew than it
    strictly had to be.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    t_enter, t_exit = 0.0, 1.0
    for p, q in ((-dx, a[0] - rect[0]), (dx, rect[2] - a[0]),
                 (-dy, a[1] - rect[1]), (dy, rect[3] - a[1])):
        if abs(p) < 1e-12:
            if q < 0:                      # parallel to this slab and outside it
                return False
            continue
        t = q / p
        if p < 0:
            if t > t_exit:
                return False
            t_enter = max(t_enter, t)
        else:
            if t < t_enter:
                return False
            t_exit = min(t_exit, t)
    return t_enter <= t_exit


def has_line_of_sight(a, b, rects) -> bool:
    """True when nothing Lot knows about stands between ``a`` and ``b``.

    Buildings are the only occluders Lot can be sure of -- a shell is solid from
    the outside whatever is in it. Props and street furniture are not counted:
    they are shorter than a standing agent's eyeline more often than not, and a
    sightline model that credits a planter with cover is worse than one that
    admits it only knows about walls.

    A rect containing either endpoint is skipped. You are not hidden by the
    building you are standing in, and treating it as cover would let the whole
    check pass on a crew spawn that landed indoors -- which is exactly the case
    this is guarding.
    """
    for rect in rects:
        if _inside(a, rect) or _inside(b, rect):
            continue
        if _segment_crosses(a, b, rect):
            return False
    return True


def opening_engagement_is_fair(candidate, spawn, occluders,
                               opening_range: float = OPENING_RANGE,
                               clearance: float = OPENING_CLEARANCE) -> bool:
    """True when an enemy here cannot shoot the crew before it has moved.

    Either it is further away than *either* side can open fire from with a
    second of daylight on top, or a building stands between the two. Both are
    checked at the spawn point rather than along the route on purpose: the
    crew's first second is the only moment it has no cover, no information and
    no ability to react, and that is the moment Laser Tag measures as
    ``time_to_first_contact``.

    The range defaults to `OPENING_RANGE`, which is the crew's reach and not the
    enemy's -- the crew sees ten metres further and shoots first, so the enemy's
    35 m answers the wrong question. `OPENING_CLEARANCE` is the part that was
    missing after that: a distance *equal* to the acquisition threshold is not
    a standoff, it is the threshold, and it starts the fight on frame one just
    as surely as standing next to the crew does.
    """
    if math.dist(candidate, spawn) >= opening_range + clearance:
        return True
    return not has_line_of_sight(candidate, spawn, occluders)


def _fractions(index: int, count: int, step: float = SLIDE_STEP):
    """Where along the route to sample for enemy ``index``, nearest first.

    The even spread is the design; the slide is the fallback for when it cannot
    be honoured. Sliding forward rather than back means an enemy that cannot be
    placed fairly ends up deeper into the mission, never behind the crew.
    """
    start = (index + 1) / (count + 1)
    fraction = start
    while fraction <= 1.0 + 1e-9:
        yield min(fraction, 1.0)
        fraction += step


def _candidates(index: int, count: int, total: float, *, lateral: float,
                max_push: float = MAX_PUSH, push_step: float = PUSH_STEP,
                slide_step: float = SLIDE_STEP) -> list:
    """``(fraction, offset)`` pairs ordered by how far they deviate from design.

    Two ways to move an enemy that cannot stand where it was designed to: push
    it sideways off the route, or slide it further along the route. Searching
    one before the other decides the answer by loop order rather than by which
    is the smaller change -- push-first walks a spawn eighty metres out into a
    field to escape a sightline the next block would have broken for free.

    So both are priced in metres of deviation and the cheapest is taken. The
    designed lateral kick is free; everything past it costs what it moves. Ties
    resolve towards the earlier fraction and then towards the offset order,
    which keeps placement deterministic for a given site.
    """
    start = (index + 1) / (count + 1)
    scored = []
    for fi, fraction in enumerate(_fractions(index, count, slide_step)):
        slide = (fraction - start) * total
        for oi, offset in enumerate(_offsets(lateral, max_push, push_step)):
            cost = slide + max(0.0, abs(offset) - lateral)
            scored.append((cost, fi, oi, fraction, offset))
    scored.sort(key=lambda c: (c[0], c[1], c[2]))
    return [(c[3], c[4]) for c in scored]


def _route_point(route, lengths, total, fraction):
    """``(point, direction)`` at ``fraction`` of the way along the polyline."""
    target = total * fraction
    walked = 0.0
    for (a, b), length in zip(zip(route, route[1:]), lengths):
        if walked + length >= target:
            t = (target - walked) / length
            point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            return point, (b[0] - a[0], b[1] - a[1])
        walked += length
    a, b = route[-2], route[-1]
    return (b[0], b[1]), (b[0] - a[0], b[1] - a[1])


def _offsets(lateral: float, max_push: float, step: float):
    """Candidate perpendicular offsets, nearest first, alternating sides.

    Nearest-first matters: the enemy should end up on the street the route
    actually passes, not on whichever side of the block the search happened to
    scan first.
    """
    yield lateral
    yield -lateral
    distance = max(lateral, step)
    while distance <= max_push:
        distance += step
        yield distance
        yield -distance


def place_enemies(site_spec, positions, *, enemy_count: int = 6,
                  lateral: float = 1.5, standoff: float = MIN_STANDOFF,
                  separation: float = MIN_SEPARATION) -> Placement:
    """Enemy spawns along the mission route, on ground the crew can walk.

    ``positions`` is ``lot._walk_positions``' dict: site-space ``spawn``,
    ``objective`` and ``extraction``. The engagement sequence is unchanged --
    samples spread along the route, kicked alternately to either side -- and
    what is new is that a sample which lands in a building is pushed
    perpendicular until it clears one, instead of being written where it fell.
    """
    plan = Placement()
    count = max(0, int(enemy_count))
    if not count:
        return plan

    route = [tuple(positions[k][:2])
             for k in ("spawn", "objective", "extraction")]
    lengths = [max(1e-6, math.dist(a, b)) for a, b in zip(route, route[1:])]
    total = sum(lengths)
    rects = footprints(site_spec)
    ground = ground_rect(site_spec)
    spawn = route[0]

    if ground is None and not rects:
        # Nothing known to place against. Keep the old behaviour rather than
        # inventing constraints out of an empty site description, and say so.
        plan.findings.append({
            "code": "LOT_SPAWN_PLACEMENT_UNCHECKED",
            "severity": "moderate",
            "category": "spawn",
            "message": (
                "this site declares neither a ground rect nor any building "
                "footprint, so enemy spawns were placed along the mission "
                "route without being checked against geometry; if the map "
                "comes back with UNREACHABLE_SPAWN, this is why"),
        })

    # Sight is blocked by the buildings themselves, not by the margin kept
    # around them for the navmesh. Occluding with the grown rects would credit
    # a metre of open street on either side of every wall as cover.
    occluders = footprints(site_spec, margin=0.0)

    placed: list = []
    for i in range(count):
        side = 1.0 if i % 2 == 0 else -1.0
        chosen = None
        for fraction, offset in _candidates(i, count, total, lateral=lateral):
            base, direction = _route_point(route, lengths, total, fraction)
            norm = math.hypot(*direction) or 1.0
            perp = (-direction[1] / norm, direction[0] / norm)
            candidate = (base[0] + perp[0] * offset * side,
                         base[1] + perp[1] * offset * side)
            if not outdoors(candidate, ground, rects):
                continue
            if math.dist(candidate, spawn) < standoff:
                continue
            if any(math.dist(candidate, p) < separation for p in placed):
                continue
            # The rule the standoff number was standing in for.
            if not opening_engagement_is_fair(candidate, spawn, occluders):
                continue
            chosen = (candidate, abs(offset), fraction)
            break

        if chosen is None:
            plan.dropped.append(i)
            continue
        (cx, cy), pushed, fraction = chosen
        if pushed > lateral + 1e-6:
            plan.pushed.append((i, pushed))
        if fraction > (i + 1) / (count + 1) + 1e-9:
            plan.slid.append((i, math.dist((cx, cy), spawn)))
        placed.append((cx, cy))
        plan.positions.append((cx, cy, GROUND_Z))

    plan.findings.extend(_findings(plan, count, standoff, spawn, occluders))
    return plan


def seat_destinations(positions, *, floor: float = GROUND_Z,
                      climb: float = AGENT_CLIMB, solids=None,
                      bounds=None, agent_height: float = AGENT_HEIGHT,
                      radius: float = RESOLVE_RADIUS,
                      step: float = RESOLVE_STEP) -> tuple:
    """Put the mission's nav hooks on ground an agent can stand on.

    ``LT_ObjectivePoint`` is a *navigation* target, not the objective prop. The
    prop can sit on a counter -- a till, a safe, a case is meant to be up
    there. The nav hook cannot: Laser Tag's bot paths to it, and the site that
    produced this function put the hook 0.9 m up on a 1.1 m counter in a room
    whose floor is 0, with no step between. Against a 0.5 m climb limit no
    route to it exists, so the bot completed 0% of runs and the map came back
    blocked -- for a marker that was only ever describing where the prop goes.

    Lot already floors two of the three mission points: a site-level crew spawn
    and extraction are both read as ``(x, y, 0.0)`` regardless of the marker's
    own height. The objective was the one that took its z verbatim. This makes
    the third consistent with its siblings, and only within the range where
    "this is furniture" is the honest reading -- see ``FURNITURE_MAX``.

    Height alone is not enough, which cost a second full evaluation to learn.
    Dropping the hook's z to the floor left its *footprint* on the counter, and
    the navmesh takes its standing surface from the geometry under the point,
    not from the number in the marker: the cell still read 1.1 m up, still had
    no step to it, and the map came back refused with the same 0% completion.
    So when ``solids`` is supplied -- a ``site_collision.Reading`` for this
    site -- each hook is also moved sideways off whatever it is standing in,
    the shortest distance that reaches floor the bake will agree is walkable,
    and never outside ``bounds[key]`` when the caller knows which room the hook
    belongs to.

    Without ``solids`` the lateral pass does not run and nothing pretends it
    did: this function then does exactly what it did before, and the caller
    that skipped the geometry is the one that knows why.

    Returns ``(seated, findings)``; ``seated`` is a new dict, the input is left
    alone.
    """
    seated = dict(positions)
    findings: list = []
    for key in ("spawn", "objective", "extraction"):
        point = positions.get(key)
        if point is None:
            continue
        x, y, z = point
        drop = z - floor
        if drop <= climb:
            continue
        if drop > FURNITURE_MAX:
            findings.append({
                "code": "LOT_DESTINATION_ABOVE_FLOOR",
                "severity": "major",
                "category": "spawn",
                "message": (
                    f"the {key} marker stands {drop:.2f} m above the site "
                    f"ground plane, which is too tall to read as furniture, so "
                    f"Lot left it where the marker put it. If that height is a "
                    f"storey, the nav hook needs the stair or ladder that "
                    f"reaches it; if it is a prop, the marker's z is wrong. "
                    f"Laser Tag cannot path to it either way and reports "
                    f"TRAVERSAL with 0% completion."),
            })
            continue
        seated[key] = (x, y, floor)
        findings.append({
            "code": "LOT_DESTINATION_RESEATED",
            "severity": "minor",
            "category": "spawn",
            "message": (
                f"the {key} marker sat {drop:.2f} m above the floor -- on a "
                f"counter or a crate, further than the {climb:g} m an agent "
                f"can step -- so its navigation hook was seated on the floor "
                f"beneath it. Whatever prop the marker describes is unmoved; "
                f"what changed is the point Laser Tag's bot walks to, which "
                f"now has a route."),
        })
    if solids is not None:
        findings.extend(_resolve_laterally(
            seated, solids, floor=floor, climb=climb,
            agent_height=agent_height, radius=radius, step=step,
            bounds=bounds or {}))
    return seated, findings


def _resolve_laterally(seated: dict, solids, *, floor: float, climb: float,
                       agent_height: float, radius: float, step: float,
                       bounds: dict) -> list:
    """Move each nav hook off the prop it stands in. Mutates ``seated``."""
    import site_collision

    findings: list = []
    for key in ("spawn", "objective", "extraction"):
        point = seated.get(key)
        if point is None:
            continue
        outcome = site_collision.resolve_onto_floor(
            point, solids, floor=floor, climb=climb,
            agent_height=agent_height, radius=radius, step=step,
            bounds=bounds.get(key))
        if not outcome.needed:
            continue
        if not outcome.resolved:
            findings.append({
                "code": "LOT_DESTINATION_ON_PROP",
                "severity": "major",
                "category": "spawn",
                "message": (
                    f"the {key} nav hook stands inside {outcome.blocked_by}, "
                    f"and no floor an agent can both stand on and reach exists "
                    f"within {radius:g} m of it, so Lot left it where it was. "
                    f"Laser Tag's navmesh takes its standing surface from the "
                    f"geometry under the point: the hook is an island the bot "
                    f"cannot path to, which comes back as TRAVERSAL with 0% "
                    f"completion. Either the room needs clear floor beside "
                    f"that prop or the marker belongs somewhere else in it."),
            })
            continue
        seated[key] = outcome.point
        findings.append({
            "code": "LOT_DESTINATION_RESOLVED",
            "severity": "minor",
            "category": "spawn",
            "message": (
                f"the {key} nav hook stood inside {outcome.blocked_by} -- on "
                f"the prop, not beside it -- so it was moved "
                f"{outcome.moved:.2f} m to the nearest floor an agent can "
                f"stand on and walk to. The prop and the marker that describes "
                f"it are unmoved; what changed is the point Laser Tag's bot "
                f"paths to. Seating the hook's height alone did not fix this: "
                f"the navmesh reads the surface under the point, so a hook at "
                f"floor height inside a counter is still on the counter."),
        })
    if not getattr(solids, "complete", True):
        unread = list(getattr(solids, "unread", ()) or ())
        findings.append({
            "code": "LOT_DESTINATION_COLLISION_UNREAD",
            "severity": "moderate",
            "category": "collision",
            "message": (
                f"{len(unread)} geometry source(s) could not be read for "
                f"collision, so the nav hooks were checked against a partial "
                f"picture of the site and one may still be standing on "
                f"something Lot could not see: {'; '.join(unread[:4])}"
                f"{' ...' if len(unread) > 4 else ''}."),
        })
    return findings


def nearest_enemy(positions, spawn) -> tuple:
    """``(index, distance)`` of the placed enemy closest to the crew spawn.

    ``(None, inf)`` when nothing was placed. This is the number that describes
    the map -- as opposed to any number describing what the placer did -- and it
    is a function of the positions that were actually written, so a search that
    got the wrong answer cannot hide behind it.
    """
    if not positions:
        return None, math.inf
    index, distance = min(
        ((i, math.dist(p[:2], spawn)) for i, p in enumerate(positions)),
        key=lambda pair: pair[1])
    return index, distance


def _findings(plan: Placement, requested: int, standoff: float,
              spawn=None, occluders=None) -> list:
    out = []
    if plan.dropped:
        out.append({
            "code": "LOT_ENEMY_SPAWN_UNPLACEABLE",
            "severity": "major",
            "category": "spawn",
            "message": (
                f"{len(plan.dropped)} of {requested} enemy spawn(s) had no "
                f"position on open ground within {MAX_PUSH:g} m of the mission "
                f"route that is also at least {standoff:g} m from the crew "
                f"spawn and either beyond {OPENING_RANGE:g} m or behind a "
                f"building from it, so they were not written. Laser Tag will "
                f"evaluate "
                f"{len(plan.positions)} enemies instead of {requested}; a spawn "
                f"placed inside a building would have refused the whole map "
                f"with UNREACHABLE_SPAWN and scored nothing."),
        })
    if plan.pushed:
        worst = max(d for _, d in plan.pushed)
        out.append({
            "code": "LOT_ENEMY_SPAWN_PUSHED",
            "severity": "minor",
            "category": "spawn",
            "message": (
                f"{len(plan.pushed)} of {requested} enemy spawn(s) fell inside "
                f"a building footprint on the straight line through the "
                f"mission route and were moved to the nearest open ground "
                f"(furthest move {worst:.1f} m). The engagement sequence still "
                f"runs spawn to objective to extraction, but these enemies "
                f"stand off the route rather than on it."),
        })
    index, closest = (nearest_enemy(plan.positions, spawn)
                      if spawn is not None else (None, math.inf))
    if plan.slid:
        moved = min(d for _, d in plan.slid)
        on_map = (f"The nearest enemy on the map is now Enemy_{index} at "
                  f"{closest:.1f} m. " if index is not None else "")
        out.append({
            "code": "LOT_ENEMY_SPAWN_STANDOFF",
            "severity": "minor",
            "category": "spawn",
            "message": (
                f"{len(plan.slid)} of {requested} enemy spawn(s) had the crew "
                f"spawn in the open within {OPENING_RANGE:g} m -- the range "
                f"the crew's own bot opens fire at, which is ten metres "
                f"further than the enemy sees -- and were moved further along "
                f"the mission route until the crew was out of range or behind "
                f"a building (nearest of those now {moved:.1f} m). {on_map}"
                f"Without this the opening engagement starts before the crew "
                f"can move, which Laser Tag reports as INSTANT_CONTACT and "
                f"which ends the run in a team wipe inside ten seconds. "
                f"Distance is the blunt half of the fix; `site_cover` puts "
                f"something in the ground between them."),
        })
    out.extend(_opening_findings(plan, spawn, occluders, index, closest))
    return out


def _opening_findings(plan: Placement, spawn, occluders, index: int,
                      closest: float) -> list:
    """What the written spawns say about the crew's first second.

    Deliberately redundant with the search in `place_enemies`: the search
    decides where an enemy may stand, this reads back the positions that came
    out of it and asks the same question of them. The two agreeing costs a few
    microseconds. The two disagreeing is the finding, and it is the one class of
    defect the search cannot report on itself -- if the placer's model of what
    counts as cover is wrong, or the code that ran is not the code that was
    reviewed, every enemy passes on the way in and the map still opens with a
    shot.

    That is not hypothetical. Seed 5320 of ``category5_baie_dore_001`` wrote
    Enemy_0 23.0 m from the crew down a clear street, and the only finding the
    run carried about the opening engagement was the reassuring one, because it
    described the enemies the placer had *moved* rather than the enemy nearest
    the crew.
    """
    if spawn is None or index is None:
        return []
    out = []
    exposed = []
    if occluders is not None:
        for i, point in enumerate(plan.positions):
            xy = point[:2]
            if not opening_engagement_is_fair(xy, spawn, occluders):
                exposed.append((i, math.dist(xy, spawn)))
    if exposed:
        worst, distance = min(exposed, key=lambda pair: pair[1])
        out.append({
            "code": "LOT_ENEMY_SPAWN_IN_THE_OPEN",
            "severity": "major",
            "category": "spawn",
            "message": (
                f"{len(exposed)} of the {len(plan.positions)} enemy spawn(s) "
                f"written to the scene can see the crew spawn from inside the "
                f"range the crew's own bot opens fire at, the nearest being "
                f"Enemy_{worst} {distance:.1f} m away with no building between "
                f"the two. Laser Tag stamps time_to_first_contact on the first "
                f"shot by either side, and the crew bot only advances its route "
                f"when no enemy is visible -- so one enemy in this position is "
                f"0% route completion and a team wipe inside ten seconds, on "
                f"every run of every seed. The placer is supposed to make this "
                f"impossible: if this finding is present, the positions in the "
                f"scene did not come from the rule that was supposed to have "
                f"produced them."),
        })
    elif closest < OPENING_RANGE + OPENING_CLEARANCE:
        out.append({
            "code": "LOT_ENEMY_SPAWN_CLOSE",
            "severity": "minor",
            "category": "spawn",
            "message": (
                f"the nearest enemy to the crew spawn is Enemy_{index} at "
                f"{closest:.1f} m, inside the {OPENING_RANGE:g} m at which the "
                f"crew's bot opens fire. It is a fair opening because a "
                f"building stands between the two, and it stays fair only for "
                f"as long as that building does: a later pass that moves the "
                f"crew spawn, the enemy or the block starts the map with a "
                f"shot. Stated so the distance is in the report rather than "
                f"only in the geometry."),
        })
    return out
