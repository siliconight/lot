"""
lot.py  --  site assembler for Deli Counter buildings (Phase 1)
==============================================================
Deli Counter makes one monolithic, deterministic building per spec. A
PAYDAY-scale heist is several buildings with space between them. Lot is the
sibling tool that COMPOSES already-built Deli Counter buildings into a site:
it places each building on a shared ground, merges their gameplay data into one
site-level file, and emits a Godot scene that instances them.

It never re-generates or edits the buildings. Each building stays an untouched,
independently-rebuildable .glb (the disposable-.glb / iterate-the-spec loop keeps
working per building). Lot is a composition layer ABOVE the buildings, consuming
their public contract (.glb + .gameplay.json) — never their internals.

PHASE 1 (this file): deterministic placement + ground slab manifest + merged,
world-offset, namespaced gameplay.json + a generated Godot .tscn that instances
each building at its placement. No geometry merging — buildings stay separate
files, composed at load time.

PHASE 2 (later): box-vocabulary outdoor — paths, courtyards, perimeter walls,
cover — generated as the same axis-aligned blockout geometry Deli Counter uses.

A site spec (JSON):
{
  "name": "big_oil",
  "ground": {"size_x": 120, "size_y": 80},
  "buildings": [
    {"id": "bank", "glb": "bank.glb", "gameplay": "bank.gameplay.json",
     "at": [0, 0], "rot": 0},
    {"id": "warehouse", "glb": "warehouse.glb", "gameplay": "warehouse.gameplay.json",
     "at": [45, 10], "rot": 90}
  ],
  "site_markers": [
     {"type": "extraction", "at": [60, -30]}
  ]
}
"""

import json
import math
import os


#: What a MISSING contract file falls back to. These must track the ratified
#: values in deli_counter/agent_contract.json -- they had drifted, still saying
#: agent_max_climb_m 0.5 and cell_size_m 0.15 after both were changed, so a
#: build with no contract present would have silently used the numbers that let
#: the bake promise a 0.49 m climb and then severed every stair over 45 deg.
_AGENT_DEFAULTS = {"nav_bake": {"agent_radius_m": 0.4, "agent_height_m": 1.8,
                                "agent_max_climb_m": 0.15,
                                "agent_max_slope_deg": 55.0,
                                "cell_size_m": 0.10, "cell_height_m": 0.15},
                   "characters": {"player": {"radius_m": 0.35,
                                             "height_m": 1.8,
                                             "eye_height_m": 1.6,
                                             "crouch_height_m": 1.2,
                                             "max_step_up_m": 0.5,
                                             "walk_speed_mps": 4.0},
                                  "npc_standard": {"radius_m": 0.35,
                                                   "height_m": 1.8}},
                   "clearances": {"min_door_width_m": 1.25,
                                  "min_corridor_width_m": 1.1,
                                  "min_headroom_m": 2.0,
                                  "unassisted_step_max_m": 0.1025},
                   "qa": {"arrive_dist_m": 1.5, "stuck_seconds": 4.0,
                          "snap_max_m": 2.0}}
_agent_cache = None


