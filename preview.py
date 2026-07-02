"""
preview.py  --  Blender-free building preview (no bpy, no .glb)
===============================================================
Lot composes BUILT buildings (.glb + .gameplay.json from Deli Counter's Blender
builder). That's the real pipeline. But to ITERATE THE LEVEL — placement,
routes, scale, nav, the heist flow — you don't need detailed interiors yet; you
need to walk the site. This module lets `--preview` do that with zero Blender:
it reads a Deli Counter building *spec* (the JSON new_level.py writes without
Blender) and synthesizes the gameplay data Lot needs, so each building can be
dropped in as a labeled greybox massing box with its real anchors.

This is the ONE place Lot peeks at Deli Counter's authoring spec format rather
than the public gameplay.json contract — and only for preview. It mirrors the
marker/room/objective/loot/zone shape the builder would emit; it does NOT
produce acoustic `surfaces` (those need the real geometry) and is not
authoritative. Swap in the Blender-built buildings for the real walk.
"""

_PREFIX = {
    "attacker_spawn": "ATTACKER_SPAWN", "defender_spawn": "DEFENDER_SPAWN",
    "crew_spawn": "CREW_SPAWN", "responder_spawn": "RESPONDER_SPAWN",
    "objective": "OBJECTIVE", "loot": "LOOT", "extraction": "EXTRACTION",
    "cover_low": "COVER_LOW", "cover_high": "COVER_HIGH",
    "camera_socket": "CAMERA_SOCKET", "landmark": "LANDMARK",
    "staging": "STAGING", "horde_spawn": "HORDE_SPAWN",
    "patrol_point": "PATROL_POINT", "survivor_spawn": "SURVIVOR_SPAWN",
}


# Building rarity: a mirror of the PUBLISHED Deli Counter rarity contract
# (deli_counter/docs/RARITY.md; canonical source = deli_counter/rarity.py,
# which is bpy-free but not importable from here — Lot consumes DC's outputs,
# not its code). Preview stamps the same top-level fields a Blender build
# would, so the site's per-building rarity index works before any build
# exists. If DC ever changes a hue, it changes rarity.py + RARITY.md — update
# this table to match.
_RARITY_TIERS = ["common", "uncommon", "rare", "very_rare", "legendary"]
_RARITY_HEX = {
    "common":    ("white",  "#FFFFFF"),
    "uncommon":  ("green",  "#1EFF00"),
    "rare":      ("blue",   "#0070DD"),
    "very_rare": ("purple", "#A335EE"),
    "legendary": ("gold",   "#FFD700"),
}


def _rarity_color(tier):
    """tier name -> the contract's rarity_color dict, or None if unset/unknown."""
    rec = _RARITY_HEX.get(tier)
    if rec is None:
        return None
    name, hx = rec
    h = hx.lstrip("#")
    rgb = [round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4)]
    return {"tier": tier, "rank": _RARITY_TIERS.index(tier),
            "color_name": name, "hex": hx, "rgb": rgb}


def footprint_of(spec):
    return [float(spec.get("footprint_x", 20.0)), float(spec.get("footprint_y", 20.0))]


def height_of(spec):
    """Above-ground height in metres (basements are below the pad)."""
    sh = float(spec.get("story_height", 3.6) or 3.6)
    n = int(spec.get("n_stories", 1) or 1)
    return sh * max(1, n)


