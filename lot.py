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

LOT_VERSION = "0.4.0"


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
        gp_path = os.path.join(base_dir, b["gameplay"])
        if not os.path.exists(gp_path):
            # a building with no gameplay.json still places fine; skip its data
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

PATH_THICK = 0.1
COURT_THICK = 0.12
GROUND_THICK = 0.5
WALL_THICK = 0.3
COVER = (1.0, 1.0, 1.0)


def _box_node(name, size, at_xyz):
    """(body_lines, subres_lines) for an axis-aligned StaticBody3D box with a
    BoxMesh + BoxShape3D, at Godot-frame (x, y_height, z)."""
    sx, sy, sz = size
    x, yh, z = at_xyz
    body = [
        f'[node name="{name}" type="StaticBody3D" parent="."]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {x:g}, {yh:g}, {z:g})',
        '',
        f'[node name="mesh" type="MeshInstance3D" parent="./{name}"]',
        f'mesh = SubResource("BoxMesh_{name}")',
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
    return body, sub


def _yaw_box_node(name, size, center_godot, yaw_deg):
    """Like _box_node but yaw'd about Godot-Y (for paths between buildings)."""
    sx, sy, sz = size
    x, yh, z = center_godot
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    xform = (f"{c:g}, 0, {s:g}, 0, 1, 0, {-s:g}, 0, {c:g}, {x:g}, {yh:g}, {z:g}")
    body = [
        f'[node name="{name}" type="StaticBody3D" parent="."]',
        f'transform = Transform3D({xform})',
        '',
        f'[node name="mesh" type="MeshInstance3D" parent="./{name}"]',
        f'mesh = SubResource("BoxMesh_{name}")',
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
    return body, sub


def _outdoor_nodes(site_spec):
    """(body_lines, subres_lines) for all Phase-2 outdoor geometry."""
    body, sub = [], []
    bld = {b["id"]: b for b in site_spec["buildings"]}

    g = site_spec.get("ground")
    if g:
        gx, gy = g["size_x"], g["size_y"]
        b, s = _box_node("Ground", (gx, GROUND_THICK, gy), (0, -GROUND_THICK / 2, 0))
        body += b
        sub += s

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
        bl, sr = _yaw_box_node(f"path_{i}", (length, PATH_THICK, w),
                               (cx, PATH_THICK / 2, -cy), -ang)
        body += bl
        sub += sr

    for i, cdef in enumerate(site_spec.get("courtyards", [])):
        cx, cy = cdef["at"]
        sx, sy = cdef.get("size_x", 10), cdef.get("size_y", 10)
        bl, sr = _box_node(f"courtyard_{i}", (sx, COURT_THICK, sy),
                           (cx, COURT_THICK / 2, -cy))
        body += bl
        sub += sr

    per = site_spec.get("perimeter")
    if per and g:
        h = per.get("height", 3.0)
        gx, gy = g["size_x"], g["size_y"]
        hx, hy = gx / 2, gy / 2
        for name, size, at_xyz in [
            ("perim_N", (gx, h, WALL_THICK), (0, h / 2, -hy)),
            ("perim_S", (gx, h, WALL_THICK), (0, h / 2, hy)),
            ("perim_E", (WALL_THICK, h, gy), (hx, h / 2, 0)),
            ("perim_W", (WALL_THICK, h, gy), (-hx, h / 2, 0)),
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

    return body, sub


def write_godot_scene(site_spec, merged, out_path, glb_dir="."):
    """Emit a .tscn that instances each building (a .tscn scene or a baked .glb)
    at its placement, plus Phase-2 outdoor geometry (ground, paths, courtyards,
    perimeter, cover) as Godot primitive nodes. Buildings stay separate assets
    referenced by path -- instancing a building .tscn lets a shared module edit
    propagate across every building in the site."""
    res_ids = {}
    res_lines = []
    next_id = 1
    for b in site_spec["buildings"]:
        src = _building_source(b)
        if src not in res_ids:
            rid = f"b{next_id}"
            res_ids[src] = rid
            next_id += 1
            rel = os.path.join(glb_dir, src).replace("\\", "/")
            rel = rel[2:] if rel.startswith("./") else rel
            res_lines.append(
                f'[ext_resource type="PackedScene" path="res://{rel}" id="{rid}"]')

    outdoor_body, outdoor_sub = _outdoor_nodes(site_spec)
    n_sub = sum(1 for ln in outdoor_sub if ln.startswith("[sub_resource"))
    load_steps = len(res_lines) + n_sub + 1

    lines = [f'[gd_scene load_steps={load_steps} format=3]', '']
    lines += res_lines + ['']
    lines += outdoor_sub
    lines += ['[node name="Site" type="Node3D"]', '']
    lines += outdoor_body
    for b in site_spec["buildings"]:
        rid = res_ids[_building_source(b)]
        xform = _godot_transform(b["at"], b.get("rot", 0))
        lines.append(
            f'[node name="{b["id"]}" parent="." '
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


def write_walk_scene(site_spec, merged, walk_out, site_tscn_base, addon_dir="addons/lot"):
    """Emit <name>_walk.tscn: instances the composed site under a baked
    NavigationRegion3D, spawns a first-person player at the crew start, and
    beacons the objective + extraction. Reuses godot/addons/lot scripts."""
    pos = _walk_positions(site_spec, merged)
    sx, sy, sz = pos["spawn"]
    player_godot = f"{sx:g}, {sz + 1.0:g}, {-sy:g}"   # eye/capsule lift

    lines = [
        '[gd_scene load_steps=6 format=3]', '',
        f'[ext_resource type="PackedScene" path="res://{site_tscn_base}.tscn" id="site"]',
        f'[ext_resource type="Script" path="res://{addon_dir}/lot_site_walk.gd" id="walk"]',
        f'[ext_resource type="Script" path="res://{addon_dir}/lot_player.gd" id="player"]', '',
        '[sub_resource type="NavigationMesh" id="NavMesh"]',
        'geometry_parsed_geometry_type = 2',
        'cell_size = 0.25',
        'agent_radius = 0.5',
        'agent_height = 1.8', '',
        '[sub_resource type="CapsuleShape3D" id="PlayerCol"]',
        'radius = 0.4',
        'height = 1.8', '',
        f'[node name="{site_spec["name"]}_walk" type="Node3D"]',
        'script = ExtResource("walk")',
        f'spawn_pos = {_v3(pos["spawn"], 1.0)}',
        f'objective_pos = {_v3(pos["objective"])}',
        f'extraction_pos = {_v3(pos["extraction"])}', '',
        '[node name="Nav" type="NavigationRegion3D" parent="."]',
        'navigation_mesh = SubResource("NavMesh")', '',
        '[node name="Site" parent="./Nav" instance=ExtResource("site")]', '',
        '[node name="Player" type="CharacterBody3D" parent="."]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {player_godot})',
        'script = ExtResource("player")', '',
        '[node name="col" type="CollisionShape3D" parent="Player"]',
        'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.9, 0)',
        'shape = SubResource("PlayerCol")', '',
        '[node name="Camera" type="Camera3D" parent="Player"]',
        'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.6, 0)', '',
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


def _navqa_anchors(site_spec, merged):
    markers = merged.get("markers", [])

    def pts(types):
        return [(m.get("x", 0.0), m.get("y", 0.0), m.get("z", 0.0))
                for m in markers if m.get("type") in types]

    proxies = pts(_PROXY_TYPES)
    for sm in merged.get("site_markers", []):
        if sm.get("type") == "extraction":
            a = sm.get("at", [0.0, 0.0])
            proxies.append((a[0], a[1], 0.0))
    return {"player_proxies": proxies, "cover": pts(_COVER_TYPES),
            "bot_spawns": pts(_BOT_TYPES)}


def write_navqa_scene(site_spec, merged, navqa_out, site_tscn_base, addon_dir="addons/lot"):
    """Emit <name>_navqa.tscn: the composed site under a baked NavigationRegion3D
    plus a NavQASetup node that tags the heist's anchors into the addon groups
    and runs the bot QA (if the Heist Nav QA addon is installed)."""
    anc = _navqa_anchors(site_spec, merged)
    crew = _walk_positions(site_spec, merged)["spawn"]
    lines = [
        '[gd_scene load_steps=4 format=3]', '',
        f'[ext_resource type="PackedScene" path="res://{site_tscn_base}.tscn" id="site"]',
        f'[ext_resource type="Script" path="res://{addon_dir}/lot_navqa_setup.gd" id="setup"]', '',
        '[sub_resource type="NavigationMesh" id="NavMesh"]',
        'geometry_parsed_geometry_type = 2',
        'cell_size = 0.25',
        'agent_radius = 0.5',
        'agent_height = 1.8', '',
        f'[node name="{site_spec["name"]}_navqa" type="Node3D"]', '',
        '[node name="Nav" type="NavigationRegion3D" parent="."]',
        'navigation_mesh = SubResource("NavMesh")', '',
        '[node name="Site" parent="./Nav" instance=ExtResource("site")]', '',
        '[node name="NavQASetup" type="Node3D" parent="."]',
        'script = ExtResource("setup")',
        f'player_proxies = {_pv3_array(anc["player_proxies"], 1.0)}',
        f'cover_points = {_pv3_array(anc["cover"])}',
        f'bot_spawns = {_pv3_array(anc["bot_spawns"], 1.0)}',
        f'crew_home = {_v3(crew, 1.0)}', '',
    ]
    with open(navqa_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return {"player_proxies": len(anc["player_proxies"]),
            "cover": len(anc["cover"]), "bot_spawns": len(anc["bot_spawns"])}


# ---------------------------------------------------------------------------
# top-level assemble
# ---------------------------------------------------------------------------
def assemble(site_spec_path, out_dir=None, walkable=False, navqa=False):
    """Read a site spec, write <name>.site.gameplay.json and <name>.tscn."""
    base_dir = os.path.dirname(os.path.abspath(site_spec_path))
    out_dir = out_dir or base_dir
    os.makedirs(out_dir, exist_ok=True)
    with open(site_spec_path, encoding="utf-8") as f:
        site_spec = json.load(f)

    # site-level tactical: gate first (raises if a declared mode's hard needs
    # aren't met — the site echo of Deli Counter's per-mode gates), then attach
    # the intel report (connectivity / approaches / distances — never fails).
    import site_tactical
    site_tactical.gate(site_spec)
    tactical_report = site_tactical.analyze(site_spec)

    merged = merge_gameplay(site_spec, base_dir)
    merged["tactical"] = tactical_report

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
    merged["encounters"] = site_pacing.encounter_intel(site_spec, adj)

    gp_out = os.path.join(out_dir, f"{site_spec['name']}.site.gameplay.json")
    with open(gp_out, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    tscn_out = os.path.join(out_dir, f"{site_spec['name']}.tscn")
    write_godot_scene(site_spec, merged, tscn_out)

    result = {
        "gameplay": gp_out, "scene": tscn_out,
        "buildings": len(site_spec["buildings"]),
        "markers": len(merged["markers"]),
        "rooms": len(merged["rooms"]),
        "tactical": tactical_report,
        "pacing": merged["pacing"],
    }

    if walkable:
        walk_out = os.path.join(out_dir, f"{site_spec['name']}_walk.tscn")
        result["walk_positions"] = write_walk_scene(
            site_spec, merged, walk_out, site_spec["name"])
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
    if not args:
        print("usage: python lot.py <site_spec.json> [out_dir] [--walkable] [--navqa]")
        raise SystemExit(2)
    out = args[1] if len(args) > 1 else None
    try:
        r = assemble(args[0], out, walkable=walkable, navqa=navqa)
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