def _agent():
    """The shared agent contract (deli_counter/agent_contract.json -- ONE
    source of truth for character metrics and derived clearances; the
    body-metrics sibling of COORDINATE_CONTRACT.md). Search order:
    $DC_AGENT_CONTRACT, then the deli_counter sibling repo. Fallbacks equal
    the ratified values, so a missing file degrades gracefully."""
    global _agent_cache
    if _agent_cache is not None:
        return _agent_cache
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    if os.environ.get("DC_AGENT_CONTRACT"):
        candidates.append(os.environ["DC_AGENT_CONTRACT"])
    candidates.append(os.path.join(os.path.dirname(here), "deli_counter",
                                   "agent_contract.json"))
    merged = {k: dict(v) for k, v in _AGENT_DEFAULTS.items()}
    for c in candidates:
        try:
            with open(c, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge what the FILE has, not what the defaults happen to
            # list. This iterated over `merged` -- the defaults' keys -- so any
            # contract section absent from _AGENT_DEFAULTS was read off disk and
            # discarded. `characters` and `clearances` were both dropped, which
            # is why the step gate died on KeyError: 'characters' and why the
            # walk-scene player had to be a literal. The contract is
            # authoritative; defaults only survive a missing file.
            for sec, val in data.items():
                if isinstance(val, dict) and isinstance(merged.get(sec), dict):
                    merged[sec].update(val)
                else:
                    merged[sec] = val
            break
        except (OSError, json.JSONDecodeError):
            continue
    _agent_cache = merged
    return merged


LOT_VERSION = "0.17.2"


# ---------------------------------------------------------------------------
# placement math
# ---------------------------------------------------------------------------
def _rotate_xy(x, y, deg):
    """Rotate a point about the origin in the XY (ground) plane, deterministic."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (x * c - y * s, x * s + y * c)


def _place_point(local_x, local_y, local_z, placement):
    """Transform a building-local marker position into world space: rotate about
    the building origin (Z-up yaw), then translate to the building's site
    position. Z (height) is unchanged — buildings sit on the shared ground."""
    rx, ry = _rotate_xy(local_x, local_y, placement["rot"])
    return [rx + placement["at"][0], ry + placement["at"][1], local_z]


# ---------------------------------------------------------------------------
# building geometry source: .tscn (preferred) or .glb
# ---------------------------------------------------------------------------
def _building_source(b):
    """Resolve a building record's geometry file. A building may reference a
    Godot scene (`scene`: a .tscn that instances shared modules) or a baked
    `glb` -- `scene` wins when both are present. Deli Counter's primary output
    is the .tscn; the baked .glb is the self-contained special case. Both are
    instanced the same way (a PackedScene ExtResource), so this is the only
    place the distinction lives. Returns the file path string."""
    scene = b.get("scene")
    glb = b.get("glb")
    if scene and glb:
        print(f"[lot] building '{b.get('id', '?')}' has both scene and glb; "
              f"using scene ({scene}), ignoring glb")
    src = scene or glb
    if not src:
        raise ValueError(
            f"building '{b.get('id', '?')}' has no geometry: set 'scene' "
            f"(a .tscn) or 'glb' (a baked .glb)")
    if not (src.endswith(".tscn") or src.endswith(".glb")):
        print(f"[lot] building '{b.get('id', '?')}' geometry '{src}' is not a "
              f".tscn or .glb -- instancing it anyway")
    return src


# ---------------------------------------------------------------------------
# gameplay.json merge  (the high-value, fiddly-by-hand core of Phase 1)
# ---------------------------------------------------------------------------
def merge_gameplay(site_spec, base_dir):
    """Merge every building's gameplay.json into one site-level file, with all
    positions offset to world space and all ids namespaced by building id so
    nothing collides. Deterministic: same inputs -> identical output."""
    site = {
        "site": site_spec["name"],
        "ground": site_spec.get("ground", {}),
        "buildings": [],
        "markers": [],
        "rooms": [],
        "objectives": [],
        "loot": [],
        "zones": [],
        "vertical_links": [],
        "openings": [],
        "surfaces": [],
        "surface_roles": {},
        "site_markers": site_spec.get("site_markers", []),
    }

    for b in site_spec["buildings"]:
        bid = b["id"]
        placement = {"at": b["at"], "rot": b.get("rot", 0)}
        record = {
            "id": bid, "source": _building_source(b),
            "at": b["at"], "rot": b.get("rot", 0),
        }
        if "glb" in b:
            record["glb"] = b["glb"]      # preserved for back-compat readers
        if "scene" in b:
            record["scene"] = b["scene"]
        gp_ref = b.get("gameplay")
        gp_path = os.path.join(base_dir, gp_ref) if gp_ref else None
        if not gp_path or not os.path.exists(gp_path):
            # a building with no gameplay ref/file still places fine; skip its data
            site["buildings"].append(record)
            continue
        with open(gp_path, encoding="utf-8") as f:
            gp = json.load(f)

        # carry the building's rarity onto its site record so the compound has a
        # clean per-building rarity index (every building has its own hidden
        # rarity -- the door reveal reads it). Breachable openings already carry
        # the same colour and pass through the openings merge below untouched.
        if gp.get("rarity") is not None:
            record["rarity"] = gp.get("rarity")
            record["rarity_color"] = gp.get("rarity_color")
        if gp.get("footprint") is not None:
            record["footprint"] = gp.get("footprint")
            # annotate the SPEC's building entry too: the scene builder cuts
            # the ground slab around footprints (a solid ground box through a
            # building seals its basement stairwell -- Phase 1 site walktests
            # proved basements bake as disjoint islands otherwise)
            b["_footprint"] = gp.get("footprint")
        site["buildings"].append(record)

        def ns(name):
            return f"{bid}/{name}"

        # markers: offset position to world, namespace name, tag origin building
        for m in gp.get("markers", []):
            wm = dict(m)
            wm["name"] = ns(m.get("name", m.get("type", "marker")))
            wm["building"] = bid
            x, y, z = m.get("x", 0.0), m.get("y", 0.0), m.get("z", 0.0)
            wx, wy, wz = _place_point(x, y, z, placement)
            wm["x"], wm["y"], wm["z"] = wx, wy, wz
            if "rot_z" in m:
                wm["rot_z"] = (m["rot_z"] + placement["rot"]) % 360
            site["markers"].append(wm)

        # rooms: namespace id, offset bounds corners to world
        for r in gp.get("rooms", []):
            wr = dict(r)
            wr["id"] = ns(r["id"])
            wr["building"] = bid
            if "bounds" in r and len(r["bounds"]) == 4:
                x0, y0, x1, y1 = r["bounds"]
                # rotate all four corners, take the world AABB (axis-aligned)
                corners = [_rotate_xy(cx, cy, placement["rot"])
                           for cx, cy in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
                xs = [c[0] + placement["at"][0] for c in corners]
                ys = [c[1] + placement["at"][1] for c in corners]
                wr["bounds"] = [min(xs), min(ys), max(xs), max(ys)]
            site["rooms"].append(wr)

        # objectives / loot / zones: namespace any id/room refs, carry through
        for key in ("objectives", "loot", "zones"):
            for item in gp.get(key, []):
                wi = dict(item)
                wi["building"] = bid
                for ref in ("id", "room", "name"):
                    if ref in wi and isinstance(wi[ref], str):
                        wi[ref] = ns(wi[ref])
                site[key].append(wi)

        # vertical_links / openings: carry through, tag building (positions are
        # descriptive; markers already carry the authoritative world coords)
        for key in ("vertical_links", "openings"):
            for item in gp.get(key, []):
                wi = dict(item)
                wi["building"] = bid
                site[key].append(wi)

        # surfaces (acoustic) + surface_roles: namespace node names so the
        # site-wide maps stay unambiguous across buildings
        for s in gp.get("surfaces", []):
            ws = dict(s)
            if "node" in ws:
                ws["node"] = ns(ws["node"])
            site["surfaces"].append(ws)
        for node, role in gp.get("surface_roles", {}).items():
            site["surface_roles"][ns(node)] = role

    return site


# ---------------------------------------------------------------------------
# lights.json merge  (compose each building's baked light anchors + exterior)
# ---------------------------------------------------------------------------
STREETLIGHT_H = 6.0        # pole-top height (Blender Z-up metres)


def _lights_ref_for(b):
    """The building's <name>.lights.json: an explicit 'lights' field, else
    derived from its gameplay/glb reference."""
    if b.get("lights"):
        return b["lights"]
    ref = b.get("gameplay") or b.get("glb") or ""
    if ref.endswith(".gameplay.json"):
        return ref[:-len(".gameplay.json")] + ".lights.json"
    if ref.endswith(".glb"):
        return ref[:-len(".glb")] + ".lights.json"
    return None


def _streetlight_anchors(site_spec):
    """Exterior lights Lot owns (Deli Counter can't see the outdoors): a
    streetlight row down each path, and a ring around the ground perimeter."""
    anchors = []
    bmap = {b["id"]: b for b in site_spec["buildings"]}

    for i, p in enumerate(site_spec.get("paths", [])):
        a = bmap[p["from"]]["at"] if "from" in p else p["a"]
        b2 = bmap[p["to"]]["at"] if "to" in p else p["b"]
        (ax, ay), (bx, by) = a, b2
        length = math.hypot(bx - ax, by - ay)
        if length < 1e-3:
            continue
        count = max(2, min(8, round(length / 10.0)))
        anchors.append({
            "id": "site/path_%d_lights" % i, "type": "streetlight",
            "source": "derived", "building": None,
            "pos": [round((ax + bx) / 2, 3), round((ay + by) / 2, 3), STREETLIGHT_H],
            "rot_y": round(math.degrees(math.atan2(by - ay, bx - ax)) % 360, 3),
            "row": {"count": count, "spacing": round(length / count, 3)},
            "reacts_to_alarm": False,
        })

    import site_extent
    rect = site_extent.resolve(site_spec).rect
    if rect:
        x0, y0, x1, y1 = rect
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        span_x, span_y = x1 - x0, y1 - y0
        inset = 2.0
        # (name, x, y, rot_y, span-along-the-edge)
        edges = [
            ("s", cx, y0 + inset, 0.0, span_x),
            ("n", cx, y1 - inset, 0.0, span_x),
            ("w", x0 + inset, cy, 90.0, span_y),
            ("e", x1 - inset, cy, 90.0, span_y),
        ]
        for name, x, y, rot, span in edges:
            count = max(2, min(10, round(span / 15.0)))
            anchors.append({
                "id": "site/perimeter_%s_lights" % name, "type": "streetlight",
                "source": "derived", "building": None,
                "pos": [round(x, 3), round(y, 3), STREETLIGHT_H], "rot_y": rot,
                "row": {"count": count, "spacing": round(span / count, 3)},
                "reacts_to_alarm": False,
            })
    return anchors


def merge_lights(site_spec, base_dir):
    """Merge every building's <name>.lights.json into one site-level lighting
    manifest: each anchor offset to world space and id-namespaced by building
    (mirrors merge_gameplay), plus the exterior streetlights Lot derives.
    Deterministic. Consumed by Lux's light-anchor loader."""
    site = {
        "light_manifest_version": "1.0.0",
        "site": site_spec["name"],
        "space": ("Blender Z-up, meters; rot_y = degrees about up; "
                  "pos is the fixture location"),
        "rig_library": "lux",
        "anchors": [],
    }
    for b in site_spec["buildings"]:
        bid = b["id"]
        placement = {"at": b["at"], "rot": b.get("rot", 0)}
        ref = _lights_ref_for(b)
        if not ref:
            continue
        lp = os.path.join(base_dir, ref)
        if not os.path.exists(lp):
            continue
        with open(lp, encoding="utf-8") as f:
            lm = json.load(f)
        for a in lm.get("anchors", []):
            wa = dict(a)
            wa["id"] = f"{bid}/{a.get('id', 'light')}"
            wa["building"] = bid
            x, y, z = a.get("pos", [0.0, 0.0, 0.0])
            wx, wy, wz = _place_point(x, y, z, placement)
            wa["pos"] = [round(wx, 4), round(wy, 4), round(wz, 4)]
            if "rot_y" in a:
                wa["rot_y"] = (a["rot_y"] + placement["rot"]) % 360
            if isinstance(a.get("room"), str):
                wa["room"] = f"{bid}/{a['room']}"
            site["anchors"].append(wa)

    site["anchors"].extend(_streetlight_anchors(site_spec))
    return site


# ---------------------------------------------------------------------------
# Godot scene generation
# ---------------------------------------------------------------------------
def _godot_transform(at, rot, z=0.0):
    """Godot Transform3D basis+origin string for a Y-up yaw rotation. Deli
    Counter is Z-up/metres; Godot is Y-up. We map site XY ground -> Godot XZ,
    site Z height -> Godot Y. Yaw (about site Z) becomes yaw about Godot Y."""
    r = math.radians(rot)
    c, s = math.cos(r), math.sin(r)
    # Godot Basis rows for a rotation about Y by -rot (handedness flip from the
    # Z-up->Y-up axis swap). origin: site (x,y) -> Godot (x, z_height, -y)
    bx = (c, 0.0, s)
    by = (0.0, 1.0, 0.0)
    bz = (-s, 0.0, c)
    ox, oy, oz = at[0], z, -at[1]
    nums = [bx[0], bx[1], bx[2], by[0], by[1], by[2], bz[0], bz[1], bz[2], ox, oy, oz]
    return ", ".join(f"{n:g}" for n in nums)


# ---------------------------------------------------------------------------
# Phase 2 — box-vocabulary outdoor as Godot scene nodes
# ---------------------------------------------------------------------------
# Outdoor is generated as Godot primitive nodes (BoxMesh + box collision), NOT a
# baked .glb — keeps Lot offline (no Blender) and blockout-honest. Strictly
# axis-aligned boxes / flat regions: paths, courtyards, perimeter walls, cover.
# No terrain, no organic shapes (that would break the thesis). Site coords (x,y)
# map to Godot (x, height, -y); thickness/height is Godot-Y.

# Outdoor surface heights are DERIVED, and the derivation changed once the kerb
# probe measured what the previous one cost.
#
# THE OLD SHAPE. SIDEWALK_H was a picked 0.16 carrying the comment "a kerb is
# MEANT to be a wall". A capsule walks up a step only while the contact normal
# stays inside floor_max_angle, so it clears STEP_MAX and no more -- 0.16 sits
# above that, making the kerb unclimbable from bare ground by design. Slabs then
# had to live in [SIDEWALK_H - step, step] so they could serve as a half-step
# onto it, which is why paths stood 0.08 proud of the ground with roads and
# courtyards 1.6 cm either side.
#
# WHY THAT WAS WRONG, measured rather than argued. lot_player.gd implements
# step-up, so the kerb never walled OUR player. It walled a stock
# CharacterBody3D -- which is what every recipient of a site pack has. The wall
# only ever stopped the person we ship to. coldrun_kerb_probe made it explicit:
# LOT_STEP_NEEDS_ASSIST on ground -> sidewalk, 0.16 m against a 0.1025 m
# ceiling, on a level that walks perfectly inside this repo.
#
# THE NEW SHAPE. Put the kerb under the step ceiling and the stack collapses:
# bare ground mounts the kerb, so slabs stop being a half-step to anything and
# can lie flat. Every outdoor surface becomes reachable by a stock controller
# with no step-up code -- which is what the standalone contract needs -- and
# every lip on the site goes, including the 1.6 cm path-over-road lip that no
# traversal gate could see.
GROUND_THICK = 0.5
WALL_THICK = 0.3
COVER = (1.0, 1.0, 1.0)
ROAD_COLOR = (0.13, 0.13, 0.14)        # asphalt
SIDEWALK_COLOR = (0.55, 0.55, 0.57)    # concrete, raised curb

#: The tallest step the contract player walks up with no step-up code.
STEP_MAX = float(_agent()["clearances"]["unassisted_step_max_m"])

#: A kerb the contract body mounts from bare ground, with margin rather than at
#: the limit: a rise exactly equal to STEP_MAX puts the contact normal exactly
#: on floor_max_angle, and shipping physics that sits on a boundary is how a
#: thing works on one machine and not the next.
KERB_FRACTION = 0.95
SIDEWALK_H = round(STEP_MAX * KERB_FRACTION, 4)

#: Flush -- but not zero. Two coplanar faces z-fight where a path crosses a
#: road, so these tiers exist to separate them and for no other reason. 2 mm
#: against a ~103 mm step ceiling is not a step, and check_steps will not see
#: it. The ordering (road lowest, courtyard highest) is kept so overlaps
#: resolve the way a reader expects.
SURFACE_BASE = 0.010
SURFACE_TIER = 0.002
ROAD_THICK = SURFACE_BASE
PATH_THICK = SURFACE_BASE + SURFACE_TIER
COURT_THICK = SURFACE_BASE + 2 * SURFACE_TIER

#: The rung below the ladder, for the one surface Lot does not own.
#:
#: A building's ground-floor slab tops out at y = 0 -- that is Deli Counter's
#: coordinate contract, not a choice made here -- and `GROUND_HOLE_INSET` cuts
#: the ground hole INSIDE the footprint on purpose, so the plate and the slab
#: overlap in a 0.45 m ring around every building. With the plate topping out
#: at 0 as well, that ring is two coplanar up-facing faces: roughly 59 m^2 of
#: z-fight per 38 x 28 building, hugging the inside of every exterior wall.
#:
#: No per-building gate could see it. One solid is Deli Counter's, the other is
#: Lot's, and they first share a scene after cater composes them.
#:
#: Sinking the plate rather than raising the building is deliberate: y = 0 is
#: read by slot transforms, opening heights, marker Z and the nav bake, while
#: nothing anywhere measures against the plate's top face.
GROUND_SINK = SURFACE_TIER
BLOCKER_COLOR = (0.38, 0.34, 0.30)     # warm massing -- reads as a building you can't enter


def _box_node(name, size, at_xyz, color=None):
    """(body_lines, subres_lines) for an axis-aligned StaticBody3D box with a
    BoxMesh + BoxShape3D, at Godot-frame (x, y_height, z). color: optional
    (r,g,b[,a]) -> a StandardMaterial3D override."""
    sx, sy, sz = size
    x, yh, z = at_xyz
    mat_line = f'material_override = SubResource("Mat_{name}")' if color else ''
    body = [
        f'[node name="{name}" type="StaticBody3D" parent="."]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {x:g}, {yh:g}, {z:g})',
        '',
        f'[node name="mesh" type="MeshInstance3D" parent="./{name}"]',
        f'mesh = SubResource("BoxMesh_{name}")',
    ]
    if mat_line:
        body.append(mat_line)
    body += [
        '',
        f'[node name="col" type="CollisionShape3D" parent="./{name}"]',
        f'shape = SubResource("BoxShape_{name}")',
        '',
    ]
    sub = [
        f'[sub_resource type="BoxMesh" id="BoxMesh_{name}"]',
        f'size = Vector3({sx:g}, {sy:g}, {sz:g})', '',
        f'[sub_resource type="BoxShape3D" id="BoxShape_{name}"]',
        f'size = Vector3({sx:g}, {sy:g}, {sz:g})', '',
    ]
    sub += _mat_sub(name, color)
    return body, sub


def _yaw_box_node(name, size, center_godot, yaw_deg, color=None):
    """Like _box_node but yaw'd about Godot-Y (for paths/roads between buildings).
    color: optional (r,g,b[,a]) -> a StandardMaterial3D override."""
    sx, sy, sz = size
    x, yh, z = center_godot
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    xform = (f"{c:g}, 0, {s:g}, 0, 1, 0, {-s:g}, 0, {c:g}, {x:g}, {yh:g}, {z:g}")
    mat_line = f'material_override = SubResource("Mat_{name}")' if color else ''
    body = [
        f'[node name="{name}" type="StaticBody3D" parent="."]',
        f'transform = Transform3D({xform})',
        '',
        f'[node name="mesh" type="MeshInstance3D" parent="./{name}"]',
        f'mesh = SubResource("BoxMesh_{name}")',
    ]
    if mat_line:
        body.append(mat_line)
    body += [
        '',
        f'[node name="col" type="CollisionShape3D" parent="./{name}"]',
        f'shape = SubResource("BoxShape_{name}")',
        '',
    ]
    sub = [
        f'[sub_resource type="BoxMesh" id="BoxMesh_{name}"]',
        f'size = Vector3({sx:g}, {sy:g}, {sz:g})', '',
        f'[sub_resource type="BoxShape3D" id="BoxShape_{name}"]',
        f'size = Vector3({sx:g}, {sy:g}, {sz:g})', '',
    ]
    sub += _mat_sub(name, color)
    return body, sub


def _mat_sub(name, color):
    if not color:
        return []
    if len(color) == 3:
        color = color + (1.0,)
    r, g, b, a = color
    lines = [f'[sub_resource type="StandardMaterial3D" id="Mat_{name}"]']
    if a < 1.0:
        lines.append('transparency = 1')
    lines.append(f'albedo_color = Color({r:g}, {g:g}, {b:g}, {a:g})')
    lines.append('')
    return lines


def _blocker_source(bk):
    """Optional facade-shell geometry for a blocker (.tscn wins over .glb), or
    None to fall back to a plain box."""
    return bk.get("scene") or bk.get("glb")


def _ground_tiles(rect, holes):
    """Axis-aligned decomposition of the ground rect minus hole rects.

    `rect` is the resolved (x0, y0, x1, y1) plate from `site_extent.resolve` --
    not a size, because a plate is not necessarily centred on the origin and
    assuming it was is what put a building's ground hole off the edge of the
    world. Band split on hole y-edges, then per-band x-interval subtraction.
    Deterministic; returns (x0, y0, x1, y1) site-space tiles.

    A hole outside the plate is dropped and a hole straddling the rim is
    trimmed, exactly as before -- but by this point `site_extent.resolve` has
    grown the plate to contain every hole, and `site_extent.hole_findings`
    reports any that it could not. The clipping here is arithmetic, no longer
    a decision taken in silence."""
    x_min, y_min, x_max, y_max = rect
    holes = [(max(x_min, h[0]), max(y_min, h[1]),
              min(x_max, h[2]), min(y_max, h[3])) for h in holes
             if h[0] < x_max and h[2] > x_min and h[1] < y_max and h[3] > y_min]
    if not holes:
        return [(x_min, y_min, x_max, y_max)]
    ys = sorted({y_min, y_max} | {v for h in holes for v in (h[1], h[3])
                                  if y_min < v < y_max})
    tiles = []
    for y0, y1 in zip(ys, ys[1:]):
        mid = (y0 + y1) / 2
        cuts = sorted({x_min, x_max} | {v for h in holes
                                        if h[1] < mid < h[3]
                                        for v in (h[0], h[2])
                                        if x_min < v < x_max})
        for x0, x1 in zip(cuts, cuts[1:]):
            cxm = (x0 + x1) / 2
            if any(h[0] < cxm < h[2] and h[1] < mid < h[3] for h in holes):
                continue
            tiles.append((x0, y0, x1, y1))
    return tiles


#: How far inside a footprint the ground hole is cut. The overlap keeps the
#: building's exterior walls seated on ground with no gap at the threshold.
GROUND_HOLE_INSET = 0.45


def ground_holes(site_spec, self_flooring=None):
    """The rects cut out of the ground plate, in site space.

    Shared by the scene builder and by the gate that checks the plate contains
    them, so the two cannot disagree about which holes were cut. `self_flooring`
    is the set of building ids whose geometry demonstrably brings collision
    (see `site_ground.audit`); None means nothing was checked, so nothing is
    cut -- an unchecked assumption must not be able to open a void.
    """
    import site_extent
    floors = set() if self_flooring is None else set(self_flooring)
    holes = []
    for bdef in site_spec.get("buildings") or []:
        if str(bdef.get("id", "?")) not in floors:
            continue
        # `_footprint` specifically: the annotation `merge_gameplay` writes from
        # the building's own gameplay file. A footprint recovered from anywhere
        # else is fine for sizing the ground and not authority enough to cut a
        # hole in it.
        if not bdef.get("_footprint"):
            continue
        rect = site_extent.rotated_footprint(bdef)
        if rect is None:
            continue
        hole = site_extent.grow(rect, -GROUND_HOLE_INSET)
        if hole[2] > hole[0] and hole[3] > hole[1]:
            holes.append(hole)
    return holes


def _kerb_crossings(site_spec, bld, origin, along, perp, offset, length, width):
    """(centre, span) per crossing: where a path OR another road crosses this
    kerb, and how much kerb that crossing consumes measured along it.

    Distances are from the road's start point. Anything that runs parallel, or
    crosses beyond either end, contributes nothing -- there is no crossing to
    drop. `width` is the kerb band's depth."""
    ox, oy = origin
    ux, uy = along
    px, py = perp
    # A point on this kerb is origin + u*t + p*offset.
    kx, ky = ox + px * offset, oy + py * offset
    out = []
    # Everything that crosses this kerb and therefore needs it dropped. `paths`
    # are the site's designed circulation; ROADS were missing entirely, and at a
    # junction that means one road's kerb runs uncut across the other's
    # carriageway -- four raised strips through the crossroads on
    # warehouse_district, a 0.16 m wall across a road. No gate catches it either:
    # site_steps reports a rise only where a designed PATH crosses it.
    #
    # The angle-aware span below is already correct for a road; a road simply
    # brings its carriageway width where a path brings its own. And a road does
    # not cut its own kerb without a special case, because a road is parallel to
    # its own sidewalk and the parallel test drops it.
    crossers = [(p, float(p.get("width", 6.0)), "path")
                for p in site_spec.get("paths", []) or []]
    crossers += [(r, float(r.get("width", 9.0)), "road")
                 for r in site_spec.get("roads", []) or []]
    for p, pw, kind in crossers:
        try:
            pax, pay = bld[p["from"]]["at"] if "from" in p else p["a"]
            pbx, pby = bld[p["to"]]["at"] if "to" in p else p["b"]
        except (KeyError, TypeError):
            continue
        vx, vy = pbx - pax, pby - pay
        # solve  k + u*t = pa + v*s   for t
        den = ux * (-vy) - uy * (-vx)
        if abs(den) < 1e-9:
            continue                      # parallel: never crosses
        rx, ry = pax - kx, pay - ky
        t = (rx * (-vy) - ry * (-vx)) / den
        s = (ux * ry - uy * rx) / den
        if not (-0.05 <= s <= 1.05):
            continue                      # crosses the LINE, not the path
        if t < 0.0 or t > length:
            continue                      # past the end of this kerb
        # How much kerb this crossing consumes ALONG the kerb. A strip of width
        # pw meeting a LINE at angle t leaves pw/sin(t) on that line, not pw --
        # and a kerb is not a line, it is a band `width` deep, so the strip also
        # shears along it by width*cos(t)/sin(t). Dropping only pw assumed every
        # crossing was head-on: on ballpark_block a 6 m path meets the kerb at
        # 35 deg and needs 12.0 m, so a 7.2 m cut left the route spilling onto
        # the sidewalk sections either side and hitting a 0.16 m wall on both.
        vl = math.hypot(vx, vy) or 1e-9
        cos_t = abs(vx * ux + vy * uy) / vl
        sin_t = abs(vx * px + vy * py) / vl
        span = (pw + float(width) * cos_t) / max(sin_t, 1e-6)
        if span > 3.0 * pw:
            # Shallow enough that the path is running ALONG the kerb rather than
            # across it. The span is still emitted, because a body has to get
            # over the rise somewhere -- but a designer should see it, since the
            # honest fix is usually to re-route or to run the path on the
            # sidewalk instead of through it.
            print(f"[lot] LOT_KERB_CROSSED_SHALLOW: a {pw} m {kind} meets "
                  f"this kerb at "
                  f"{math.degrees(math.asin(min(1.0, sin_t))):.0f} deg "
                  f"{t:.1f} m along it, so {span:.1f} m of kerb is dropped to "
                  f"keep the crossing walkable. Re-route it closer to square, "
                  f"or run it along the sidewalk rather than across it.")
        out.append((t, span))
    return out


def _split_span(length, cuts, margin=0.6):
    """[(t0, t1, is_cut)] along a kerb: crossings, and the kerb between them.

    Each entry in `cuts` is (centre, span) from _kerb_crossings: where a route
    crosses, and the along-kerb length it actually covers -- which is wider than
    the path wherever the path meets the kerb at an angle. `margin` widens it
    further so a body approaching off-centre still meets the dropped section
    rather than clipping its corner, the same reason a real dropped kerb is
    wider than the crossing painted on it."""
    spans = []
    bands = []
    for t, span in sorted(cuts):
        half = span / 2.0 + margin
        bands.append((max(0.0, t - half), min(length, t + half)))
    merged = []
    for b in bands:
        if merged and b[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b[1]))
        else:
            merged.append(b)
    cursor = 0.0
    for b0, b1 in merged:
        if b0 > cursor:
            spans.append((cursor, b0, False))
        spans.append((b0, b1, True))
        cursor = b1
    if cursor < length:
        spans.append((cursor, length, False))
    return spans


def _outdoor_nodes(site_spec, preview=False, self_flooring=None):
    """(body_lines, subres_lines) for all Phase-2 outdoor geometry.

    `self_flooring` is the set of building ids whose geometry demonstrably
    brings collision (see site_ground.audit). Only those get a hole cut in the
    ground beneath them. Passing None means nothing has been checked, so no
    holes are cut -- an unchecked assumption must not be able to open a void.
    """
    body, sub = [], []
    bld = {b["id"]: b for b in site_spec["buildings"]}
    if SIDEWALK_H > STEP_MAX:
        # RE-AIMED, not deleted. The old test asked whether the half-step band
        # had collapsed, which a kerb under the step ceiling makes unreachable
        # -- and a check that cannot fail is indistinguishable from one that
        # passed. This is the invariant
        # the flat surfaces above actually rest on: if the kerb ever climbs back
        # over the step ceiling, they become unreachable and nothing else here
        # would notice.
        print(f"[lot] LOT_KERB_ABOVE_STEP: the {SIDEWALK_H:.4f} m kerb is taller "
              f"than the {STEP_MAX:.4f} m a contract body walks up unassisted, "
              f"so a stock CharacterBody3D cannot leave the road except at a "
              f"crossing. The flat surfaces assume it can. Lower SIDEWALK_H, or "
              f"put the slabs back on a half-step band.")
    # preview massing boxes are Lot's own StaticBody3D geometry, but they are
    # solid blocks rather than floored interiors, so the ground stays under
    # them too and the site remains walkable up to the massing.
    floors = set() if self_flooring is None else set(self_flooring)

    import site_extent
    ground = site_extent.resolve(site_spec)
    g = site_spec.get("ground")
    if g and ground.rect:
        # NOT one solid box: a ground slab running through a building
        # footprint seals its basement stairwell (Phase 1 site walktests:
        # basements bake as disjoint islands). Cut an inset hole per
        # footprint -- the inset keeps exterior walls seated on ground with
        # no exterior gap; the building's own slabs floor the interior.
        #
        # "The building's own slabs floor the interior" is a premise, not a
        # fact: a plain shell.glb imports as MeshInstance3D with no collision
        # at all. Cutting under one of those leaves a hole nothing fills, and
        # four adjacent footprints merge into a void big enough to swallow the
        # spawn, the objective and every enemy. Cut only where checked.
        holes = ground_holes(site_spec, floors)
        for j, (x0, y0, x1, y1) in enumerate(_ground_tiles(ground.rect, holes)):
            # Top at -GROUND_SINK, bottom where it always was: the plate
            # gets thicker rather than moving, so nothing below it shifts.
            bl, sr = _box_node("Ground" if j == 0 else f"Ground_{j}",
                               (x1 - x0, GROUND_THICK - GROUND_SINK, y1 - y0),
                               ((x0 + x1) / 2,
                                -(GROUND_THICK + GROUND_SINK) / 2,
                                -(y0 + y1) / 2))
            body += bl
            sub += sr

    for i, p in enumerate(site_spec.get("paths", [])):
        w = p.get("width", 3.0)
        a = bld[p["from"]]["at"] if "from" in p else p["a"]
        b2 = bld[p["to"]]["at"] if "to" in p else p["b"]
        ax, ay = a
        bx_, by_ = b2
        cx, cy = (ax + bx_) / 2, (ay + by_) / 2
        dx, dy = bx_ - ax, by_ - ay
        length = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(dy, dx))
        # path lies along its length (x), width across (z), thin (y)
        # Extended DOWN by GROUND_SINK so it stays buried in the plate; the
        # top face does not move, so every height check reads the same number.
        bl, sr = _yaw_box_node(f"path_{i}",
                               (length, PATH_THICK + GROUND_SINK, w),
                               (cx, (PATH_THICK - GROUND_SINK) / 2, -cy), -ang)
        body += bl
        sub += sr

    for i, cdef in enumerate(site_spec.get("courtyards", [])):
        cx, cy = cdef["at"]
        sx, sy = cdef.get("size_x", 10), cdef.get("size_y", 10)
        bl, sr = _box_node(f"courtyard_{i}",
                           (sx, COURT_THICK + GROUND_SINK, sy),
                           (cx, (COURT_THICK - GROUND_SINK) / 2, -cy))
        body += bl
        sub += sr

    per = site_spec.get("perimeter")
    if per and ground.rect:
        h = per.get("height", 3.0)
        # The wall rings the ground that was actually built, not a rect derived
        # a second time from the declared size: a perimeter around a plate that
        # has been extended would otherwise cut straight through the site.
        x0, y0, x1, y1 = ground.rect
        gx, gy = x1 - x0, y1 - y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for name, size, at_xyz in [
            ("perim_N", (gx, h, WALL_THICK), (cx, h / 2, -y1)),
            ("perim_S", (gx, h, WALL_THICK), (cx, h / 2, -y0)),
            ("perim_E", (WALL_THICK, h, gy), (x1, h / 2, -cy)),
            ("perim_W", (WALL_THICK, h, gy), (x0, h / 2, -cy)),
        ]:
            bl, sr = _box_node(name, size, at_xyz)
            body += bl
            sub += sr

    for i, cv in enumerate(site_spec.get("cover", [])):
        cx, cy = cv["at"]
        sx, sy, sz = cv.get("size", COVER)
        bl, sr = _box_node(f"cover_{i}", (sx, sy, sz), (cx, sy / 2, -cy))
        body += bl
        sub += sr

    # roads: the street grid the block is built on (DELCO/Philly grain). A road
    # is a flat asphalt strip between two points, optionally with raised concrete
    # sidewalks running alongside. Buildings + blockers front onto it.
    for i, rd in enumerate(site_spec.get("roads", [])):
        ax, ay = bld[rd["from"]]["at"] if "from" in rd else rd["a"]
        bx_, by_ = bld[rd["to"]]["at"] if "to" in rd else rd["b"]
        w = rd.get("width", 9.0)
        cx, cy = (ax + bx_) / 2, (ay + by_) / 2
        dx, dy = bx_ - ax, by_ - ay
        length = math.hypot(dx, dy) or 0.001
        ang = math.degrees(math.atan2(dy, dx))
        bl, sr = _yaw_box_node(f"road_{i}",
                               (length, ROAD_THICK + GROUND_SINK, w),
                               (cx, (ROAD_THICK - GROUND_SINK) / 2, -cy),
                               -ang, ROAD_COLOR)
        body += bl
        sub += sr
        sw = rd.get("sidewalk")
        if sw:
            ux, uy = dx / length, dy / length        # along
            px, py = -uy, ux                          # perpendicular (left)
            off = w / 2 + sw / 2
            # Where the site's own circulation crosses this kerb. A kerb is
            # SUPPOSED to be a wall -- 0.16 m against an unassisted step limit
            # of 0.117 -- and the answer is not to flatten it but to drop it
            # where people are meant to cross, exactly as a real street does.
            # Anything this does not reach is still a wall, and site_steps.py
            # says so rather than leaving it to be discovered in play.
            for side, sgn in (("L", 1), ("R", -1)):
                lcx, lcy = cx + px * off * sgn, cy + py * off * sgn
                cuts = _kerb_crossings(site_spec, bld,
                                       (ax, ay), (ux, uy), (px, py),
                                       off * sgn, length, sw)
                spans = _split_span(length, cuts)
                for j, (t0, t1, is_cut) in enumerate(spans):
                    seg = t1 - t0
                    if seg <= 0.05:
                        continue
                    mid = (t0 + t1) / 2.0 - length / 2.0
                    scx = lcx + ux * mid
                    scy = lcy + uy * mid
                    h = ROAD_THICK if is_cut else SIDEWALK_H
                    nm = (f"kerbcut_{i}{side}_{j}" if is_cut
                          else f"sidewalk_{i}{side}_{j}")
                    bl, sr = _yaw_box_node(
                        nm, (seg, h, sw), (scx, h / 2, -scy), -ang,
                        SIDEWALK_COLOR)
                    body += bl
                    sub += sr

    # blockers: non-interactable filler buildings -- SOLID collision massing you
    # cannot enter. They wall the street and channel the player toward the real
    # (enterable) heist buildings. The opposite of the see-through preview boxes.
    for i, bk in enumerate(site_spec.get("blockers", [])):
        # a blocker with a facade-shell ref is instanced in write_godot_scene
        # (like a real building); in preview, ignore the shell and box it.
        if _blocker_source(bk) and not preview:
            continue
        ax, ay = bk["at"]
        sx = bk.get("size_x", 12.0)
        sy = bk.get("size_y", 12.0)
        h = bk.get("height", 8.0)
        rot = bk.get("rot", 0)
        col = tuple(bk.get("color", BLOCKER_COLOR))
        if rot:
            bl, sr = _yaw_box_node(f"blocker_{i}", (sx, h, sy),
                                   (ax, h / 2, -ay), rot, col)
        else:
            bl, sr = _box_node(f"blocker_{i}", (sx, h, sy), (ax, h / 2, -ay), col)
        body += bl
        sub += sr

    return body, sub


