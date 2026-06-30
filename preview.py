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