def gameplay_from_spec(spec):
    """DC building spec dict -> gameplay.json-shaped dict (the subset Lot reads):
    markers (named + typed + world Blender-Z-up coords), rooms, objectives, loot,
    zones, vertical_links, footprint. No acoustic surfaces."""
    gp = {
        "level": spec.get("name", "building"),
        "mode": spec.get("mode", "heist"),
        "footprint": footprint_of(spec),
        "markers": [],
        "rooms": [],
        "objectives": spec.get("objectives", []),
        "loot": spec.get("loot", []),
        "zones": spec.get("zones", []),
        "vertical_links": spec.get("vertical_links", []),
        "openings": [],
        "surfaces": [],
        "surface_roles": {},
    }
    tier = spec.get("rarity")
    if tier is not None:
        color = _rarity_color(tier)
        if color is not None:
            gp["rarity"] = tier
            gp["rarity_color"] = color

    # exterior-wall openings, synthesized from the spec so site_enterability's
    # walled-in gate (and the per-door rarity anchors) work BEFORE any Blender
    # build — preview is exactly when you're shuffling placements and most
    # likely to wall a door in. Shape + per-kind defaults mirror the published
    # gameplay.json contract (canonical source: deli_counter spec_types.Opening
    # .resolved() + deli_counter.py _record_openings). Building-local x/y,
    # like the real build emits.
    _OPEN_DEFAULTS = {
        "door":   {"width": 1.2, "height": 2.2, "sill": 0.0},
        "window": {"width": 1.6, "height": 1.4, "sill": 1.0},
        "garage": {"width": 3.5, "height": 3.0, "sill": 0.0},
        "breach": {"width": 1.5, "height": 2.2, "sill": 0.0},
    }
    fx = spec.get("footprint_x", 20.0)
    fy = spec.get("footprint_y", 20.0)
    sh = spec.get("story_height", 3.0)
    for w in spec.get("ext_walls", []):
        wall = w.get("wall")
        story = w.get("story", 0)
        run = fx if wall in ("N", "S") else fy
        for op in w.get("openings", []):
            kind = op.get("kind", "door")
            dflt = _OPEN_DEFAULTS.get(kind, _OPEN_DEFAULTS["door"])
            width = op.get("width", dflt["width"])
            height = op.get("height", dflt["height"])
            sill = op.get("sill", dflt["sill"])
            u = op.get("pos", 0.0) * run
            if wall == "N":
                x, y = u, fy / 2
            elif wall == "S":
                x, y = u, -fy / 2
            elif wall == "E":
                x, y = fx / 2, u
            else:
                x, y = -fx / 2, u
            entry = {
                "wall": wall, "kind": kind, "story": story,
                "x": round(x, 3), "y": round(y, 3),
                "z": round(story * sh + sill + height / 2, 3),
                "width": width, "height": height, "sill": sill,
                "tag": op.get("tag"), "breach_class": op.get("breach_class"),
                "material": op.get("material"),
                "vaultable": bool(op.get("vaultable")),
                "reinforceable": bool(op.get("reinforceable")),
                "building": spec.get("name", "building"),
            }
            if tier is not None and gp.get("rarity_color") is not None:
                entry["rarity"] = tier
                entry["rarity_color"] = gp["rarity_color"]
            gp["openings"].append(entry)

    # ladder markers, synthesized from the spec's ladders array (mirrors
    # deli_counter.py _ladders): the climb-volume contract must exist in
    # preview too, or ladders only work after a Blender build.
    for li, ld in enumerate(spec.get("ladders", [])):
        f0 = ld.get("from_story", 0)
        gp["markers"].append({
            "name": f"LADDER_{li}", "type": "ladder", "id": f"ladder_{li}",
            "x": ld.get("x", 0.0), "y": ld.get("y", 0.0), "z": f0 * sh,
            "climb_height": (ld.get("to_story", f0 + 1) - f0) * sh,
            "width": ld.get("width", 0.5), "depth": ld.get("depth", 0.15),
            "facing": ld.get("facing"),
        })
    for m in spec.get("markers", []):
        t = m.get("type", "marker")
        pid = str(m.get("id", ""))
        name = f"{_PREFIX.get(t, t.upper())}_{pid}" if pid else _PREFIX.get(t, t.upper())
        wm = {"name": name, "type": t,
              "x": m.get("x", 0.0), "y": m.get("y", 0.0), "z": m.get("z", 0.0)}
        for k in ("rot_z", "room", "meta"):
            if k in m:
                wm[k] = m[k]
        gp["markers"].append(wm)
    for r in spec.get("rooms", []):
        gp["rooms"].append({"id": r.get("id"), "story": r.get("story", 0),
                            "bounds": r.get("bounds"), "role": r.get("role")})
    return gp