def _preview_building_nodes(b, height):
    """Greybox massing for a building with no .glb yet: a walkable footprint pad,
    a see-through massing box you walk through (no collision), and a floating id
    label. Lets you walk the LEVEL (placement / routes / scale) before any
    Blender build. Returns (body_lines, sub_lines)."""
    bid = b["id"]
    fx, fy = b.get("footprint", [20.0, 20.0])
    h = max(3.0, float(height or 6.0))
    xform = _godot_transform(b["at"], b.get("rot", 0))
    body = [
        f'[node name="{bid}" type="Node3D" parent="."]',
        f'transform = Transform3D({xform})', '',
        f'[node name="pad" type="StaticBody3D" parent="./{bid}"]',
        'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.06, 0)', '',
        f'[node name="mesh" type="MeshInstance3D" parent="./{bid}/pad"]',
        f'mesh = SubResource("PadMesh_{bid}")', '',
        f'[node name="col" type="CollisionShape3D" parent="./{bid}/pad"]',
        f'shape = SubResource("PadShape_{bid}")', '',
        f'[node name="massing" type="MeshInstance3D" parent="./{bid}"]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, {h/2:g}, 0)',
        f'mesh = SubResource("MassMesh_{bid}")',
        f'material_override = SubResource("MassMat_{bid}")', '',
        f'[node name="label" type="Label3D" parent="./{bid}"]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, {h+1.0:g}, 0)',
        f'text = "{bid}"',
        'font_size = 200',
        'billboard = 1', '',
    ]
    sub = [
        f'[sub_resource type="BoxMesh" id="PadMesh_{bid}"]',
        f'size = Vector3({fx:g}, 0.12, {fy:g})', '',
        f'[sub_resource type="BoxShape3D" id="PadShape_{bid}"]',
        f'size = Vector3({fx:g}, 0.12, {fy:g})', '',
        f'[sub_resource type="BoxMesh" id="MassMesh_{bid}"]',
        f'size = Vector3({fx:g}, {h:g}, {fy:g})', '',
        f'[sub_resource type="StandardMaterial3D" id="MassMat_{bid}"]',
        'transparency = 1',
        'albedo_color = Color(0.45, 0.55, 0.7, 0.28)', '',
    ]
    return body, sub


