"""The backdrop beyond the plate's edge (Lot 0.108.0, roadmap 228 step D).

The walker picked E from the edge menu (`docs/findings/edge_menu/` at the
factory root): a chain-link fence at the plate's edge (0.107.0), a sky-glow
over it (Lux 0.73.0) and, behind the fence, rows of rowhomes with lit windows
and a water tower (Zoo 1.95.0's `backdrop_rowhome` and `water_tower`). And
"multiple different versions depending on the level": the surroundings are a
RECIPE the site spec names (`surroundings`, Level Factory's to write from the
brief) or, unnamed, `borough`.

WHAT A RECIPE LAYS, in the mockup's figures. `borough`: three bands of
rowhomes beyond each edge, 4 to 14, 38 to 49 and 80 to 92 m out, the houses
5 to 7 m wide and 8 to 11 m tall with the odd cross street and gap, and one
water tower 90 m past the north edge. `none`: nothing. `yards`, `parkland`
and `roadside` are named here so a brief can ask for them, and lay the
borough with a finding until their kits exist (a backdrop tree, containers).

A FEW MODULES, MANY INSTANCES. A band is composed as one MultiMesh a module
a side (Level Factory, step E), so the draws scale with the modules, not the
houses: a level draws MODULES_PER_LEVEL (width, height) pairs from the
fifteen and every house is one of them. Zoo lights each module's windows by
its stem, so the pairs are the patterns too.

BACKDROP IS NOT COVER. The pieces go into their own list, `backdrop`, never
`cover`: nothing is a sightline blocker, nothing has collision, nothing is on
the navmesh, nothing stands inside the plate. `lot.write_site_slots` gives
each a slot so the same kit build makes the modules.
"""
from __future__ import annotations

import random

SPECIES = "backdrop_rowhome"
TOWER_SPECIES = "water_tower"
RECIPES = ("borough", "none", "yards", "parkland", "roadside")
#: the recipes whose kits exist; the others lay this one and say so
BUILT = ("borough", "none")
#: the bands beyond an edge, metres out (near, far); a house's depth is the band's
BANDS = ((4.0, 14.0), (38.0, 49.0), (80.0, 92.0))
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


def plan(site_spec, ground, seed=0, findings=None) -> list:
    """The backdrop's pieces beyond ``ground`` (the plate's rect), by the
    spec's recipe: ``[{name, species, at, yaw, dims, side, band, source}]``,
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
    kinds = modules(rng)
    out = []
    x0, y0, x1, y1 = (float(v) for v in ground)
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
                px, py = _place(side, t + w / 2.0, (near + far) / 2.0, (x0, y0, x1, y1))
                out.append({"name": f"Backdrop_{side}_{b}_{k}", "species": SPECIES,
                            "at": [round(px, 3), round(py, 3)], "yaw": FACING[side],
                            "dims": [w, depth, h], "side": side, "band": b,
                            "source": "site_backdrop"})
                k += 1
                t += w + (rng.uniform(*GAP) if rng.random() < GAP_SHARE else 0.0)
    tx, ty = _place("N", x0 + (x1 - x0) * 0.25, TOWER_OUT, (x0, y0, x1, y1))
    out.append({"name": "Backdrop_Tower", "species": TOWER_SPECIES,
                "at": [round(tx, 3), round(ty, 3)], "yaw": 0.0, "dims": list(TOWER),
                "side": "N", "band": -1, "source": "site_backdrop"})
    return out


def summary(pieces) -> dict:
    """What a plan laid: houses, modules, the tower, by side."""
    houses = [p for p in pieces if p["species"] == SPECIES]
    return {"houses": len(houses),
            "modules": len({(p["dims"][0], p["dims"][2]) for p in houses}),
            "towers": sum(1 for p in pieces if p["species"] == TOWER_SPECIES),
            "by_side": {s: sum(1 for p in houses if p["side"] == s) for s in ("N", "S", "E", "W")}}
