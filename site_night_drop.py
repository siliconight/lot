"""
site_night_drop.py  --  a bank's night depository beside its door
==================================================================
The walker's bank list, outside (the factory's docs/reference/BANK_INTERIOR_COMPS.md, researched): "a night depository
is a slot in the wall for after-hours deposits: envelopes for people, locking zip bags for businesses, collected the
next morning". Zoo 1.138.0 draws it (`night_drop`); this hangs it.

WHERE. On the facade the bank's door sign is on (`lot.bank_fronts`: the storefront Deli Counter chose for its sign),
beside the door nearest the sign: `site_posters.OPENING_KEEP` clear of that door and of every other storey-0 opening
on the wall (a storefront's windows), `site_posters.CORNER_KEEP` from the corners. The door's two sides are tried
first, then the free span nearest the door that holds the plate. A facade with no such span gets none, and says so.

HOW. A HUNG piece, as a poster run on an alley wall is (`site_posters`): its own list, never cover, a slot all the
same so the kit that builds the street builds it, with no collision -- a 0.15 m plate on a wall is not a thing a body
stands behind. Its back `site_posters.AIR` off the wall's face, turned so its front (Zoo's local -Y) faces out
(`site_posters.facing_yaw`), its centre `CENTRE_Z` up so the chute sits about a metre off the ground.

Frame: spec/Blender Z-up plan coordinates, metres. Pure.
"""
from __future__ import annotations

SPECIES = "night_drop"
#: Zoo's genome default (1.138.0): the plate's width, its depth off the wall, its height.
DIMS = (0.6, 0.15, 0.9)
#: The plate's centre over the ground: its chute (the hood's centre, 0.08 of the height below the middle) at about a
#: metre, a car window's height for a business's bag and an arm's for an envelope.
CENTRE_Z = 1.1
CODE = "LOT_NIGHT_DROP"


def _side_of(rect, point):
    x0, y0, x1, y1 = rect
    d = {"S": abs(point[1] - y0), "N": abs(point[1] - y1), "W": abs(point[0] - x0), "E": abs(point[0] - x1)}
    return min(d, key=d.get)


def plan(site_spec, merged, banks, rects, findings=None):
    """The night drops, one a bank at most, as hung records. ``banks`` is `lot.bank_fronts`' ``[(id, (x, y) of its
    door sign, business)]``, ``rects`` {building id: world plan rect}."""
    import site_posters as SP
    bdefs = {b["id"]: b for b in site_spec.get("buildings") or [] if "id" in b}
    w, d, _h = DIMS
    out = []
    for bid, sign, _business in banks:
        rect, bdef = rects.get(bid), bdefs.get(bid)
        if rect is None or bdef is None:
            continue
        side = _side_of(rect, sign)
        _s, nx, ny, line, lo, hi = next(s for s in SP._sides(rect) if s[0] == side)
        ops = SP._openings_on(merged, bdef, rect, side)
        u_sign = sign[0] if side in ("S", "N") else sign[1]
        if not ops:
            _say(findings, f"{CODE}_NO_DOOR: {bid}'s {side} facade carries no storey-0 opening to stand one beside")
            continue
        door_u, door_hw = min(ops, key=lambda o: abs(o[0] - u_sign))
        holes = [(u - hw - SP.OPENING_KEEP, u + hw + SP.OPENING_KEEP) for u, hw in ops]
        spans = SP._free(lo + SP.CORNER_KEEP, hi - SP.CORNER_KEEP, holes)
        fits = [(s, e) for s, e in spans if e - s >= w - 1e-9]
        beside = [door_u + k * (door_hw + SP.OPENING_KEEP + w / 2.0) for k in (1, -1)]
        u = next((c for c in beside if any(s <= c - w / 2.0 + 1e-9 and c + w / 2.0 <= e + 1e-9 for s, e in fits)), None)
        if u is None and fits:
            # the free span nearest the door, the plate at its end nearest the door
            s, e = min(fits, key=lambda f: min(abs(f[0] - door_u), abs(f[1] - door_u)))
            u = s + w / 2.0 if abs(s - door_u) <= abs(e - door_u) else e - w / 2.0
        if u is None:
            _say(findings, f"{CODE}_NO_ROOM: {bid}'s {side} facade has no {w:.2f} m between its openings")
            continue
        off = d / 2.0 + SP.AIR
        at = (u + nx * off, line + ny * off) if side in ("S", "N") else (line + nx * off, u + ny * off)
        out.append({"name": f"NightDrop_{bid}", "species": SPECIES, "at": [round(at[0], 4), round(at[1], 4)],
                    "yaw": SP.facing_yaw(nx, ny), "dims": list(DIMS), "z": CENTRE_Z, "base": None,
                    "host": f"wall:{bid}:{side}", "source": "site_night_drop"})
        _say(findings, f"{CODE}: {bid} on its {side} facade at {u - door_u:+.2f} m from its door")
    return out


def _say(findings, msg):
    if findings is not None:
        findings.append(msg)
