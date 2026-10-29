"""
site_frontage.py  --  what stands outside a shop's door
=======================================================
The walker, 2026-10-29, of the game's vertical slice: "Things still look simple, and computer made... I want to get
to a place where these levels looks handcrafted, bespoke, varied", and of the target, "detail of set dressing". The
street had furniture spaced by rule -- a lamp every 25 m, a tree between, a hydrant at each crossing -- and nothing
that said what any building on it was. A 1990s shop that sells to people walking in keeps its life outside its own
door: a soda machine against the wall beside it, a stack of the milk crates the deliveries came in, a news box. That
group is the cause the set dressing was missing (the factory's docs/findings/slice_look/).

ONE GROUP A SHOP, BESIDE ITS WAY IN, ON A STREET FACE. So:

  * a building is a SHOP when its ARCHETYPE -- the library's name for it; its `id` is the site's `b0`, `b1` -- carries
    one of `SHOP_WORDS`; a bank is not one (an orderly front is what a bank keeps), nor anything else, and gets
    nothing. RETRACTED, KEPT: the first draft read the id, every slice building was `b<n>`, and slice 6 placed nothing
    while its unit tests, which named their buildings by archetype, passed;
  * the door is a ground-storey WAY IN on a STREET FACE -- a wall a road's band lies in front of within
    `site_dumpsters.FRONT_REACH` -- on the building's `front` wall when Lot has decided one, else the first such the
    building's id picks;
  * the group stands against that wall to ONE side of the door (the id picks which), the soda machine nearest, then
    the crates, then the news box, `PIECE_GAP` apart, each stepping out along the wall by `STEP` from `DOOR_CLEAR`
    until it is clear: clear of the door's approach point by `site_dumpsters.APPROACH_CLEAR`, off every path and
    walk, off every road band, clear of the other buildings, of what already stands and of the mission's markers,
    and on the plate;
  * its back is `WALL_GAP` off the wall and its front faces away from the building.

A shop where a piece finds no clear station gets the pieces that did; one where none did is said
(`LOT_FRONTAGE_NO_ROOM`). A machine in a doorway is worse than none. The pieces are cover-shaped records like the
dumpster's, with collision, so the honesty rule holds by construction.

Site space: plan (x, y), metres. A Zoo prop's front is its -Y, which at yaw 0 points to plan -y; the yaw that turns it
to face a wall's outward normal (nx, ny) is atan2(nx, -ny), as `site_dumpsters` derives it.
"""
from __future__ import annotations

import math

import site_dumpsters as SD

#: A building is a shop when its id carries one of these words: one people walk into to buy something small.
SHOP_WORDS = ("gas", "convenience", "stop_n_go", "corner", "deli", "pizza", "primos", "card", "video", "pharmacy",
              "store", "shop", "market", "laundromat")
#: Never a shop, whatever else its id says (a "bank_shop" is a bank).
NOT_SHOP_WORDS = ("bank", "credit", "empty", "rowhome", "twin", "mansion")
#: The group, nearest the door first: (species, (w, d, h)) at each genome's default.
GROUP = (("vending_machine", (0.85, 0.75, 1.83)),
         ("milk_crate_stack", (0.35, 0.35, 1.0)),
         ("newspaper_box", (0.42, 0.45, 1.15)))
#: From the door's edge to the nearest piece's near side before any stepping, metres: a door swings a metre and a
#: body is 0.7 m wide (`agent_contract.json`). Chosen, not derived.
DOOR_CLEAR = 1.2
WALL_GAP = 0.08
PIECE_GAP = 0.25
STEP = 0.5
MAX_STEPS = 12


def is_shop(bid: str) -> bool:
    b = str(bid or "").lower()
    if any(w in b for w in NOT_SHOP_WORDS):
        return False
    return any(w in b for w in SHOP_WORDS)


def _street_faces(rect, roads_list):
    out = set()
    for side, n in SD._WALLS:
        for road in roads_list:
            gap = SD._road_side(rect, n, road)
            if gap is not None and gap <= SD.FRONT_REACH:
                out.add(side)
    return out