def write_godot_scene(site_spec, merged, out_path, glb_dir=".", preview=False,
                      portable=False, self_flooring=None):
    """Emit a .tscn that instances each building (a .tscn scene or a baked .glb)
    at its placement, plus Phase-2 outdoor geometry. With preview=True, buildings
    are emitted as greybox massing boxes instead (no .glb needed) so the level is
    walkable before any Blender build. With portable=True, ext_resource paths
    are emitted RELATIVE to the scene file (no res:// prefix) so the scene +
    its siblings form a drop-anywhere folder (a shareable site pack)."""
    prefix = "" if portable else "res://"
    res_ids = {}
    res_lines = []
    next_id = 1
    if not preview:
        for b in site_spec["buildings"]:
            src = _building_source(b)
            if src not in res_ids:
                rid = f"b{next_id}"
                res_ids[src] = rid
                next_id += 1
                rel = os.path.join(glb_dir, src).replace("\\", "/")
                rel = rel[2:] if rel.startswith("./") else rel
                res_lines.append(
                    f'[ext_resource type="PackedScene" path="{prefix}{rel}" id="{rid}"]')
        # facade-shell blockers (optional .glb/.tscn) instance like buildings
        for bk in site_spec.get("blockers", []):
            src = _blocker_source(bk)
            if src and src not in res_ids:
                rid = f"b{next_id}"
                res_ids[src] = rid
                next_id += 1
                rel = os.path.join(glb_dir, src).replace("\\", "/")
                rel = rel[2:] if rel.startswith("./") else rel
                res_lines.append(
                    f'[ext_resource type="PackedScene" path="{prefix}{rel}" id="{rid}"]')

    outdoor_body, outdoor_sub = _outdoor_nodes(
        site_spec, preview=preview, self_flooring=self_flooring)

    building_body, building_sub = [], []
    if preview:
        for b in site_spec["buildings"]:
            bb, bs = _preview_building_nodes(b, b.get("_preview_height"))
            building_body += bb
            building_sub += bs

    n_sub = sum(1 for ln in (outdoor_sub + building_sub) if ln.startswith("[sub_resource"))
    load_steps = len(res_lines) + n_sub + 1

    lines = [f'[gd_scene load_steps={load_steps} format=3]', '']
    lines += res_lines + ['']
    lines += outdoor_sub + building_sub
    lines += ['[node name="Site" type="Node3D"]', '']
    lines += outdoor_body
    lines += building_body
    if not preview:
        for b in site_spec["buildings"]:
            rid = res_ids[_building_source(b)]
            xform = _godot_transform(b["at"], b.get("rot", 0))
            lines.append(
                f'[node name="{b["id"]}" parent="." '
                f'instance=ExtResource("{rid}")]')
            lines.append(f'transform = Transform3D({xform})')
            lines.append('')
        for i, bk in enumerate(site_spec.get("blockers", [])):
            src = _blocker_source(bk)
            if not src:
                continue
            rid = res_ids[src]
            xform = _godot_transform(bk["at"], bk.get("rot", 0))
            lines.append(
                f'[node name="blocker_{i}" parent="." '
                f'instance=ExtResource("{rid}")]')
            lines.append(f'transform = Transform3D({xform})')
            lines.append('')
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# walkable scene (--walkable): a *_walk.tscn that drops a player at the crew
# spawn, bakes site nav, and beacons the objective + extraction. Pairs with the
# lot addon scripts (godot/addons/lot/). Buildings still come from the site.tscn.
# ---------------------------------------------------------------------------
def _building_at(site_spec, bid):
    for b in site_spec.get("buildings", []):
        if b.get("id") == bid:
            return b.get("at", [0.0, 0.0])
    return [0.0, 0.0]


