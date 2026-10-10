"""The backdrop beyond the plate's edge (Lot 0.108.0, roadmap 228 step D; the
other recipes 0.109.0).

The walker picked E from the edge menu (`docs/findings/edge_menu/` at the
factory root): a chain-link fence at the plate's edge (0.107.0), a sky-glow
over it (Lux 0.73.0) and, behind the fence, rows of rowhomes with lit windows
and a water tower (Zoo 1.95.0's `backdrop_rowhome` and `water_tower`). And
"multiple different versions depending on the level": the surroundings are a
RECIPE the site spec names (`surroundings`, Level Factory writes it from the
brief or decides it from the archetype) or, unnamed, `borough`.

THE RECIPES, in the mockup's figures and Zoo 1.96.0's two more species:
  * `borough`: three bands of rowhomes beyond each edge, 4 to 14, 38 to 49
    and 80 to 92 m out, 5 to 7 m wide and 8 to 11 m tall with the odd cross
    street and gap, and one water tower 90 m past the north edge.
  * `yards`: stacked cargo containers along the near band, warehouses with
    roof monitors in the two bands behind, and the water tower.
  * `parkland`: a belt of trees 2.5 to 38 m out, and a sparser far belt.
  * `roadside`: a thin belt of trees, a few far warehouses, no tower.
  * `none`: nothing.

A FEW MODULES, MANY INSTANCES. A band is composed as one MultiMesh a module
a side (Level Factory, step E), so the draws scale with the modules, not the
pieces: a level draws a few (width, height) pairs a species and every piece
is one of them. Zoo lights each module's windows by its stem, so the pairs
are the patterns too.

BACKDROP IS NOT COVER. The pieces go into their own list, `backdrop`, never
`cover`: nothing is a sightline blocker, nothing has collision, nothing is on
the navmesh, nothing stands inside the plate. `lot.write_site_slots` gives
each a slot so the same kit build makes the modules. A piece may carry `z`,
its foot's height above the plate, for a container stacked on another.
"""
from __future__ import annotations

import random

SPECIES = "backdrop_rowhome"
TOWER_SPECIES = "water_tower"
TREE_SPECIES = "backdrop_tree"
WAREHOUSE_SPECIES = "backdrop_warehouse"
CONTAINER_SPECIES = "cargo_container"
RECIPES = ("borough", "none", "yards", "parkland", "roadside")
#: the recipes whose kits exist; the others lay the borough and say so
BUILT = ("borough", "none", "yards", "parkland", "roadside")
#: the borough's bands beyond an edge, metres out (near, far); a house's depth is the band's,
#: THE SAME IN EVERY BAND (0.109.0): a module is a species at its dims, depth included, so
#: three depths were three times the modules a level was said to draw from (18, not 6)
BANDS = ((4.0, 16.0), (38.0, 50.0), (80.0, 92.0))
WIDTHS = (5.0, 5.5, 6.0, 6.5, 7.0)
HEIGHTS = (8.0, 9.5, 11.0)
MODULES_PER_LEVEL = 6
#: a cross street now and then, and a gap between some houses
CROSS_STREET_SHARE = 0.07
CROSS_STREET = (8.0, 14.0)
GAP_SHARE = 0.2
GAP = (1.0, 3.0)
#: the long sides' bands run this far past the plate's corners, so the corners fill
CORNER_REACH = 20.0
TOWER = (14.0, 14.0, 40.0)
TOWER_OUT = 90.0
#: the yards: a container (Zoo's `cargo_container` at its default), stacked two high in runs
#: along the near band; warehouses, three sizes, in the bands behind
CONTAINER = (2.44, 6.06, 2.59)
CONTAINER_BAND = (3.0, 10.0)
CONTAINER_RUN = (3, 6)
CONTAINER_GAP = (2.0, 9.0)
CONTAINER_STACK_SHARE = 0.6
WAREHOUSE_BANDS = ((22.0, 40.0), (66.0, 92.0))
WAREHOUSES = ((24.0, 16.0, 7.0), (32.0, 16.0, 8.0), (40.0, 20.0, 9.0))
WAREHOUSE_GAP = (6.0, 14.0)
#: the parkland: a belt of trees, three sizes, and a sparser far belt
TREES = ((5.0, 5.0, 7.0), (7.0, 7.0, 10.0), (9.0, 9.0, 13.0))
TREE_BELT = (2.5, 38.0)
TREE_STEP = (1.2, 3.2)
FAR_TREE_BELT = (60.0, 90.0)
FAR_TREE_STEP = (4.0, 9.0)
#: the roadside: a thin belt of trees and a few far warehouses
ROADSIDE_BELT = (2.5, 20.0)
ROADSIDE_STEP = (2.0, 5.0)
ROADSIDE_WAREHOUSE_GAP = (20.0, 45.0)
#: the yaw that turns a module's front (-Y) toward the plate from each side
FACING = {"N": 0.0, "S": 180.0, "E": 270.0, "W": 90.0}