def plan_frontage(site_spec, merged, roads_list, markers=(), standing=(), keep_out=(), ground=None, findings=None):
    """A shop's group beside its way in, as cover pieces. Arguments as `site_dumpsters.plan_dumpsters`'s."""
    import site_enterability as SE
    import site_extent
    import site_furniture
    openings = SD._openings(site_spec, merged)
    approaches = [ap for rows in SE._approach_points(site_spec, merged).values() for (_e, ap, _w) in rows]
    rects = {}
    for b in site_spec.get("buildings", []) or []:
        r = site_extent.rotated_footprint(b)
        if r is not None:
            rects[b["id"]] = r
    placed, taken = [], list(standing)
    for b in site_spec.get("buildings", []) or []:
        bid = b["id"]
        if not is_shop(b.get("archetype") or bid):
            continue
        rect = rects.get(bid)
        if rect is None or float(b.get("rot", 0) or 0) % 90 != 0:
            SD._say(findings, f"LOT_FRONTAGE_NO_ROOM: {bid} has no footprint this can read, or stands off the "
                              "right angles; nothing outside its door")
            continue
        faces = _street_faces(rect, roads_list)
        doors = []
        for (ox, oy), (onx, ony), hw, entry in openings.get(bid, []):
            if not entry:
                continue
            for side, n in SD._WALLS:
                if side in faces and onx * n[0] + ony * n[1] > 0.9:
                    doors.append((side, n, (ox, oy), hw))
        if not doors:
            SD._say(findings, f"LOT_FRONTAGE_NO_ROOM: {bid} has no way in on a street face")
            continue
        front = (b.get("front") or {}).get("wall")
        doors.sort(key=lambda d: (d[0] != front, SD._h("door", bid, d[0], round(d[2][0], 2), round(d[2][1], 2))))
        side, n, (ox, oy), hw = doors[0]
        (sx0, sy0), (ux, uy), length = SD._wall_line(rect, side)
        u_door = (ox - sx0) * ux + (oy - sy0) * uy
        sign = 1.0 if SD._h("hand", bid) % 2 == 0 else -1.0
        cursor = hw + DOOR_CLEAR                      # from the door's centre, along the wall, to the next near side
        got = []
        for species, (w, d, h) in GROUP:
            piece = None
            for k in range(MAX_STEPS):
                near = cursor + k * STEP
                u = u_door + sign * (near + w / 2.0)
                if not (w / 2.0 <= u <= length - w / 2.0):
                    break
                cx = sx0 + ux * u + n[0] * (WALL_GAP + d / 2.0)
                cy = sy0 + uy * u + n[1] * (WALL_GAP + d / 2.0)
                px, py = (w, d) if side in ("S", "N") else (d, w)
                r = (cx - px / 2.0, cy - py / 2.0, cx + px / 2.0, cy + py / 2.0)
                if ground is not None and not (ground[0] + SD.EDGE <= r[0] and r[2] <= ground[2] - SD.EDGE
                                               and ground[1] + SD.EDGE <= r[1] and r[3] <= ground[3] - SD.EDGE):
                    continue
                if any(SD._overlap(r, SD._grow(o, SD.GAP)) for oid, o in rects.items() if oid != bid):
                    continue
                if any(SD._overlap(r, k_) for k_ in keep_out):
                    continue
                if any(SD._overlap(r, SD._grow(t, SD.GAP)) for t in taken):
                    continue
                if any(SD._in_band(r, road) for road in roads_list):
                    continue
                grown = SD._grow(r, SD.APPROACH_CLEAR)
                if any(grown[0] <= ax <= grown[2] and grown[1] <= ay <= grown[3] for ax, ay in approaches):
                    continue
                cand = {"name": f"Frontage_{bid}_{len(got)}", "species": species,
                        "at": [round(cx, 3), round(cy, 3)],
                        "yaw": round(math.degrees(math.atan2(n[0], -n[1])) % 360.0, 3),
                        "dims": [w, d, h], "size": [px, h, py], "base": "plate",
                        "building": bid, "wall": side,
                        "source": "site_frontage", "breaks": f"outside {bid}'s door"}
                if not site_furniture._clear_of_markers(cand, markers):
                    continue
                piece = cand
                cursor = near + w + PIECE_GAP
                break
            if piece is None:
                continue
            got.append(piece)
            taken.append(SD._grow(r, 0.0))
        if not got:
            SD._say(findings, f"LOT_FRONTAGE_NO_ROOM: no clear station beside {bid}'s door")
            continue
        placed.extend(got)
    return placed