def _room_bounds_at(merged, point):
    """The bounds of the smallest merged room containing `point`, or None.

    A nav hook that has to be moved off a prop should not leave the room it
    was placed in: the mission is designed around where it happens, and a
    hook that wanders into the corridor is a different level. Smallest-wins so
    a room nested inside a hall keeps the tighter bound.
    """
    x, y = point[0], point[1]
    best = None
    for r in merged.get("rooms", []) or []:
        b = r.get("bounds")
        if not b or len(b) != 4:
            continue
        if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
            area = abs(b[2] - b[0]) * abs(b[3] - b[1])
            if best is None or area < best[0]:
                best = (area, (b[0], b[1], b[2], b[3]))
    return best[1] if best else None


def _destination_bounds(merged, positions):
    """key -> room rect, for the mission points that stand in a room."""
    out = {}
    for key in ("spawn", "objective", "extraction"):
        point = positions.get(key)
        if point is None:
            continue
        rect = _room_bounds_at(merged, point)
        if rect:
            out[key] = rect
    return out


def _walk_positions(site_spec, merged):
    """Resolve crew-spawn / objective / extraction world (site) coords for the
    walk scene, robust to heist branches that emit only arrays (no objective
    marker). Returns dict of (x, y, z) site-space tuples."""
    markers = merged.get("markers", [])

    def first_marker(types, building=None):
        for m in markers:
            if m.get("type") in types and (building is None or m.get("building") == building):
                return (m.get("x", 0.0), m.get("y", 0.0), m.get("z", 0.0))
        return None

    spawn_b = site_spec.get("spawn")
    obj_b = site_spec.get("objective")
    extr_b = site_spec.get("extraction")

    # a site-level crew_spawn marker wins (symmetric with the site-level
    # extraction marker below): where the crew stages is a SITE concern —
    # across the street, down the block — not something a building's own
    # spec should have to know about.
    spawn = None
    for sm in merged.get("site_markers", []):
        if sm.get("type") == "crew_spawn":
            a = sm.get("at", [0.0, 0.0])
            spawn = (a[0], a[1], 0.0)
            break
    if spawn is None:
        spawn = first_marker(("crew_spawn", "attacker_spawn"), spawn_b) \
            or first_marker(("crew_spawn", "attacker_spawn"))
    if spawn is None:
        at = _building_at(site_spec, spawn_b) if spawn_b else [0.0, 0.0]
        spawn = (at[0], at[1], 0.0)

    objective = first_marker(("objective",), obj_b)
    if objective is None and obj_b:
        at = _building_at(site_spec, obj_b)
        for o in merged.get("objectives", []):
            if str(o.get("id", "")).startswith(obj_b + "/"):
                objective = (o.get("x", 0.0) + at[0], o.get("y", 0.0) + at[1], o.get("z", 0.0))
                break
        if objective is None:
            objective = (at[0], at[1], 0.0)
    objective = objective or (0.0, 0.0, 0.0)

    extraction = None
    for sm in merged.get("site_markers", []):
        if sm.get("type") == "extraction":
            a = sm.get("at", [0.0, 0.0])
            extraction = (a[0], a[1], 0.0)
            break
    if extraction is None:
        extraction = first_marker(("extraction",), extr_b) or first_marker(("extraction",))
    if extraction is None and extr_b:
        at = _building_at(site_spec, extr_b)
        extraction = (at[0], at[1], 0.0)
    extraction = extraction or (0.0, 0.0, 0.0)

    return {"spawn": tuple(spawn), "objective": tuple(objective),
            "extraction": tuple(extraction)}


def _v3(world_xyz, lift=0.0):
    """Site (x, y, z) -> Godot Vector3 string (x, z+lift, -y)."""
    x, y, z = world_xyz
    return f"Vector3({x:g}, {z + lift:g}, {-y:g})"


# Godot 4: String::invalid_node_name_characters. set_name() rewrites each of
# these to "_" when a scene loads, so a name written with one in it does not
# survive -- and every `parent="..."` string still pointing at the original is
# then parsed as a PATH, finds nothing, and the child node is dropped. Marker
# names are building-namespaced ("b0/LADDER_0"), so every ladder volume Lot
# emitted arrived in the engine with no CollisionShape3D and nothing could
# climb it. Apply Godot's own rule at write time so name and parent agree.
_GODOT_BAD_NAME_CHARS = '.:@/"%'


def _node_name(raw):
    return "".join("_" if c in _GODOT_BAD_NAME_CHARS else c for c in str(raw))


def _lasertag_hook_nodes(pos, site_spec=None, enemy_count=6, lateral=1.5,
                         solids=None, bounds=None):
    """Lot's half of the LaserTag map contract (LaserTag TDD 8).

    LaserTag's evaluator discovers its fixtures by node name -- LT_PlayerSpawn,
    LT_EnemySpawnPoints, LT_ObjectivePoint, and the optional LT_PlayerRoutePoints
    / LT_CoverTestPoints -- and short-circuits before a single run if the
    required three are absent. A walk scene that carries spawn/objective/
    extraction only as script properties reads to the evaluator as an empty map:
    it reports a grade for a match it never played. Emit the nodes so the
    positions Lot already knows are the positions LaserTag actually reads.

    Enemies are still an engagement sequence spread along the spawn ->
    objective -> extraction route, but where each one lands is decided by
    `site_spawns` against the footprints and ground rect this site was built
    from. The arithmetic that used to place them knew only the route, so on any
    site whose buildings straddle it the whole sequence went indoors and
    LaserTag refused the map. `site_spawns.place_enemies` returns the findings
    for anything it could not honour; `_lasertag_hook_nodes` returns only the
    body, and the caller that has somewhere to put findings asks for them.
    """
    import site_spawns

    # The nav hooks first: a destination on top of a counter has no route to
    # it, and every point below is derived from these three. `solids` is the
    # site's collision reading when the caller has one -- without it the hook
    # is only floored, not moved off whatever it is standing in.
    pos = site_spawns.seat_destinations(
        pos, solids=solids, bounds=bounds)[0]
    route = [pos["spawn"], pos["objective"], pos["extraction"]]
    enemies = site_spawns.place_enemies(
        site_spec or {}, pos, enemy_count=enemy_count,
        lateral=lateral).positions

    def _hook(name, parent, world, lift=0.0):
        return [f'[node name="{name}" type="Node3D" parent="{parent}"]',
                f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, '
                f'{_v3(world, lift)[8:-1]})', '']

    body = _hook("LT_PlayerSpawn", ".", pos["spawn"], 1.0)
    body += ['[node name="LT_EnemySpawnPoints" type="Node3D" parent="."]', '']
    for i, e in enumerate(enemies):
        body += _hook(f"Enemy_{i}", "LT_EnemySpawnPoints", e, 1.0)
    body += _hook("LT_ObjectivePoint", ".", pos["objective"])
    body += ['[node name="LT_PlayerRoutePoints" type="Node3D" parent="."]', '']
    for i, r in enumerate(route):
        body += _hook(f"Route_{i}", "LT_PlayerRoutePoints", r)
    body += ['[node name="LT_CoverTestPoints" type="Node3D" parent="."]', '']
    ox, oy, oz = pos["objective"]
    # The cover the crew can actually hide behind, which until now this never
    # named. These four points were a hardcoded rosette 5 m around the
    # objective, unrelated to any cover the site had -- so
    # `LT_BotPlayerController._on_damaged` seeking "nearest cover" was always
    # seeking the objective, whatever `site_cover` had placed and wherever it
    # had placed it. On seed 5017 that meant a crew taking fire 69 m out broke
    # off its route to walk toward four imaginary points sitting 10.8-19.4 m
    # from an enemy spawn. It never arrived; it died at 11.9 s having fired
    # twice.
    #
    # `assemble` extends `site_spec["cover"]` from the cover plan before the
    # walk scene is written, so the real positions are here to be read. A site
    # with no planned cover keeps the rosette: the hook is optional to Laser
    # Tag, but an empty node reads as "this map has no cover" when what is true
    # is "nothing was planned", and those want different answers.
    placed = [c for c in (site_spec or {}).get("cover", [])
              if isinstance(c, dict) and len(c.get("at", ())) >= 2]
    if placed:
        for i, piece in enumerate(placed):
            cx, cy = piece["at"][0], piece["at"][1]
            body += _hook(f"Cover_{i}", "LT_CoverTestPoints", (cx, cy, oz))
    else:
        for i, (cx, cy) in enumerate(((5.0, 0.0), (-5.0, 0.0),
                                      (0.0, 5.0), (0.0, -5.0))):
            body += _hook(f"Cover_{i}", "LT_CoverTestPoints",
                          (ox + cx, oy + cy, oz))
    return body