def _say(findings, msg):
    if findings is not None:
        findings.append(msg)


def surroundings(site_spec) -> str:
    """The recipe the spec names, lower-cased; `borough` unnamed."""
    return str(site_spec.get("surroundings") or "borough").strip().lower()


def modules(rng) -> list:
    """The (width, height) pairs this level draws its houses from."""
    pairs = [(w, h) for w in WIDTHS for h in HEIGHTS]
    rng.shuffle(pairs)
    return sorted(pairs[:MODULES_PER_LEVEL])


def _place(side, along, out, ground):
    """Plan (x, y) of a point `along` a side and `out` metres beyond it."""
    x0, y0, x1, y1 = ground
    if side == "N":
        return along, y1 + out
    if side == "S":
        return along, y0 - out
    if side == "E":
        return x1 + out, along
    return x0 - out, along


def _span(side, ground):
    x0, y0, x1, y1 = ground
    if side in ("N", "S"):
        return x0 - CORNER_REACH, x1 + CORNER_REACH
    return y0 + 2.0, y1 - 2.0


def _piece(name, species, side, band, at, yaw, dims, z=0.0):
    p = {"name": name, "species": species, "at": [round(at[0], 3), round(at[1], 3)],
         "yaw": yaw, "dims": [float(v) for v in dims], "side": side, "band": band,
         "source": "site_backdrop"}
    if z:
        p["z"] = round(z, 3)
    return p


def _tower(ground):
    x0, y0, x1, y1 = ground
    tx, ty = _place("N", x0 + (x1 - x0) * 0.25, TOWER_OUT, ground)
    return _piece("Backdrop_Tower", TOWER_SPECIES, "N", -1, (tx, ty), 0.0, TOWER)


def _borough(ground, rng) -> list:
    kinds = modules(rng)
    out = []
    for side in ("S", "N", "W", "E"):
        s0, s1 = _span(side, ground)
        for b, (near, far) in enumerate(BANDS):
            depth = round(far - near, 2)
            t = s0
            k = 0
            while t < s1:
                if rng.random() < CROSS_STREET_SHARE:
                    t += rng.uniform(*CROSS_STREET)
                    continue
                w, h = kinds[rng.randrange(len(kinds))]
                if t + w > s1:
                    break
                at = _place(side, t + w / 2.0, (near + far) / 2.0, ground)
                out.append(_piece(f"Backdrop_{side}_{b}_{k}", SPECIES, side, b, at,
                                  FACING[side], (w, depth, h)))
                k += 1
                t += w + (rng.uniform(*GAP) if rng.random() < GAP_SHARE else 0.0)
    out.append(_tower(ground))
    return out


def _facing_along(side, dims):
    """A module whose width runs along a side: for the long sides the width is
    along x and the module faces the plate at its yaw; a container's length is
    its depth, so it turns a quarter to lie along the edge."""
    return FACING[side]


def _yards(ground, rng) -> list:
    out = []
    cw, cd, ch = CONTAINER
    for side in ("S", "N", "W", "E"):
        s0, s1 = _span(side, ground)
        # the near band: runs of containers lying along the edge, some stacked
        near, far = CONTAINER_BAND
        t = s0
        k = 0
        while t < s1:
            n = rng.randint(*CONTAINER_RUN)
            for _ in range(n):
                if t + cd > s1:
                    break
                at = _place(side, t + cd / 2.0, (near + far) / 2.0, ground)
                # the container's length lies along the edge: its local depth
                # along the side, a quarter turn off the facing yaw
                yaw = (FACING[side] + 90.0) % 360.0
                out.append(_piece(f"Backdrop_{side}_0_{k}", CONTAINER_SPECIES, side, 0, at, yaw,
                                  (cw, cd, ch)))
                k += 1
                if rng.random() < CONTAINER_STACK_SHARE:
                    out.append(_piece(f"Backdrop_{side}_0_{k}", CONTAINER_SPECIES, side, 0, at,
                                      yaw, (cw, cd, ch), z=ch))
                    k += 1
                t += cd + 0.3
            t += rng.uniform(*CONTAINER_GAP)
        # the bands behind: warehouses facing the plate
        for b, (near, far) in enumerate(WAREHOUSE_BANDS, start=1):
            t = s0 + rng.uniform(0.0, 10.0)
            k = 0
            while t < s1:
                w, d, h = WAREHOUSES[rng.randrange(len(WAREHOUSES))]
                if t + w > s1:
                    break
                at = _place(side, t + w / 2.0, near + d / 2.0, ground)
                out.append(_piece(f"Backdrop_{side}_{b}_{k}", WAREHOUSE_SPECIES, side, b, at,
                                  FACING[side], (w, d, h)))
                k += 1
                t += w + rng.uniform(*WAREHOUSE_GAP)
    out.append(_tower(ground))
    return out


