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
            "id": bid, "glb": b["glb"],
            "at": b["at"], "rot": b.get("rot", 0),
        }
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
    """Emit a .tscn that instances each building .glb at its placement, plus
    Phase-2 outdoor geometry (ground, paths, courtyards, perimeter, cover) as
    Godot primitive nodes. Buildings stay separate assets referenced by path."""
    res_ids = {}
    res_lines = []
    next_id = 1
    for b in site_spec["buildings"]:
        glb = b["glb"]
        if glb not in res_ids:
            rid = f"b{next_id}"
            res_ids[glb] = rid
            next_id += 1
            rel = os.path.join(glb_dir, glb).replace("\\", "/")
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
        rid = res_ids[b["glb"]]
        xform = _godot_transform(b["at"], b.get("rot", 0))
        lines.append(
            f'[node name="{b["id"]}" parent="." '
            f'instance=ExtResource("{rid}")]')
        lines.append(f'transform = Transform3D({xform})')
        lines.append('')
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# top-level assemble
# ---------------------------------------------------------------------------
def assemble(site_spec_path, out_dir=None):
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

    return {
        "gameplay": gp_out, "scene": tscn_out,
        "buildings": len(site_spec["buildings"]),
        "markers": len(merged["markers"]),
        "rooms": len(merged["rooms"]),
        "tactical": tactical_report,
        "pacing": merged["pacing"],
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python lot.py <site_spec.json> [out_dir]")
        raise SystemExit(2)
    out = sys.argv[2] if len(sys.argv) > 2 else None
    try:
        r = assemble(sys.argv[1], out)
    except Exception as e:
        # site_tactical.SiteTacticalError and friends: fail loudly, like a gate
        print(f"[lot] BUILD FAILED: {e}")
        raise SystemExit(1)
    print(f"[lot] assembled '{os.path.basename(sys.argv[1])}': "
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