def _ladder_volume_nodes(merged):
    """Area3D climb volumes (group "ladder") from the site's gameplay ladder
    markers -- Lot's half of the DC ladder contract. DC bakes the LADDER_
    anchor + climb metadata into the glb/gameplay; something import- or
    scene-side must build the volume (in a DC project the post-import plugin
    does it; in a Lot walk scene, this does). Sizing mirrors
    deli_counter_postimport.gd: +1 m dismount lip over the top, generous
    square footprint so building rotation can't turn the volume edge-on."""
    body, subs = [], []
    for i, m in enumerate(merged.get("markers", [])):
        if m.get("type") != "ladder":
            continue
        ch = float(m.get("climb_height", 3.0))
        w = max(float(m.get("width", 0.5)) + 0.8, 1.0)
        d = float(m.get("depth", 0.15)) + 1.0
        fp = max(w, d)
        gx, gy, gz = m["x"], m["z"], -m["y"]          # site -> Godot
        sid = f"LadderBox_{i}"
        subs += [f'[sub_resource type="BoxShape3D" id="{sid}"]',
                 f'size = Vector3({fp}, {ch + 1.0}, {fp})', '']
        nm = _node_name(m.get("name", f"LADDER_{i}"))
        body += [
            f'[node name="{nm}_climb" type="Area3D" parent="." groups=["ladder"]]',
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, '
            f'{gx}, {gy}, {gz})',
            'monitoring = true',
            'monitorable = true', '',
            f'[node name="shape" type="CollisionShape3D" parent="{nm}_climb"]',
            f'shape = SubResource("{sid}")',
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, '
            f'0, {ch * 0.5}, 0)', '',
        ]
    return body, subs


def _player_metric(key, fallback):
    """One body metric from the contract, for the walk scene's Player node.

    Exists so the walk scene cannot carry a second opinion about the body. Each
    of these was a literal in the emitted .tscn, and lot_player.gd carried a
    third copy of the step height as an export default.
    """
    try:
        return float(_agent()["characters"]["player"][key])
    except (KeyError, TypeError, ValueError):
        return fallback