def _trees(ground, rng, side, belt, step, band, start=0) -> list:
    out = []
    s0, s1 = _span(side, ground)
    t = s0
    k = start
    while t < s1:
        w, d, h = TREES[rng.randrange(len(TREES))]
        # a crown never overhangs the plate: its foot stands at least its
        # radius beyond the edge, and the fence, whatever the belt's near edge
        near = max(belt[0], w / 2.0 + 0.25)
        at = _place(side, t, rng.uniform(near, max(near, belt[1])), ground)
        out.append(_piece(f"Backdrop_{side}_{band}_{k}", TREE_SPECIES, side, band, at,
                          rng.choice((0.0, 90.0, 180.0, 270.0)), (w, d, h)))
        k += 1
        t += rng.uniform(*step)
    return out


def _parkland(ground, rng) -> list:
    out = []
    for side in ("S", "N", "W", "E"):
        out += _trees(ground, rng, side, TREE_BELT, TREE_STEP, 0)
        out += _trees(ground, rng, side, FAR_TREE_BELT, FAR_TREE_STEP, 1)
    return out


def _roadside(ground, rng) -> list:
    out = []
    for side in ("S", "N", "W", "E"):
        out += _trees(ground, rng, side, ROADSIDE_BELT, ROADSIDE_STEP, 0)
        s0, s1 = _span(side, ground)
        near, far = WAREHOUSE_BANDS[1]
        t = s0 + rng.uniform(0.0, 20.0)
        k = 0
        while t < s1:
            w, d, h = WAREHOUSES[rng.randrange(len(WAREHOUSES))]
            if t + w > s1:
                break
            at = _place(side, t + w / 2.0, near + d / 2.0, ground)
            out.append(_piece(f"Backdrop_{side}_1_{k}", WAREHOUSE_SPECIES, side, 1, at,
                              FACING[side], (w, d, h)))
            k += 1
            t += w + rng.uniform(*ROADSIDE_WAREHOUSE_GAP)
    return out


_LAY = {"borough": _borough, "yards": _yards, "parkland": _parkland, "roadside": _roadside}


def plan(site_spec, ground, seed=0, findings=None) -> list:
    """The backdrop's pieces beyond ``ground`` (the plate's rect), by the
    spec's recipe: ``[{name, species, at, yaw, dims, side, band, source[, z]}]``,
    deterministic for ``seed``. None for the ground, or `none` for the
    recipe, lays nothing."""
    recipe = surroundings(site_spec)
    if recipe not in RECIPES:
        _say(findings, f"LOT_BACKDROP_RECIPE_UNKNOWN: surroundings {recipe!r} is not one of "
                       f"{', '.join(RECIPES)}; the borough stands in")
        recipe = "borough"
    elif recipe not in BUILT:
        _say(findings, f"LOT_BACKDROP_RECIPE_PENDING: surroundings {recipe!r} has no kit yet; "
                       f"the borough stands in")
        recipe = "borough"
    if recipe == "none" or not ground:
        return []
    rng = random.Random(f"backdrop|{seed}|{site_spec.get('name', '')}")
    rect = tuple(float(v) for v in ground)
    return _LAY[recipe](rect, rng)


def summary(pieces) -> dict:
    """What a plan laid: pieces by species, modules, the tower, by side."""
    by_species = {}
    for p in pieces:
        by_species[p["species"]] = by_species.get(p["species"], 0) + 1
    houses = [p for p in pieces if p["species"] == SPECIES]
    return {"houses": len(houses),
            "by_species": by_species,
            "modules": len({(p["species"], tuple(p["dims"])) for p in pieces}),
            "towers": sum(1 for p in pieces if p["species"] == TOWER_SPECIES),
            "by_side": {s: sum(1 for p in pieces if p["side"] == s and p["species"] != TOWER_SPECIES)
                        for s in ("N", "S", "E", "W")}}