def write_walk_scene(site_spec, merged, walk_out, site_tscn_base,
                     addon_dir="addons/lot", portable=False, solids=None):
    """Emit <name>_walk.tscn: instances the composed site under a baked
    NavigationRegion3D, spawns a first-person player at the crew start, and
    beacons the objective + extraction. Reuses godot/addons/lot scripts."""
    import site_spawns

    raw = _walk_positions(site_spec, merged)
    # Seat the mission points here, once, and write the seated ones everywhere.
    # The scene used to carry two different answers for the same destination --
    # `objective_pos` took the marker's z verbatim while LT_ObjectivePoint was
    # floored -- so the beacon the player walks to and the point the bot paths
    # to were metres apart in a scene that looked internally consistent.
    # Findings are dropped here on purpose: `assemble` runs the same call on
    # the same inputs and reports them, and a finding raised twice reads as two
    # problems.
    pos = site_spawns.seat_destinations(
        raw, solids=solids, bounds=_destination_bounds(merged, raw))[0]
    _p = "" if portable else "res://"
    _a = "" if portable else addon_dir + "/"
    ladder_body, ladder_subs = _ladder_volume_nodes(merged)
    lt_body = _lasertag_hook_nodes(
        pos, site_spec, solids=solids,
        bounds=_destination_bounds(merged, pos))
    sx, sy, sz = pos["spawn"]
    player_godot = f"{sx:g}, {sz + 1.0:g}, {-sy:g}"   # eye/capsule lift

    lines = [
        f'[gd_scene load_steps={9 + sum(1 for l in ladder_subs if l.startswith("[sub_resource"))} format=3]', '',
        f'[ext_resource type="PackedScene" path="{_p}{site_tscn_base}.tscn" id="site"]',
        f'[ext_resource type="Script" path="{_p}{_a}lot_site_walk.gd" id="walk"]',
        f'[ext_resource type="Script" path="{_p}{_a}lot_player.gd" id="player"]', '',
        '[sub_resource type="NavigationMesh" id="NavMesh"]',
        'geometry_parsed_geometry_type = 2',
        # 0.15 m cells + 0.4 m agent: voxel erosion is per-cell, so coarser
        # bakes eat legal doorways and fragment interiors into islands
        f'cell_size = {_agent()["nav_bake"]["cell_size_m"]}',
        f'cell_height = {_agent()["nav_bake"]["cell_height_m"]}',
        f'agent_radius = {_agent()["nav_bake"]["agent_radius_m"]}',
        f'agent_height = {_agent()["nav_bake"]["agent_height_m"]}',
        # stairs bake as ~42 deg collision ramps; the default 45 deg slope
        # limit quantizes them into disjoint islands (same fix as nav_gate)
        f'agent_max_slope = {_agent()["nav_bake"]["agent_max_slope_deg"]}',
        f'agent_max_climb = {_agent()["nav_bake"]["agent_max_climb_m"]}', '',
        # The body a human walks in the preview scene. These two were fixed
        # string literals -- 0.4 radius and 1.8 height -- sitting three lines
        # under an agent_radius and agent_height that both read the contract.
        # So the shipped capsule was wider than the contract player every
        # clearance had been derived for. Deliberately not quoting the old
        # values in a way a search could match: a comment mentioning
        # `site_steps.py` is what made this patch's own idempotency guard
        # report success while skipping the wiring. Godot's `height` is the
        # FULL height including both hemispheres.
        '[sub_resource type="CapsuleShape3D" id="PlayerCol"]',
        f'radius = {_agent()["characters"]["player"]["radius_m"]}',
        f'height = {_agent()["characters"]["player"]["height_m"]}', '',
        # sun + sky + ambient: mirrors Deli Counter's walk harness
        # (godot/addon/deli_counter/template/level_test.tscn) so a Lot site
        # walk lights identically to a DC building walk. Without this the
        # runtime scene renders unlit (the editor's preview sun hides it).
        '[sub_resource type="ProceduralSkyMaterial" id="Sky_mat"]', '',
        '[sub_resource type="Sky" id="Sky_res"]',
        'sky_material = SubResource("Sky_mat")', '',
        '[sub_resource type="Environment" id="Env_res"]',
        'background_mode = 2',
        'sky = SubResource("Sky_res")',
        'ambient_light_source = 3',
        'ambient_light_color = Color(0.6, 0.62, 0.68, 1)',
        'ambient_light_energy = 0.6',
        'tonemap_mode = 2', '',
        *ladder_subs,
        f'[node name="{site_spec["name"]}_walk" type="Node3D"]',
        'script = ExtResource("walk")',
        f'spawn_pos = {_v3(pos["spawn"], 1.0)}',
        f'objective_pos = {_v3(pos["objective"])}',
        f'extraction_pos = {_v3(pos["extraction"])}',
        f'site_title = "{site_spec["name"].upper()}"', '',
        '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]',
        'environment = SubResource("Env_res")', '',
        '[node name="Sun" type="DirectionalLight3D" parent="."]',
        'transform = Transform3D(0.707107, -0.5, 0.5, 0, 0.707107, 0.707107, '
        '-0.707107, -0.5, 0.5, 0, 20, 0)',
        'shadow_enabled = true', '',
        *ladder_body,
        *lt_body,
        '[node name="Nav" type="NavigationRegion3D" parent="."]',
        'navigation_mesh = SubResource("NavMesh")', '',
        '[node name="Site" parent="./Nav" instance=ExtResource("site")]', '',
        # Every body metric on this node comes from the contract. The capsule
        # already did; the step-up ceiling, the head-clearance height, the
        # collision offset and the eye height were literals, and lot_player.gd's
        # own default step height (0.45) had already drifted from the contract's
        # max_step_up_m (0.5). The collision shape sits half the body height up
        # because the node origin is at the FEET.
        '[node name="Player" type="CharacterBody3D" parent="."]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {player_godot})',
        'script = ExtResource("player")',
        f'max_step_height = {_player_metric("max_step_up_m", 0.5)}',
        f'body_height = {_player_metric("height_m", 1.8)}', '',
        '[node name="col" type="CollisionShape3D" parent="Player"]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, '
        f'{_player_metric("height_m", 1.8) / 2.0}, 0)',
        'shape = SubResource("PlayerCol")', '',
        '[node name="Camera" type="Camera3D" parent="Player"]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, '
        f'{_player_metric("eye_height_m", 1.6)}, 0)', '',
    ]
    with open(walk_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return pos


# ---------------------------------------------------------------------------
# nav-QA scene (--navqa): feed the Heist Nav QA addon the heist's real anchors
# (crew/objective/loot/extraction as player proxies, cover, cop spawns) on the
# composed + nav-baked site, so 16 bots stress-test it with zero hand-placement.
# ---------------------------------------------------------------------------
_PROXY_TYPES = ("crew_spawn", "attacker_spawn", "objective", "loot", "extraction")
_COVER_TYPES = ("cover_low", "cover_high")
_BOT_TYPES = ("responder_spawn", "horde_spawn", "defender_spawn")


def _pv3_array(world_pts, lift=0.0):
    """PackedVector3Array literal from site-space (x,y,z) points -> Godot."""
    nums = []
    for (x, y, z) in world_pts:
        nums += [f"{x:g}", f"{z + lift:g}", f"{-y:g}"]
    return "PackedVector3Array(" + ", ".join(nums) + ")"


def _floor_index(merged):
    """room id -> that room's floor elevation, from the merged gameplay file.

    Deli Counter writes one room record per room per storey, and `center[2]` is
    the storey's floor height (story -1/0/1 -> -4.0/0.0/4.0 for a 4 m storey).
    Read the elevation rather than multiplying `story` by an assumed height:
    the storey height is Deli Counter's to choose and it is not in this file."""
    idx = {}
    for r in merged.get("rooms", []):
        c = r.get("center")
        if r.get("id") and isinstance(c, (list, tuple)) and len(c) >= 3:
            idx[r["id"]] = float(c[2])
    return idx


def _floor_of(marker, floors, merged):
    """The elevation of the floor this marker stands on, or None.

    Markers name their room unnamespaced (`"vault"`); the merged room ids are
    namespaced by building (`"b0/vault"`). If the room is missing or unknown,
    fall back to the highest floor in the same building at or below the marker
    -- a marker is on the storey it sits above, never the one over its head."""
    bid = marker.get("building")
    room = marker.get("room")
    if bid and room:
        z = floors.get(f"{bid}/{room}")
        if z is not None:
            return z
    z_marker = float(marker.get("z", 0.0))
    below = [z for rid, z in floors.items()
             if (not bid or rid.startswith(f"{bid}/")) and z <= z_marker + 0.01]
    return max(below) if below else None


def _navqa_anchors(site_spec, merged):
    """The heist's own markers, as STANDING POSITIONS for the nav QA.

    A marker is where a thing IS. An anchor is where a body has to be able to
    stand to use it, and those are not the same point. Deli Counter puts
    OBJECTIVE_CAGE at the cashier counter, LOOT_VAULT_CASH on the vault block:
    marker heights of 0.9 and -2.8 sit ON the prop, and the floor directly
    under them is inside a solid box. Emitted at marker height, every one of
    them snapped to the prop's own tabletop -- a 1.0 m surface no body can
    climb to, which bakes as an isolated navmesh island. Sixteen of twenty-one
    anchors in the first honest walktest were standing on furniture, and the
    report read as a severed navmesh.

    So anchors are emitted at their room's FLOOR, keeping x/y. From there the
    nav QA looks for standing room on that storey plane and finds the floor
    beside the counter, which is where a player actually stands to use it."""
    markers = merged.get("markers", [])
    floors = _floor_index(merged)
    unresolved = []

    def pts(types):
        out = []
        for m in markers:
            if m.get("type") not in types:
                continue
            z = _floor_of(m, floors, merged)
            if z is None:
                unresolved.append(m.get("name", m.get("type", "?")))
                z = float(m.get("z", 0.0))
            out.append((m.get("x", 0.0), m.get("y", 0.0), z))
        return out

    proxies = pts(_PROXY_TYPES)
    bots = pts(_BOT_TYPES)
    for sm in merged.get("site_markers", []):
        t = sm.get("type")
        a = sm.get("at", [0.0, 0.0])
        if t in ("extraction", "crew_spawn"):
            proxies.append((a[0], a[1], 0.0))
        elif t in _BOT_TYPES:
            # cop pressure arrives from the STREET — road ends, alleys — which
            # is site geography, not any one building's spec.
            bots.append((a[0], a[1], 0.0))
    # Dropping markers onto their floor makes stacked markers coincide: Deli
    # Counter puts the vault objective and the vault loot at one XY, 0.2 m
    # apart in Z. Two anchors on one point are not two tests, and they hid a
    # stranded anchor once already -- it "reached" its own twin and passed.
    proxies, merged_pairs = _dedupe_anchors(proxies)
    bots, _ = _dedupe_anchors(bots)
    return {"player_proxies": proxies, "cover": pts(_COVER_TYPES),
            "bot_spawns": bots, "unresolved": unresolved,
            "merged_pairs": merged_pairs}


def _dedupe_anchors(points, tol=0.01):
    """Collapse anchors that land on the same point; return (kept, dropped)."""
    kept, seen = [], set()
    dropped = 0
    for p in points:
        key = tuple(round(v / tol) for v in p)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(p)
    return kept, dropped


def write_navqa_scene(site_spec, merged, navqa_out, site_tscn_base,
                      addon_dir="addons/lot", portable=False):
    """Emit <name>_navqa.tscn: the composed site under a baked NavigationRegion3D
    plus a NavQASetup node that tags the heist's anchors into the addon groups
    and runs the bot QA (if the Heist Nav QA addon is installed)."""
    anc = _navqa_anchors(site_spec, merged)
    _p = "" if portable else "res://"
    _a = "" if portable else addon_dir + "/"
    crew = _walk_positions(site_spec, merged)["spawn"]
    lines = [
        '[gd_scene load_steps=7 format=3]', '',
        f'[ext_resource type="PackedScene" path="{_p}{site_tscn_base}.tscn" id="site"]',
        f'[ext_resource type="Script" path="{_p}{_a}lot_navqa_setup.gd" id="setup"]', '',
        '[sub_resource type="NavigationMesh" id="NavMesh"]',
        'geometry_parsed_geometry_type = 2',
        # 0.15 m cells + 0.4 m agent: voxel erosion is per-cell, so coarser
        # bakes eat legal doorways and fragment interiors into islands
        f'cell_size = {_agent()["nav_bake"]["cell_size_m"]}',
        f'cell_height = {_agent()["nav_bake"]["cell_height_m"]}',
        f'agent_radius = {_agent()["nav_bake"]["agent_radius_m"]}',
        f'agent_height = {_agent()["nav_bake"]["agent_height_m"]}',
        # stairs bake as ~42 deg collision ramps; the default 45 deg slope
        # limit quantizes them into disjoint islands (same fix as nav_gate)
        f'agent_max_slope = {_agent()["nav_bake"]["agent_max_slope_deg"]}',
        f'agent_max_climb = {_agent()["nav_bake"]["agent_max_climb_m"]}', '',
        '[sub_resource type="ProceduralSkyMaterial" id="Sky_mat"]', '',
        '[sub_resource type="Sky" id="Sky_res"]',
        'sky_material = SubResource("Sky_mat")', '',
        '[sub_resource type="Environment" id="Env_res"]',
        'background_mode = 2',
        'sky = SubResource("Sky_res")',
        'ambient_light_source = 3',
        'ambient_light_color = Color(0.6, 0.62, 0.68, 1)',
        'ambient_light_energy = 0.6',
        'tonemap_mode = 2', '',
        f'[node name="{site_spec["name"]}_navqa" type="Node3D"]', '',
        '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]',
        'environment = SubResource("Env_res")', '',
        '[node name="Sun" type="DirectionalLight3D" parent="."]',
        'transform = Transform3D(0.707107, -0.5, 0.5, 0, 0.707107, 0.707107, '
        '-0.707107, -0.5, 0.5, 0, 20, 0)',
        'shadow_enabled = true', '',
        '[node name="Nav" type="NavigationRegion3D" parent="."]',
        'navigation_mesh = SubResource("NavMesh")', '',
        '[node name="Site" parent="./Nav" instance=ExtResource("site")]', '',
        '[node name="NavQASetup" type="Node3D" parent="."]',
        'script = ExtResource("setup")',
        # NO LIFT. _navqa_anchors already put these on their room's floor, which
        # is the only height a standing position can have. Two earlier versions
        # got this wrong in opposite directions: one added a metre to markers
        # that already carried body height, the other trusted the marker height
        # itself -- and a marker height is the height of the counter the loot is
        # lying on. crew_home keeps its lift: it comes from _walk_positions at
        # z 0, so it needs raising off the floor rather than lowering onto it.
        f'player_proxies = {_pv3_array(anc["player_proxies"])}',
        f'cover_points = {_pv3_array(anc["cover"])}',
        f'bot_spawns = {_pv3_array(anc["bot_spawns"])}',
        f'crew_home = {_v3(crew, 1.0)}', '',
    ]
    with open(navqa_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if anc.get("unresolved"):
        names = ", ".join(anc["unresolved"][:4])
        print(f"[lot] navqa: {len(anc['unresolved'])} marker(s) name no room this "
              f"site knows the floor of ({names}) -- emitted at marker height, "
              f"so the nav QA may snap them onto whatever they are sitting on")
    if anc.get("merged_pairs"):
        print(f"[lot] navqa: {anc['merged_pairs']} anchor(s) coincided once "
              f"dropped to their floor (stacked markers) and were merged")
    return {"player_proxies": len(anc["player_proxies"]),
            "cover": len(anc["cover"]), "bot_spawns": len(anc["bot_spawns"]),
            "unresolved": len(anc.get("unresolved", [])),
            "merged_pairs": anc.get("merged_pairs", 0)}


# ---------------------------------------------------------------------------
# top-level assemble
# ---------------------------------------------------------------------------
def assemble(site_spec_path, out_dir=None, walkable=False, navqa=False, preview=False):
    """Read a site spec, write <name>.site.gameplay.json and <name>.tscn."""
    base_dir = os.path.dirname(os.path.abspath(site_spec_path))
    out_dir = out_dir or base_dir
    os.makedirs(out_dir, exist_ok=True)
    with open(site_spec_path, encoding="utf-8") as f:
        site_spec = json.load(f)

    # preview: no .glb / no Blender. For each building, synthesize its gameplay
    # from its Deli Counter `spec` (the JSON new_level writes without Blender),
    # write it next to the spec so the merge reads it normally, and record the
    # footprint/height so the scene can box it.
    if preview:
        import preview as _preview
        for b in site_spec["buildings"]:
            spec_ref = b.get("spec")
            if not spec_ref:
                continue
            with open(os.path.join(base_dir, spec_ref), encoding="utf-8") as sf:
                bspec = json.load(sf)
            gp = _preview.gameplay_from_spec(bspec)
            # write a clearly-named preview file next to the spec; never clobber a
            # real .gameplay.json from a Blender build
            spec_dir = os.path.dirname(spec_ref)
            gp_name = os.path.join(spec_dir, f"{b['id']}.preview.gameplay.json")
            with open(os.path.join(base_dir, gp_name), "w", encoding="utf-8") as gf:
                json.dump(gp, gf, indent=2)
            b["gameplay"] = gp_name
            b.setdefault("footprint", _preview.footprint_of(bspec))
            b["_preview_height"] = _preview.height_of(bspec)

    # site-level tactical: gate first (raises if a declared mode's hard needs
    # aren't met — the site echo of Deli Counter's per-mode gates), then attach
    # the intel report (connectivity / approaches / distances — never fails).
    import site_tactical
    site_tactical.gate(site_spec)
    tactical_report = site_tactical.analyze(site_spec)

    merged = merge_gameplay(site_spec, base_dir)
    merged["tactical"] = tactical_report

    # Ground policy: a hole is cut under a building only where its geometry is
    # known to bring collision. A plain shell.glb brings none, and cutting
    # under it opens a void the site never fills -- which downstream reads as
    # NO_WORLD_COLLISION and zero evaluated runs, four steps and fifteen
    # minutes away from the cause. Decide here, before the gameplay file is
    # written, so the reason travels with the site.
    # How big the ground is and where it sits, decided from the content before
    # anything is placed against it. This runs ahead of the hole policy because
    # a hole is cut in a plate, and a plate in the wrong place turns the cut
    # into a clip nobody sees.
    import site_extent
    extent = site_extent.resolve(site_spec)
    if extent.rect:
        merged["ground_extent"] = {
            "rect": [round(v, 3) for v in extent.rect],
            "declared": [round(v, 3) for v in extent.declared] if extent.declared else None,
            "required": [round(v, 3) for v in extent.required] if extent.required else None,
            "extended": extent.extended,
        }
    for f_ in extent.findings:
        tactical_report.setdefault("findings", []).append(f_)
        print(f"[lot] {f_['code']}: {f_['message']}")

    import site_ground
    ground_reports = site_ground.audit(site_spec, [base_dir, out_dir])
    self_flooring = site_ground.self_flooring_ids(ground_reports)
    merged["ground"] = {bid: rep.as_dict() for bid, rep in
                        sorted(ground_reports.items())}
    ground_findings = site_ground.findings(ground_reports)
    # Every hole that will be cut, checked against the plate it is cut from.
    # `_ground_tiles` trims a hole to the plate as arithmetic; before the extent
    # was resolved from the content that trim was also the only record that a
    # building had fallen off the edge of the world, and it left none.
    ground_findings = list(ground_findings) + site_extent.hole_findings(
        extent.rect, ground_holes(site_spec, self_flooring))
    # ...and every shell checked against its neighbours. Nothing compared two
    # footprints to each other until now, so a row spaced narrower than the
    # buildings standing in it assembled interpenetrating shells and reported a
    # clean site.
    ground_findings += site_extent.overlap_findings(site_spec)
    tactical_report.setdefault("findings", []).extend(ground_findings)
    for f_ in ground_findings:
        print(f"[lot] {f_['code']}: {f_['message']}")

    # Where the enemies can stand, decided against the footprints and ground
    # rect above rather than by arithmetic on the route. Run here as well as in
    # write_walk_scene -- same inputs, same answer -- because the walk scene is
    # written after this report closes and a placement Lot could not honour has
    # to travel with the site, not sit silently in a .tscn nobody diffs.
    # What the shells are actually solid at. `site_ground` above answers "does
    # this building bring collision at all"; this answers "and where", which is
    # the question a nav hook standing inside a counter needs asked. Read once
    # and shared with the walk scene so the site report and the scene cannot
    # disagree about which prop was in the way.
    import site_collision
    solids = site_collision.read_site(site_spec, [base_dir, out_dir])
    merged["collision"] = {
        "colliders": len(solids.boxes),
        "complete": solids.complete,
        "unread": list(solids.unread),
        "detail": solids.detail,
    }

    import site_spawns
    raw_pos = _walk_positions(site_spec, merged)
    walk_pos, seat_findings = site_spawns.seat_destinations(
        raw_pos, solids=solids,
        bounds=_destination_bounds(merged, raw_pos))
    spawn_plan = site_spawns.place_enemies(site_spec, walk_pos)

    # Something to hide behind, before the scene is written.
    #
    # Moving an enemy is what Lot used to do about an unfair opening, and it
    # only ever traded one bad grade for another: the ground between the two
    # markers was still empty. Laser Tag is a soft gate -- it grades a map, it
    # never refuses one -- so its finding is answered by changing what gets
    # built rather than by blocking the build, and the thing to change is the
    # floor. `site_cover` decides where; the existing `cover` emitter in
    # `_outdoor_nodes` builds it, so the pieces land in the site scene, are
    # instanced under the walk scene's NavigationRegion3D, and are parsed by
    # the same bake that carves the buildings out. Cover the navmesh cannot see
    # is cover the bots walk into and stick on.
    import site_cover
    cover_points = {"LT_PlayerSpawn": tuple(walk_pos["spawn"][:2]),
                    "LT_ObjectivePoint": tuple(walk_pos["objective"][:2]),
                    "LT_ExtractionPoint": tuple(walk_pos["extraction"][:2])}
    for i, (ex, ey, _ez) in enumerate(spawn_plan.positions):
        cover_points[f"Enemy_{i}"] = (ex, ey)
    cover_plan = site_cover.plan_cover(
        cover_points,
        # The footprints as built. `plan_cover` measures sightlines against
        # these and adds a piece's own clearance itself -- passing pre-grown
        # rects makes a marker standing legally clear of a wall read as indoors
        # and silently deletes that building from the measurement.
        site_spawns.footprints(site_spec, margin=0.0),
        site_spawns.ground_rect(site_spec),
        opening_range=site_spawns.OPENING_RANGE,
        # The bake's own numbers, so the room a cover piece needs beside a wall
        # is derived from the agent contract rather than guessed.
        nav_bake=_agent().get("nav_bake"),
        # The crew's actual path, so cover can be placed on the ground it
        # crosses and not only between the markers at either end of it.
        route=[cover_points["LT_PlayerSpawn"],
               cover_points["LT_ObjectivePoint"],
               cover_points["LT_ExtractionPoint"]])
    site_spec.setdefault("cover", []).extend(
        c.as_site_cover() for c in cover_plan.cover)
    merged["cover_plan"] = {
        "placed": [c.as_dict() for c in cover_plan.cover],
        "still_open": [f"{a} -> {b} ({d:.1f} m)"
                       for a, b, _pa, _pb, d in cover_plan.open_lines],
        "unbreakable": [f"{a} -> {b} ({d:.1f} m)"
                        for a, b, _pa, _pb, d in cover_plan.unbreakable],
        "route_open": [f"{a} -> {b} ({d:.1f} m)"
                       for a, b, _pa, _pb, d in cover_plan.route_open],
        "pinches": [f"{n} vs {w} ({g:g} m)" for n, w, g in cover_plan.pinches],
    }

    cover_findings = site_cover.findings(
        cover_plan, opening_range=site_spawns.OPENING_RANGE)
    for f_ in seat_findings + spawn_plan.findings + cover_findings:
        tactical_report.setdefault("findings", []).append(f_)
        print(f"[lot] {f_['code']}: {f_['message']}")

    # pvp_heist post-merge gates: defender spawns live inside the buildings'
    # gameplay.json files, so they can only be validated after the merge.
    pvp_report = site_tactical.gate_merged(site_spec, merged)
    if pvp_report is not None:
        merged["pvp_heist"] = pvp_report

    # site enterability: can you actually REACH each building's entries once
    # they're placed? Gate the clear-cut walled-in case (needs merged openings +
    # footprints), then attach the per-building approach report.
    import site_enterability
    enter_report = site_enterability.gate(site_spec, merged)
    merged["enterability"] = enter_report

    # pacing estimate + structural encounter intel (both offline, structural,
    # never a fun-score). Pacing needs the merged markers (objective/loot counts).
    import site_pacing
    adj = site_tactical.build_graph(site_spec)
    merged["pacing"] = site_pacing.estimate_pacing(site_spec, merged)

    # site-level design grammar (report-only, like DC's combat_audit):
    # exfil shape, responder pressure, safe anchors, leg rhythm, crossings
    import site_audit
    print(site_audit.format_report(site_audit.audit(site_spec)))
    merged["encounters"] = site_pacing.encounter_intel(site_spec, adj)

    gp_out = os.path.join(out_dir, f"{site_spec['name']}.site.gameplay.json")
    with open(gp_out, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    # site-level lighting contract: every building's baked light anchors merged
    # to world space + namespaced, plus Lot's exterior streetlights. Lux's light
    # loader bakes this the same way it bakes a single building's .lights.json.
    lights_out = os.path.join(out_dir, f"{site_spec['name']}.site.lights.json")
    merged_lights = merge_lights(site_spec, base_dir)
    with open(lights_out, "w", encoding="utf-8") as f:
        json.dump(merged_lights, f, indent=2)
    print(f"[lot] site lights -> {lights_out} "
          f"({len(merged_lights['anchors'])} anchors)")

    tscn_out = os.path.join(out_dir, f"{site_spec['name']}.tscn")
    write_godot_scene(site_spec, merged, tscn_out, preview=preview,
                      self_flooring=self_flooring)

    # Site-level step gate, read back off the scene just WRITTEN rather than
    # re-derived from the constants that produced it. A capsule walks up a step
    # only while the contact normal stays inside floor_max_angle, which for the
    # contract player is clearances.unassisted_step_max_m -- and SIDEWALK_H is
    # 0.16, so a kerb away from a crossing is a wall to anything without
    # step-up code. Two codes: BLOCKS_A_ROUTE is major and fires when a designed
    # route crosses the rise; NEEDS_ASSIST is minor and fires off-route, which
    # is what a kerb correctly is. Never allowed to break a build -- but note
    # that a check which cannot fail is also a check that can go silent, so the
    # unavailable branch says so loudly.
    result_steps = []
    try:
        import site_steps as _steps
        _a = _agent()
        result_steps = _steps.findings(
            tscn_out,
            radius_m=float(_a["characters"]["player"]["radius_m"]),
            floor_max_angle_deg=45.0,
            assist_m=float(_a["characters"]["player"]["max_step_up_m"]),
            site_spec=site_spec)
        for _i in result_steps:
            # Column zero, and the prefix library_walk.py filters on. Its
            # forwarder does `if line.startswith("[lot]")` and adds the indent
            # itself, so a leading space here means the line is dropped -- which
            # silently hid this gate's first live run, findings and failures
            # alike.
            print(f"[lot] {_i['code']}: {_i['message']}")
        # This gate necessarily runs AFTER the gameplay contract was written,
        # because it reads back the .tscn emitted above. Fold its findings in and
        # rewrite, so <site>.site.gameplay.json carries EVERY finding with the
        # severity its emitter gave it. Anything downstream can then read one
        # file instead of re-deriving severity from printed text -- which is what
        # library_walk was doing, with a hardcoded lookup table that was already
        # missing a severity level the emitters use.
        if result_steps:
            tactical_report.setdefault("findings", []).extend(result_steps)
            with open(gp_out, "w", encoding="utf-8") as _gf:
                json.dump(merged, _gf, indent=2)
    except Exception as _e:
        print(f"[lot] STEP GATE DID NOT RUN ({type(_e).__name__}: {_e}) -- "
              f"a silent check is not a passing one")

    result = {
        "gameplay": gp_out, "scene": tscn_out, "lights": lights_out,
        "buildings": len(site_spec["buildings"]),
        "markers": len(merged["markers"]),
        "rooms": len(merged["rooms"]),
        "tactical": tactical_report,
        "steps": result_steps,
        "pacing": merged["pacing"],
    }

    if walkable:
        walk_out = os.path.join(out_dir, f"{site_spec['name']}_walk.tscn")
        result["walk_positions"] = write_walk_scene(
            site_spec, merged, walk_out, site_spec["name"], solids=solids)
        result["walk_scene"] = walk_out

    if navqa:
        navqa_out = os.path.join(out_dir, f"{site_spec['name']}_navqa.tscn")
        result["navqa_counts"] = write_navqa_scene(
            site_spec, merged, navqa_out, site_spec["name"])
        result["navqa_scene"] = navqa_out

    return result


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    walkable = "--walkable" in sys.argv
    navqa = "--navqa" in sys.argv
    preview = "--preview" in sys.argv
    if not args:
        print("usage: python lot.py <site_spec.json> [out_dir] "
              "[--walkable] [--navqa] [--preview]")
        raise SystemExit(2)
    out = args[1] if len(args) > 1 else None
    try:
        r = assemble(args[0], out, walkable=walkable, navqa=navqa, preview=preview)
    except Exception as e:
        # site_tactical.SiteTacticalError and friends: fail loudly, like a gate
        print(f"[lot] BUILD FAILED: {e}")
        raise SystemExit(1)
    print(f"[lot] assembled '{os.path.basename(args[0])}': "
          f"{r['buildings']} buildings, {r['markers']} markers, "
          f"{r['rooms']} rooms")
    t = r["tactical"]
    if t.get("mode"):
        print(f"[lot]   mode: {t['mode']} (gates passed)")
    iso = t["intel"].get("isolated_buildings")
    if iso:
        print(f"[lot]   WARNING: isolated buildings: {', '.join(iso)}")
    if "objective_approaches" in t["intel"]:
        print(f"[lot]   objective approaches: {t['intel']['objective_approaches']}")
    p = r.get("pacing", {})
    if p.get("mode"):
        print(f"[lot]   pacing: ~{p['estimate_expected_min']} min "
              f"(range {p['range_min']}, target {p['target_min']}) "
              f"-> {p['status']}")
    print(f"[lot]   -> {os.path.basename(r['gameplay'])}")
    print(f"[lot]   -> {os.path.basename(r['scene'])}")
    if r.get("walk_scene"):
        wp = r["walk_positions"]
        print(f"[lot]   -> {os.path.basename(r['walk_scene'])}  (walkable: "
              f"spawn {tuple(round(v,1) for v in wp['spawn'])} -> "
              f"objective {tuple(round(v,1) for v in wp['objective'])} -> "
              f"extraction {tuple(round(v,1) for v in wp['extraction'])})")
    if r.get("navqa_scene"):
        nc = r["navqa_counts"]
        print(f"[lot]   -> {os.path.basename(r['navqa_scene'])}  (nav-QA: "
              f"{nc['player_proxies']} player proxies, {nc['cover']} cover, "
              f"{nc['bot_spawns']} cop spawns -> needs the heist_nav_qa addon)")
