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

import hashlib
import json
import math
import os
import shutil


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


# Re-coupled to the release number at 0.49.0 (it had sat at 0.17.2 while the
# VERSION file reached 0.48.0, and version.py said 0.18.0 -- three answers to
# one question). Nothing imports this one, but a wrong constant is a lie at
# rest; version.py is the copy package.py stamps with.
LOT_VERSION = "0.49.0"


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
        "interactives": [],
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

        # interactives: the replicable state machines DC emits (one per
        # interactive fixture, docs/INTERACTIVES.md). Ids are already globally
        # unique ("<building>:if:<hash>") and are the network handle every
        # client, snapshot and saved game references -- so they are carried
        # VERBATIM (a concatenation, not a merge; namespacing them would break
        # the correlation with slots.json and the composed scene's
        # metadata/interactive_id). slot_ref stays building-local for the same
        # reason; the building tag says whose slots.json it names. Transforms
        # are offset to world space exactly like markers: Z-up yaw + translate.
        for item in gp.get("interactives", []):
            wi = dict(item)
            wi["building"] = bid
            tf = dict(wi.get("transform") or {})
            if tf.get("translation"):
                tr = tf["translation"]
                tf["translation"] = _place_point(tr[0], tr[1], tr[2], placement)
                if "rot_y" in tf:
                    tf["rot_y"] = (tf["rot_y"] + placement["rot"]) % 360
                wi["transform"] = tf
            site["interactives"].append(wi)

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
        # STAMPED FROM THE FILES BEING MERGED, not a literal (roadmap 95).
        # This was "1.0.0" written by hand while Deli Counter's lights.py
        # stamped 1.1.0 on every building manifest, and the anchors were
        # copied wholesale -- so the site file declared one contract and
        # satisfied a later one (`drop` on 28 of 28 ceiling anchors, a 1.1.0
        # field). Nothing read the envelope, which is why it drifted; the
        # `--art --unlit` handoff is documented as "a contract another
        # lighting system can read", and the version is the field that makes
        # that safe. Set below once the merged versions are known.
        "light_manifest_version": "1.0.0",
        "site": site_spec["name"],
        "space": ("Blender Z-up, meters; rot_y = degrees about up; "
                  "pos is the fixture location"),
        "rig_library": "lux",
        "anchors": [],
    }
    merged_versions = []
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
        # A file with no version predates the field and is 1.0.0 by
        # definition -- that was the only contract when the field was absent.
        merged_versions.append(str(lm.get("light_manifest_version") or "1.0.0"))
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
    # THE HIGHEST VERSION MERGED, because that is the contract the anchors
    # actually need: a 1.1.0 anchor carries fields a 1.0.0 reader does not
    # know, and an envelope claiming 1.0.0 over it promises a consumer more
    # than the file keeps. A site with no building manifests at all is Lot's
    # streetlights alone, which carry nothing past 1.0.0. The full set is
    # recorded beside it so a MIX is visible rather than averaged away.
    if merged_versions:
        site["light_manifest_version"] = max(merged_versions, key=_version_key)
    site["light_manifest_versions_merged"] = sorted(set(merged_versions))
    return site


def _version_key(v):
    """'1.1.0' -> (1, 1, 0), so 1.10.0 sorts above 1.9.0 and a stray suffix
    does not raise."""
    out = []
    for part in str(v).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


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
#: The site's greybox palette. Everything below except the two street colours
#: was emitting NO material at all: a generated spec produces ground, paths, a
#: perimeter and cover, and not one of those was a coloured caller.
#:
#: Value carries the read that matters outdoors -- can I stand here, or is this
#: in my way -- and the surfaces answering it are held 0.15 apart in relative
#: luminance:
#:
#:     road 0.131 < ground 0.317 < path 0.478 < DC wall 0.710 < perimeter 0.879
#:
#: Anything answering a DIFFERENT question is a marker carried by chroma
#: instead, which is the convention Deli Counter's palette already uses for
#: stairs, ladders, doorways and breaches. Value is one-dimensional: solving the
#: full co-read graph for the largest gap that satisfies every pair returns
#: 0.140, below the floor, so not every surface can have one. Spending it on the
#: walk/block question and marking the rest is a choice, and this is where it is
#: written down. `patch_lot_greybox_palette.py --palette` re-checks these
#: numbers and refuses to write them if they stop holding.
#:
#: The perimeter is bright rather than dark for a reason that is arithmetic
#: before it is taste: dark would have to clear road's 0.131 by 0.15, which is
#: below zero. Bright is also the better read -- a uniform chalky boundary is
#: never mistaken for floor.
ROAD_COLOR = (0.13, 0.13, 0.14)        # 0.131 -- asphalt
SIDEWALK_COLOR = (0.55, 0.55, 0.57)    # 0.551 -- concrete, raised curb
GROUND_COLOR = (0.30, 0.32, 0.34)      # 0.317 -- the plate everything is read against
PATH_COLOR = (0.53, 0.47, 0.40)        # 0.478 -- a walked surface; warm cast names it
COURT_COLOR = (0.48, 0.52, 0.55)       # 0.514 -- path's band, cool cast names it apart
PERIM_COLOR = (0.87, 0.88, 0.90)       # 0.879 -- the edge of the world: bright, flat, dead
COVER_COLOR = (0.18, 0.55, 0.22)       # 0.448 -- a MARKER: chroma finds it, value is free

#: Warm massing -- reads as a building you can't enter. MOVED from
#: (0.38, 0.34, 0.30): against the new plate that was 0.03 apart in luminance
#: and 0.09 in saturation, which is the flat-grey complaint in miniature. Same
#: intent, enough chroma to carry it.
BLOCKER_COLOR = (0.46, 0.28, 0.16)     # 0.310

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
# BLOCKER_COLOR moved up into the palette block above, where the numbers that
# constrain it are written down.


#: Largest edge a Lot-drawn VISUAL mesh may have, in metres (roadmap item 54).
#: Godot's GL Compatibility renderer budgets positional lights PER MESH
#: (`max_lights_per_object`, engine default 8), and the first honest per-mesh
#: census (2026-08-23, lot_demo_001's walk preview) put `path_0/mesh` -- one
#: 65 x 8 m BoxMesh -- under 58 lights, with `path_1` at 52 and `path_3` at
#: 44. Ground plates, paths, roads and perimeter walls are exactly the
#: room-spanning plates that item names, drawn by Lot instead of Zoo or Deli
#: Counter. Same law as zoo `core.arch.PLATE_TILE` and deli_counter
#: `floors.SLAB_TILE`; duplicated deliberately across repos (each is pure and
#: imports none of the others) and cross-named so the trio is findable if any
#: of them changes. COLLISION IS NOT TILED: the BoxShape3D stays one shape,
#: because a collider has no light budget and every height/step check reads
#: the shape, not the mesh.
MESH_TILE = 8.0


def _mesh_tiles(sx, sz, tile=MESH_TILE):
    """Cut an sx (local x) by sz (local z) mesh footprint into <=tile cells.

    Returns ``[(suffix, dx, dz, tx, tz)]`` -- child-node suffix, LOCAL offset
    from the body's origin, cell size. A footprint inside the tile on both
    axes is the single ``("", 0, 0, sx, sz)`` entry, so the emitted node is
    byte-identical to what these writers always produced -- every kerb, cover
    box and crossing is untouched. Equal division per axis (``ceil`` cells,
    never fixed strides), so there is no sliver cell at an edge -- item 41's
    fragmentation counter-pressure, answered rather than traded into.
    Interior cut lines snap to whole millimetres so abutting cells meet at
    the same coordinate.
    """
    eps = 1e-6
    nx = int((sx - eps) // tile) + 1 if sx > tile + eps else 1
    nz = int((sz - eps) // tile) + 1 if sz > tile + eps else 1
    if nx == 1 and nz == 1:
        return [("", 0.0, 0.0, sx, sz)]

    def edges(extent, n):
        lo = -extent / 2.0
        return ([lo] + [round(lo + extent * k / n, 3) for k in range(1, n)]
                + [lo + extent])

    xe, ze = edges(sx, nx), edges(sz, nz)
    out = []
    for j in range(nz):
        for i in range(nx):
            out.append((f"_t{j}_{i}",
                        round((xe[i] + xe[i + 1]) / 2.0, 6),
                        round((ze[j] + ze[j + 1]) / 2.0, 6),
                        round(xe[i + 1] - xe[i], 6),
                        round(ze[j + 1] - ze[j], 6)))
    return out


def _mesh_child_lines(name, size, color, skin=None):
    """The MeshInstance3D children and their BoxMesh sub_resources for one
    StaticBody3D, tiled to MESH_TILE. Shared by `_box_node` and
    `_yaw_box_node` so the law cannot drift between them. Children sit in the
    body's LOCAL frame, so the yaw'd writer needs no rotation math here --
    the parent's transform carries it."""
    sx, sy, sz = size
    body, sub = [], []
    for suffix, dx, dz, tx, tz in _mesh_tiles(sx, sz):
        body.append(f'[node name="mesh{suffix}" type="MeshInstance3D" '
                    f'parent="./{name}"]')
        if suffix:
            body.append('transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, '
                        f'{dx:g}, 0, {dz:g})')
        body.append(f'mesh = SubResource("BoxMesh_{name}{suffix}")')
        if color or skin:
            body.append(f'material_override = SubResource("Mat_{name}")')
        body.append('')
        sub += [
            f'[sub_resource type="BoxMesh" id="BoxMesh_{name}{suffix}"]',
            f'size = Vector3({tx:g}, {sy:g}, {tz:g})', '',
        ]
    return body, sub


def _box_node(name, size, at_xyz, color=None, skin=None):
    """(body_lines, subres_lines) for an axis-aligned StaticBody3D box with a
    BoxMesh + BoxShape3D, at Godot-frame (x, y_height, z). color: optional
    (r,g,b[,a]) -> a StandardMaterial3D override; skin: a `ground_skins`
    record, which wins over the colour. The VISUAL is tiled to
    MESH_TILE (see `_mesh_tiles`); the shape is one box, as it always was."""
    sx, sy, sz = size
    x, yh, z = at_xyz
    mesh_body, mesh_sub = _mesh_child_lines(name, size, color, skin)
    body = [
        f'[node name="{name}" type="StaticBody3D" parent="."]',
        f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {x:g}, {yh:g}, {z:g})',
        '',
    ]
    body += mesh_body
    body += [
        f'[node name="col" type="CollisionShape3D" parent="./{name}"]',
        f'shape = SubResource("BoxShape_{name}")',
        '',
    ]
    sub = list(mesh_sub) + [
        f'[sub_resource type="BoxShape3D" id="BoxShape_{name}"]',
        f'size = Vector3({sx:g}, {sy:g}, {sz:g})', '',
    ]
    sub += _mat_sub(name, color, skin)
    return body, sub


def _yaw_box_node(name, size, center_godot, yaw_deg, color=None, skin=None):
    """Like _box_node but yaw'd about Godot-Y (for paths/roads between buildings).
    color: optional (r,g,b[,a]) -> a StandardMaterial3D override. The VISUAL
    is tiled to MESH_TILE in the body's LOCAL frame -- the parent transform
    carries the yaw, so the tiles need no rotation math and a 65 m path
    becomes nine ~7 m meshes lying exactly where the one mesh lay."""
    sx, sy, sz = size
    x, yh, z = center_godot
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    xform = (f"{c:g}, 0, {s:g}, 0, 1, 0, {-s:g}, 0, {c:g}, {x:g}, {yh:g}, {z:g}")
    mesh_body, mesh_sub = _mesh_child_lines(name, size, color, skin)
    body = [
        f'[node name="{name}" type="StaticBody3D" parent="."]',
        f'transform = Transform3D({xform})',
        '',
    ]
    body += mesh_body
    body += [
        f'[node name="col" type="CollisionShape3D" parent="./{name}"]',
        f'shape = SubResource("BoxShape_{name}")',
        '',
    ]
    sub = list(mesh_sub) + [
        f'[sub_resource type="BoxShape3D" id="BoxShape_{name}"]',
        f'size = Vector3({sx:g}, {sy:g}, {sz:g})', '',
    ]
    sub += _mat_sub(name, color, skin)
    return body, sub


#: Where paint sits: on the road's top face, one surface tier up, so it
#: draws over the asphalt without a collider and without a z-fight.
MARKING_Y = ROAD_THICK + SURFACE_TIER / 2.0 + 0.001


def paint_offset(key: str) -> tuple:
    """A fixed (u, v, w) in [0, 1) for one marking's paint, from ``key``.

    WHY. Paint is projected in WORLD space (`_mat_sub`), so two bars a whole
    number of tiles apart wear the same scuffs whatever the tile size:
    measured on cold run 9044's `site.markings.json`, 5 of 210 bar pairs
    still matched after the road-paint pack went to an 8 m tile (Pixelcoat
    0.39.0), 4 of them exactly, every pair in a different crosswalk. Each
    marking already has its own material, so a per-marking offset costs
    nothing.

    WHICH COMPONENTS. Godot 4.7's generated shader (read from the binary's
    template) is `uv1_triplanar_pos = world * uv1_scale + uv1_offset`, then
    `*= (1, -1, 1)`, and a face whose normal is up samples `pos.xz`. So a
    flat marking's two texture axes are shifted by the offset's X and Z --
    its Y moves only the side faces -- and all three are set.

    DETERMINISTIC: SHA-1 of the key, not Python's `hash()`, which is salted
    per process and would re-roll the wear on every build."""
    d = hashlib.sha1(key.encode("utf-8")).digest()
    return tuple(int.from_bytes(d[i:i + 4], "big") / 4294967296.0 for i in (0, 4, 8))


def _yaw_quad_node(name, size, center_godot, yaw_deg, color, skin=None,
                   uv_offset=None):
    """(body_lines, subres_lines) for a flat painted rectangle: a Node3D
    carrying the tiled meshes `_mesh_child_lines` makes, one shared
    material, and NO body -- markings have no collision. ``size`` is
    (along, across) in the plan; the quad is `SURFACE_TIER` thick. With a
    `paint` skin the quad wears the pack, tinted by the marking's own
    colour, and the pack's cutout is where the paint has worn through;
    ``uv_offset`` (see `paint_offset`) shifts that pack's projection."""
    along, across = size
    x, yh, z = center_godot
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    xform = (f"{c:g}, 0, {s:g}, 0, 1, 0, {-s:g}, 0, {c:g}, {x:g}, {yh:g}, {z:g}")
    mesh_body, mesh_sub = _mesh_child_lines(name, (along, SURFACE_TIER, across), color, skin)
    body = [f'[node name="{name}" type="Node3D" parent="."]',
            f'transform = Transform3D({xform})', '']
    body += mesh_body
    return body, list(mesh_sub) + _mat_sub(name, color, skin, tint=color if skin else None,
                                           uv_offset=uv_offset)


def _mat_sub(name, color, skin=None, tint=None, uv_offset=None):
    """The one StandardMaterial3D a body's tiles share. `color` alone is the
    flat greybox read; with a `skin` (see `ground_skins`) the material carries
    the Pixelcoat maps, projected in WORLD space so a plate tiled into 8 m
    meshes and a path yawed to its buildings read as one continuous surface
    -- the same projection `zoo_worldskin.gd` gives the kit at import. The
    tile period is the pack's `meters_per_tile`, not a number chosen here."""
    if not color and not skin:
        return []
    lines = [f'[sub_resource type="StandardMaterial3D" id="Mat_{name}"]']
    if skin:
        rid = skin["id"]
        lines.append(f'albedo_texture = ExtResource("{rid}_albedo")')
        if skin.get("roughness"):
            lines.append(f'roughness_texture = ExtResource("{rid}_roughness")')
        if skin.get("normal"):
            lines.append('normal_enabled = true')
            lines.append(f'normal_texture = ExtResource("{rid}_normal")')
        if skin.get("nearest"):
            lines.append('texture_filter = 2')      # nearest, with mipmaps
        s = 1.0 / float(skin["meters_per_tile"])
        lines.append('uv1_triplanar = true')
        lines.append('uv1_world_triplanar = true')
        lines.append(f'uv1_scale = Vector3({s:g}, {s:g}, {s:g})')
        if uv_offset is not None:
            u, v, w = uv_offset
            lines.append(f'uv1_offset = Vector3({u:.6g}, {v:.6g}, {w:.6g})')
        if skin.get("alpha_mode") == "scissor":
            # the pack's alpha is a cutout: tested, never blended, so the
            # quad stays in the opaque pass and needs no sorting
            lines.append('transparency = 2')
            lines.append('alpha_scissor_threshold = 0.5')
        if tint:
            r, g, b = tint[:3]
            lines.append(f'albedo_color = Color({r:g}, {g:g}, {b:g}, 1)')
        lines.append('')
        return lines
    if len(color) == 3:
        color = color + (1.0,)
    r, g, b, a = color
    if a < 1.0:
        lines.append('transparency = 1')
    lines.append(f'albedo_color = Color({r:g}, {g:g}, {b:g}, {a:g})')
    lines.append('')
    return lines


CODE_GROUND_SKIN_MISSING = "LOT_GROUND_SKIN_MISSING"
CODE_SIGN_PACK_MISSING = "LOT_SIGN_PACK_MISSING"

#: A SHOP SIGN IS A BAND ACROSS ITS FRONTAGE, not a plaque on a wall. The
#: walker's reference frames (docs/SET_DRESSING_REFERENCES.md, the Call of
#: Duty forecourt): the store's name runs the full width of the storefront
#: above the glazing. So the band is sized from the facade it hangs on --
#: `SIGN_SPAN` of it, within these bounds -- and its face is six times as
#: wide as it is tall, which is the shape Pixelcoat renders a sign pack at.
SIGN_SPAN = 0.72          # of the facade's width
SIGN_MIN_W = 2.4
SIGN_MAX_W = 9.0
SIGN_ASPECT = 6.0         # width : height, matching the pack
SIGN_D = 0.22
SIGN_Z = 3.6              # the band's centre, above grade
SIGN_PROUD = 0.06         # how far its back sits off the facade
SIGNS_DIR = "signs"


def sign_size(facade_w: float):
    """(w, h) of the band on a facade ``facade_w`` wide."""
    w = max(SIGN_MIN_W, min(SIGN_MAX_W, facade_w * SIGN_SPAN))
    return w, w / SIGN_ASPECT

#: Outdoor families a site spec may skin, and the ext_resource id stem each
#: gets. The spec names a Pixelcoat PACK DIRECTORY per family
#: (`"ground_skins": {"ground": "<dir>", "path": "<dir>", "courtyard": "<dir>"}`);
#: which material kind a family wears is the caller's decision (Level Factory
#: maps ground -> asphalt, path -> sidewalk), because Lot does not know the
#: theme and does not read Pixelcoat's profiles -- only the pack it was handed.
SKIN_FAMILIES = ("ground", "path", "courtyard", "road", "sidewalk", "paint")


def ground_skins(site_spec):
    """Resolve the spec's `ground_skins` pack directories into skin records.

    Returns (skins, findings). A family whose pack cannot be read is REPORTED
    and left flat -- the plate ships in its greybox colour and the finding
    says why -- never silently skipped: an unskinned plate and a plate nobody
    asked to skin look identical from the walker's side, and the difference
    is the whole answer to "why is the ground grey".

    Measured need (roadmap 152, cold run 9014): the exterior ground was one
    untextured 0.52 grey, so the only detail outdoors was the clutter on it,
    and 2,708 pieces of clutter read as defects in a texture that was not
    there.
    """
    raw = site_spec.get("ground_skins") or {}
    skins, findings = {}, []
    for fam, pack_dir in raw.items():
        if fam not in SKIN_FAMILIES:
            findings.append((CODE_GROUND_SKIN_MISSING,
                             f"{fam!r} is not an outdoor family "
                             f"({', '.join(SKIN_FAMILIES)}); ignored"))
            continue
        pack_dir = str(pack_dir)
        packs = sorted(f for f in (os.listdir(pack_dir) if os.path.isdir(pack_dir) else [])
                       if f.endswith(".pack.json"))
        if not packs:
            findings.append((CODE_GROUND_SKIN_MISSING,
                             f"{fam}: no *.pack.json in {pack_dir}; the "
                             f"{fam} stays flat"))
            continue
        with open(os.path.join(pack_dir, packs[0]), encoding="utf-8") as fh:
            pk = json.load(fh)
        maps = pk.get("maps") or {}
        if not maps.get("albedo"):
            findings.append((CODE_GROUND_SKIN_MISSING,
                             f"{fam}: {packs[0]} names no albedo map; the "
                             f"{fam} stays flat"))
            continue
        mpt = float(pk.get("meters_per_tile") or 0.0)
        if mpt <= 0.0:
            findings.append((CODE_GROUND_SKIN_MISSING,
                             f"{fam}: {packs[0]} has no meters_per_tile; a "
                             f"period nobody chose would be invented, so the "
                             f"{fam} stays flat"))
            continue

        def _abs(fname):
            return os.path.abspath(os.path.join(pack_dir, fname)).replace("\\", "/")

        hints = pk.get("import_hints") or {}
        skins[fam] = {
            "id": f"skin_{fam}",
            "profile": pk.get("material_profile") or packs[0][:-len(".pack.json")],
            "albedo": _abs(maps["albedo"]),
            "roughness": _abs(maps["roughness"]) if maps.get("roughness") else None,
            "normal": _abs(maps["normal"]) if maps.get("normal") else None,
            "meters_per_tile": mpt,
            "nearest": hints.get("interpolation") == "nearest",
            # a cutout pack (road paint worn through to the road) asks for
            # alpha scissor; anything else is opaque
            "alpha_mode": (hints.get("transparency") or {}).get("alpha_mode"),
        }
    return skins, findings


SKINS_DIR = "skins"


def building_signs(site_spec):
    """(signs, findings): the sign pack each building wears, read the way a
    ground skin is (`ground_skins`) -- a pack DIRECTORY per building id,
    named by the spec, resolved here into the maps a material needs.

    The spec says `{"signs": {"b0": "<pack dir>", ...}}`. A building with
    no entry has no sign, which is the ordinary case for a warehouse or a
    blocker; a building whose pack cannot be READ is reported and left
    bare, never silently skipped -- a strip with no signs and a strip
    whose signs failed to load look identical from the sidewalk.
    """
    raw = site_spec.get("signs") or {}
    known = {b["id"] for b in site_spec.get("buildings", []) or []}
    signs, findings = {}, []
    for bid, pack_dir in sorted(raw.items()):
        if bid not in known:
            findings.append((CODE_SIGN_PACK_MISSING,
                             f"{bid!r} names a sign and is not a building on "
                             f"this site; ignored"))
            continue
        pack_dir = str(pack_dir)
        packs = sorted(f for f in (os.listdir(pack_dir) if os.path.isdir(pack_dir) else [])
                       if f.endswith(".pack.json"))
        if not packs:
            findings.append((CODE_SIGN_PACK_MISSING,
                             f"{bid}: no *.pack.json in {pack_dir}; the shop "
                             f"stands with no sign over its door"))
            continue
        with open(os.path.join(pack_dir, packs[0]), encoding="utf-8") as fh:
            pk = json.load(fh)
        maps = pk.get("maps") or {}
        if not maps.get("albedo"):
            findings.append((CODE_SIGN_PACK_MISSING,
                             f"{bid}: {packs[0]} names no albedo map; no sign"))
            continue

        def _abs(fname):
            return os.path.abspath(os.path.join(pack_dir, fname)).replace("\\", "/")

        hints = pk.get("import_hints") or {}
        signs[bid] = {
            "id": f"sign_{bid}",
            "profile": pk.get("material_profile") or packs[0][:-len(".pack.json")],
            "albedo": _abs(maps["albedo"]),
            "emissive": _abs(maps["emissive"]) if maps.get("emissive") else None,
            "nearest": hints.get("interpolation") == "nearest",
        }
    return signs, findings


def _sign_ext_lines(signs, out_dir, prefix):
    """One Texture2D ext_resource per sign map, the map COPIED beside the
    scene like a ground skin's -- Godot has no loader for a png outside the
    project, and everything that loads a Lot scene copies its siblings."""
    lines = []
    dest = os.path.join(out_dir, SIGNS_DIR)
    for bid in sorted(signs):
        sk = signs[bid]
        for m in ("albedo", "emissive"):
            src = sk.get(m)
            if not src:
                continue
            os.makedirs(dest, exist_ok=True)
            name = os.path.basename(src)
            target = os.path.join(dest, name)
            if not (os.path.exists(target) and _same_bytes(src, target)):
                shutil.copyfile(src, target)
            lines.append(f'[ext_resource type="Texture2D" '
                         f'path="{prefix}{SIGNS_DIR}/{name}" '
                         f'id="{sk["id"]}_{m}"]')
    return lines


def sign_placement(bdef, roads_list):
    """(x, y, yaw) for a building's sign: centred on the facade that faces
    the street, a hand proud of it, looking at the road.

    The facade is chosen by which of the footprint's four sides the nearest
    road lies off -- the side whose outward normal points most nearly at
    the road's closest point. A site with no roads hangs the sign on the
    side facing the plate's centre, which is where a lot's own frontage is.
    """
    import site_spawns
    rect = site_spawns.footprint_rect(bdef, 0.0)
    if not rect:
        return None
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    target = None
    best = None
    for road in roads_list or []:
        dx, dy = cx - road.a[0], cy - road.a[1]
        t = max(0.0, min(road.length, dx * road.along[0] + dy * road.along[1]))
        p = road.point(t)
        d = math.hypot(p[0] - cx, p[1] - cy)
        if best is None or d < best:
            best, target = d, p
    if target is None:
        target = (0.0, 0.0)
    vx, vy = target[0] - cx, target[1] - cy
    sides = (("S", 0.0, -1.0, (cx, y0), 270.0),
             ("N", 0.0, 1.0, (cx, y1), 90.0),
             ("W", -1.0, 0.0, (x0, cy), 180.0),
             ("E", 1.0, 0.0, (x1, cy), 0.0))
    _side, nx, ny, at, yaw = max(sides, key=lambda s: s[1] * vx + s[2] * vy)
    facade = (y1 - y0) if abs(nx) > abs(ny) else (x1 - x0)
    return (at[0] + nx * (SIGN_D / 2.0 + SIGN_PROUD),
            at[1] + ny * (SIGN_D / 2.0 + SIGN_PROUD), yaw, facade)


def sign_facing(yaw_plan: float) -> float:
    """The Godot rotation about Y, in degrees, that turns a sign cabinet's
    face along a facade whose outward normal lies at `yaw_plan` degrees
    counterclockwise from plan +x.

    THE DERIVATION, because a bare `- 90` here is how this went wrong twice
    already. `_sign_node` writes the text
    `Transform3D(c, 0, s, 0, 1, 0, -s, 0, c, ...)`, and Godot reads those
    nine numbers as the basis ROWS -- measured in Godot 4.7 with
    `str_to_var` on this writer's own text, not recalled. The lit face is a
    QuadMesh whose own normal is local +Z (also measured), carried to world
    `(s, 0, c)`: the third COLUMN. Plan maps to Godot as `(x, -y)`, so the
    face points plan `(sin r, -cos r)`, and an outward normal
    `(nx, ny) = (cos t, sin t)` wants `sin r = cos t` and `cos r = -sin t`:
    `r = t + 90` is the only angle satisfying both.

    Cold run 9041 shipped `r = -t`, a quarter turn off on every side, so the
    signs stood edge-on to their road. 0.69.2 then shipped `r = -(t + 90)`,
    derived by reading the numbers as COLUMNS: that equals `t + 90` modulo
    360 for a north or south facade and is its half turn for an east or
    west one, which put the lit face against the wall and the dark can
    toward the street. Its test read the numbers the same wrong way and
    passed. Both caught by measuring, neither by a gate.
    """
    return (yaw_plan + 90.0) % 360.0


#: How far the lit face stands off the cabinet's front. Two millimetres:
#: enough that no depth test can flip them, small enough that the face and
#: the body read as one object from the sidewalk.
SIGN_FACE_PROUD = 0.002
#: The cabinet body's colour. A sign box is a dark painted can and the
#: interesting surface is the face; a body wearing the pack was how the
#: pack came to be shown on six sides at once.
SIGN_BODY_RGBA = "0.12, 0.12, 0.13, 1"


def _sign_node(name, center_godot, yaw_deg, sign, size):
    """(body, subres) for a lit cabinet: a Node3D holding a BOX (the can) and
    a QUAD (the lit face) 2 mm proud of it. No collision -- nothing 3.6 m
    over a sidewalk needs it -- and no triplanar: a sign's face is its
    texture once across, not a tiled surface.

    WHY TWO MESHES. A BoxMesh does not map a texture 1:1 onto any of its
    sides: its unwrap's extents are proportional to the box's dimensions, so
    the face shows a sub-rectangle whose size depends on the other two axes.
    Measured on cold run 9042's frames -- a 9 x 1.5 x 0.22 cabinet showed
    about u in [0, 0.90] and v in [0, 0.62] of a centred 512 x 128 pack, and
    "KEYSTONE SAVINGS" was cut off below the letter tops. A QuadMesh spans
    the full 0..1 across its one face by construction. No `uv1_scale` could
    have fixed the box, because the correction would differ per sign size.
    """
    x, yh, z = center_godot
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    xform = (f"{c:g}, 0, {s:g}, 0, 1, 0, {-s:g}, 0, {c:g}, {x:g}, {yh:g}, {z:g}")
    face_z = SIGN_D / 2.0 + SIGN_FACE_PROUD
    body = [f'[node name="{name}" type="Node3D" parent="."]',
            f'transform = Transform3D({xform})', '',
            f'[node name="mesh" type="MeshInstance3D" parent="./{name}"]',
            f'mesh = SubResource("BoxMesh_{name}")',
            f'material_override = SubResource("Body_{name}")', '',
            f'[node name="face" type="MeshInstance3D" parent="./{name}"]',
            f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, '
            f'{face_z:g})',
            f'mesh = SubResource("Quad_{name}")',
            f'material_override = SubResource("Mat_{name}")', '']
    sw, sh = size
    sub = [f'[sub_resource type="BoxMesh" id="BoxMesh_{name}"]',
           f'size = Vector3({sw:g}, {sh:g}, {SIGN_D:g})', '',
           f'[sub_resource type="StandardMaterial3D" id="Body_{name}"]',
           f'albedo_color = Color({SIGN_BODY_RGBA})', '',
           f'[sub_resource type="QuadMesh" id="Quad_{name}"]',
           f'size = Vector2({sw:g}, {sh:g})', '',
           f'[sub_resource type="StandardMaterial3D" id="Mat_{name}"]',
           f'albedo_texture = ExtResource("{sign["id"]}_albedo")']
    if sign.get("emissive"):
        sub += ['emission_enabled = true',
                f'emission_texture = ExtResource("{sign["id"]}_emissive")',
                # 1.6 blew the face to white on cold run 9040's frames -- a
                # band that cannot be read is a band nobody put a name on.
                # A lit cabinet is brighter than its wall and no brighter.
                'emission_energy_multiplier = 0.65']
    if sign.get("nearest"):
        sub.append('texture_filter = 2')
    sub += ['cull_mode = 2', '']          # a cabinet reads from both sides
    return body, sub


def _skin_ext_lines(skins, out_dir, prefix):
    """One Texture2D ext_resource per map, the map COPIED to `<out_dir>/skins/`
    and referenced beside the scene the way a staged building is
    (`skins/<file>` in portable mode, `res://skins/<file>` otherwise).

    0.57.0 wrote the pack's absolute path and copied nothing, on the theory
    that a consumer bundles what a scene references. Level Factory's export
    does; Godot does not: a `.png` outside the project has no importer, so
    the scene's first loader -- the Lux stage, which stages the scene into a
    throwaway project -- failed to parse it ("No loader found for resource
    ... expected type: Texture2D"), the stage exited 2, and cold run 9015
    shipped a package with no lighting at all. Everything that loads a Lot
    scene copies the scene's siblings (Lux's staging does, the export does
    for `lot/`), so the maps live as siblings.
    """
    lines = []
    dest = os.path.join(out_dir, SKINS_DIR)
    for fam in SKIN_FAMILIES:
        sk = skins.get(fam)
        if not sk:
            continue
        for m in ("albedo", "roughness", "normal"):
            src = sk.get(m)
            if not src:
                continue
            os.makedirs(dest, exist_ok=True)
            name = os.path.basename(src)
            target = os.path.join(dest, name)
            if not (os.path.exists(target) and _same_bytes(src, target)):
                shutil.copyfile(src, target)
            lines.append(f'[ext_resource type="Texture2D" '
                         f'path="{prefix}{SKINS_DIR}/{name}" '
                         f'id="{sk["id"]}_{m}"]')
    return lines


def _same_bytes(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# the site's slot manifest: its cover pieces as prop slots Zoo can build to
# (roadmap 22 -- outdoor props had no swap contract, so cover stayed boxes)
# ---------------------------------------------------------------------------

CODE_COVER_MODULE_MISSING = "LOT_COVER_MODULE_MISSING"
CODE_COVER_MODULE_FAILED = "LOT_COVER_MODULE_FAILED"


def _kit_index(module_dir: str) -> dict:
    """stem -> row of the Zoo kit index in ``module_dir`` (`*_kit.built.json`),
    or {} when there is none -- then every module that exists is stood, as
    before the index was read."""
    out = {}
    try:
        names = [n for n in os.listdir(module_dir) if n.endswith("_kit.built.json")]
    except OSError:
        return out
    for n in sorted(names):
        try:
            with open(os.path.join(module_dir, n), encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            continue
        for row in doc.get("modules", []) or []:
            if row.get("stem"):
                out[row["stem"]] = row
    return out


def cover_module_stem(species: str, theme: str, style: int,
                      dims) -> str:
    """The file Zoo builds for a prop slot with a species hint, by NAME.

    THE THIRD COPY OF ONE RULE. `deli_counter/themed_tscn.module_stem` and
    `zoo_keeper/core/kit.module_stem` construct this same name from the same
    slot, and neither parses; they agree by being kept identical and each
    pins the other with literals (`test_themed_stem`, Zoo's
    `test_openings`). This mirror is pinned the same way in
    `tests/test_site_cover_slots.py`, and it exists because Lot resolves the
    site's cover the way Deli Counter resolves a building's props: a prop
    slot with dims (w, d, h) in centimetres and a species becomes
    `prop_<species>_<theme>_<style:02d>_w<w>_d<d>_h<h>`.
    """
    w, d, h = (int(round(float(v) * 100)) for v in dims)
    return f"prop_{species}_{theme}_{int(style):02d}_w{w}_d{d}_h{h}"


def write_site_slots(site_spec, out_path):
    """The site's `<name>.slots.json`: one prop slot per species cover piece,
    in Deli Counter's slot-manifest shape (`slot_manifest_version` 1.2.0),
    so the SAME Zoo kit build that dresses a building dresses the street.

    Only species pieces are slots; a square 0.58-form piece has no species
    and stays the box it was. A piece's own ``style`` (a parked car's,
    `site_parking.car_for_bay`) is the slot's; a piece with none is style 1,
    as every slot was until 0.70.0. Zoo's `plan_kit` reads the slot's style
    into the stem, so two styles of one shape are two modules. Returns the
    number of slots written."""
    slots = []
    for i, cv in enumerate(site_spec.get("cover", []) or []):
        sp = cv.get("species")
        dims = cv.get("dims")
        if not sp or not dims or len(dims) < 3:
            continue
        cx, cy = cv["at"]
        base = SIDEWALK_H if cv.get("base") == "sidewalk" else 0.0
        slots.append({
            "slot_id": f"cover_{i}", "role": "prop", "size_mod": "full",
            "style": int(cv.get("style") or 1),
            "material": COVER_MATERIALS.get(sp, "metal_painted"),
            "current_ref": "prop_greybox_01", "kit_axis": "theme",
            "species": sp,
            "transform": {"translation": [round(cx, 4), round(cy, 4),
                                          round(base + float(dims[2]) / 2.0, 4)],
                          "rot_y": float(cv.get("yaw") or 0.0),
                          "scale": [1.0, 1.0, 1.0]},
            "fit": {"dims": [float(dims[0]), float(dims[1]), float(dims[2])],
                    "pivot": "center", "openings": [], "collision": "convex"},
            "breaks": cv.get("breaks", ""),
        })
    doc = {
        "slot_manifest_version": "1.2.0",
        "building_id": "site",
        "theme": "greybox",
        "module_library": "art/zoo",
        "module_size": 2.0,
        "space": "spec/Blender Z-up raw coords; rot_y = degrees about up",
        "coverage": {"prop/site_cover": len(slots)},
        "slots": slots,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return len(slots)


#: The material a cover species is built in, as Deli Counter names one on a
#: prop slot (the Zoo genome's default). Named here so the slot Lot writes
#: says what Zoo will read, rather than leaving the field empty.
COVER_MATERIALS = {"box_truck": "metal_painted", "cargo_container": "metal_painted",
                   "simple_car": "metal_painted",
                   # the kerb line (site_furniture)
                   "streetlight": "metal", "fire_hydrant": "metal_painted",
                   "litter_bin": "metal_painted", "sign_post": "metal_bare",
                   # the waiting places (site_furniture)
                   "bus_shelter": "metal_painted", "bench": "wood",
                   # the five street trees and the generic one
                   "street_tree": "wood", "red_maple": "wood",
                   "pin_oak": "wood", "honey_locust": "wood",
                   "london_plane": "wood", "callery_pear": "wood",
                   # the 1990s street kit (site_furniture)
                   "stop_sign": "metal_bare", "traffic_signal": "metal_painted",
                   "mailbox": "metal_painted", "newspaper_box": "metal_painted",
                   "parking_meter": "metal_painted", "payphone": "metal_painted"}


COVER_DIR = "cover"


def cover_module_refs(site_spec, prefix, out_dir=None):
    """Which cover pieces have a built module to stand in for the box.

    The spec's ``cover_modules`` names the Zoo kit build's directory, theme
    and style; each species piece resolves to `<dir>/<stem>.glb` by
    `cover_module_stem`. Returns (refs, ext_lines, findings): ``refs`` maps a
    cover INDEX to its ext_resource id, ``ext_lines`` declare the GLBs, and
    each piece whose module is not there is a `LOT_COVER_MODULE_MISSING`
    finding with the stem it looked for -- the box stays, the art pass is
    progressive, and nothing is quiet about it.

    The modules are COPIED to `<out_dir>/cover/` and referenced as siblings
    of the scene (`cover/<stem>.glb`, or `res://cover/...` off portable
    mode), exactly as the ground's skins are. 0.59.0 referenced them by
    absolute path; cold run 9019 showed what that costs one stage on: the
    Lux stage stages the scene into a throwaway project, Godot has no
    loader for a glb outside it ("No loader found for resource"), and the
    applied scene the package ships came back with every cover node gone
    -- three modules built, three boxes replaced, nothing in the level.
    Every stage that loads a Lot scene copies its siblings.
    """
    cm = site_spec.get("cover_modules") or {}
    refs, ext, findings = {}, [], []
    if not cm.get("dir"):
        return refs, ext, findings
    theme, style = str(cm.get("theme", "")), int(cm.get("style", 1))
    if not theme:
        findings.append((CODE_COVER_MODULE_MISSING,
                         "cover_modules names no theme; every piece stays a box"))
        return refs, ext, findings
    index = _kit_index(str(cm["dir"]))
    seen = {}
    for i, cv in enumerate(site_spec.get("cover", []) or []):
        sp, dims = cv.get("species"), cv.get("dims")
        if not sp or not dims:
            continue
        # The piece's own style when it carries one, as `write_site_slots`
        # wrote it on the slot Zoo built from; the site's style otherwise.
        # At the site's one style a style-2 car would ask for the style-1
        # file, which is another car or no file at all.
        stem = cover_module_stem(sp, theme, int(cv.get("style") or style), dims)
        glb = os.path.abspath(os.path.join(str(cm["dir"]), stem + ".glb")).replace("\\", "/")
        if not os.path.isfile(glb):
            findings.append((CODE_COVER_MODULE_MISSING,
                             f"cover_{i} ({sp}): no {stem}.glb in {cm['dir']}; "
                             f"the box stays"))
            continue
        # THE INDEX'S VERDICT, READ. Zoo writes `site_kit.built.json` beside
        # the modules with a `status` per row; a module that failed exact
        # fit (cold run 9024: the lamp 6.18 m against 6.00, the car 4.36
        # against 4.30) was stood anyway because this resolved by file. A
        # failed module keeps its box, and says which check it failed. A
        # `warn` row is a built module with an advisory against it (a tri
        # budget, a dim range Zoo marks advisory under exact fit) and
        # stands; only `fail` -- or a status nobody named -- keeps the box.
        verdict = index.get(stem)
        if verdict is not None and verdict.get("status") not in ("pass", "warn"):
            findings.append((CODE_COVER_MODULE_FAILED,
                             f"cover_{i} ({sp}): {stem} built with status "
                             f"{verdict.get('status')!r}; the box stays"))
            continue
        if stem not in seen:
            seen[stem] = f"cover_{stem}"
            ref_path = glb
            if out_dir:
                dest = os.path.join(out_dir, COVER_DIR)
                os.makedirs(dest, exist_ok=True)
                target = os.path.join(dest, stem + ".glb")
                if not (os.path.exists(target) and _same_bytes(glb, target)):
                    shutil.copyfile(glb, target)
                ref_path = f"{prefix}{COVER_DIR}/{stem}.glb"
            ext.append(f'[ext_resource type="PackedScene" path="{ref_path}" '
                       f'id="{seen[stem]}"]')
        refs[i] = seen[stem]
    return refs, ext, findings


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


def _outdoor_nodes(site_spec, preview=False, self_flooring=None, skins=None,
                   cover_refs=None, signs=None):
    """(body_lines, subres_lines) for all Phase-2 outdoor geometry.

    `self_flooring` is the set of building ids whose geometry demonstrably
    brings collision (see site_ground.audit). Only those get a hole cut in the
    ground beneath them. Passing None means nothing has been checked, so no
    holes are cut -- an unchecked assumption must not be able to open a void.

    `skins` is `ground_skins(site_spec)[0]`: per outdoor family, the
    Pixelcoat maps its material wears. Absent, every family keeps its flat
    greybox colour, byte for byte.
    """
    body, sub = [], []
    skins = skins or {}
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
                                -(y0 + y1) / 2),
                               GROUND_COLOR, skin=skins.get("ground"))
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
                               (cx, (PATH_THICK - GROUND_SINK) / 2, -cy), -ang,
                               PATH_COLOR, skin=skins.get("path"))
        body += bl
        sub += sr

    for i, cdef in enumerate(site_spec.get("courtyards", [])):
        cx, cy = cdef["at"]
        sx, sy = cdef.get("size_x", 10), cdef.get("size_y", 10)
        bl, sr = _box_node(f"courtyard_{i}",
                           (sx, COURT_THICK + GROUND_SINK, sy),
                           (cx, (COURT_THICK - GROUND_SINK) / 2, -cy),
                           COURT_COLOR, skin=skins.get("courtyard"))
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
            bl, sr = _box_node(name, size, at_xyz, PERIM_COLOR)
            body += bl
            sub += sr

    cover_refs = cover_refs or {}
    for i, cv in enumerate(site_spec.get("cover", [])):
        cx, cy = cv["at"]
        sx, sy, sz = cv.get("size", COVER)
        # Where the piece's underside sits: the plate, or the top of a
        # sidewalk band for kerb-line furniture (roadmap 153).
        base = SIDEWALK_H if cv.get("base") == "sidewalk" else 0.0
        if i in cover_refs:
            # The module Zoo built for this slot, standing where the box
            # stood: same centre, same yaw, its own collision (roadmap 22).
            # The module is centre-pivot at the slot's dims, so its origin
            # is the box's centre.
            xform = _godot_transform((cx, cy), float(cv.get("yaw") or 0.0),
                                     z=base + sy / 2)
            body += [f'[node name="cover_{i}" parent="." '
                     f'instance=ExtResource("{cover_refs[i]}")]',
                     f'transform = Transform3D({xform})', '']
            continue
        bl, sr = _box_node(f"cover_{i}", (sx, sy, sz), (cx, base + sy / 2, -cy),
                           COVER_COLOR)
        body += bl
        sub += sr

    # roads: the street grid the block is built on (DELCO/Philly grain). A road
    # is a flat asphalt strip between two points, optionally with raised concrete
    # sidewalks running alongside. Buildings + blockers front onto it.
    # THE STREET, from its model (site_streets, roadmap 153): the strip, a
    # sidewalk band each side split at the crossings, and the paint. A kerb
    # is SUPPOSED to be a wall -- 0.16 m against an unassisted step limit of
    # 0.117 -- and the answer is not to flatten it but to drop it where
    # people are meant to cross, exactly as a real street does. Anything the
    # model does not cut is still a wall, and site_steps.py says so rather
    # than leaving it to be discovered in play.
    import site_streets
    street_findings = []
    street_roads = site_streets.roads(site_spec, street_findings)
    for f_ in street_findings:
        print(f"[lot] {f_}")
    for road in street_roads:
        i, w, ang = road.index, road.width, road.angle_deg
        # the slab: the whole road, or from the far edge of the band of a
        # road it ends on (`site_streets._slab`) -- two slabs lying
        # coplanar over a junction's mouth would z-fight, and the other
        # road's dropped kerb is that mouth's surface
        # ... and less the boxes a lower-index road owns where it crosses
        # through (an X): the slab and the band pieces stop at the box's
        # edges and resume past them (`site_streets.drawn_spans`).
        spans = site_streets.drawn_spans(road)
        for k, (s0, s1) in enumerate(spans):
            cx, cy = road.point((s0 + s1) / 2.0)
            nm = f"road_{i}" if len(spans) == 1 else f"road_{i}_{k}"
            bl, sr = _yaw_box_node(nm, (s1 - s0, ROAD_THICK + GROUND_SINK, w),
                                   (cx, (ROAD_THICK - GROUND_SINK) / 2, -cy),
                                   -ang, ROAD_COLOR, skin=skins.get("road"))
            body += bl
            sub += sr
        for kerb in road.kerbs:
            pieces = [(t0, t1, is_cut, j) for j, (t0, t1, is_cut) in enumerate(kerb.spans)]
            for t0, t1, is_cut, j in pieces:
                t0, t1 = max(t0, road.slab[0]), min(t1, road.slab[1])
                parts = site_streets._outside(t0, t1, road.gaps) if t1 > t0 else []
                for kk, (p0, p1) in enumerate(parts):
                    seg = p1 - p0
                    if seg <= 0.05:
                        continue
                    scx, scy = road.point((p0 + p1) / 2.0, kerb.offset)
                    h = ROAD_THICK if is_cut else SIDEWALK_H
                    tag = f"{j}" if len(parts) == 1 else f"{j}_{kk}"
                    nm = (f"kerbcut_{i}{kerb.side}_{tag}" if is_cut
                          else f"sidewalk_{i}{kerb.side}_{tag}")
                    bl, sr = _yaw_box_node(
                        nm, (seg, h, road.sidewalk), (scx, h / 2, -scy), -ang,
                        SIDEWALK_COLOR,
                        skin=skins.get("road" if is_cut else "sidewalk"))
                    body += bl
                    sub += sr
    # THE PAINT. Flat quads a hair above the road, tiled like every other
    # surface and with NO collision -- a marking is not a thing a body meets.
    # The quad is the decal's shape and place; with a `paint` skin (a
    # Pixelcoat road-paint pack, cutout where the paint has worn through)
    # it is the decal layer of item 152, and without one it is the
    # greybox's flat read.
    # Each marking's paint is offset by a hash of what the marking IS --
    # its road, kind and plan position -- rather than its index, so a
    # marking added elsewhere on the site does not re-roll every other
    # marking's wear (`paint_offset`).
    for n, m in enumerate(site_streets.markings(street_roads)):
        along, across = m["size"]
        paint = skins.get("paint")
        offset = (paint_offset(f"{m['road']}|{m['kind']}|{m['at'][0]:.3f}|{m['at'][1]:.3f}")
                  if paint else None)
        bl, sr = _yaw_quad_node(f"mark_{n}_{m['kind']}", (along, across),
                                (m["at"][0], MARKING_Y, -m["at"][1]),
                                -m["yaw"], tuple(m["color"]), skin=paint,
                                uv_offset=offset)
        body += bl
        sub += sr

    # THE SHOP SIGNS. A lit cabinet over each door, on the facade that
    # faces the street (`sign_placement`), drawn here rather than as a
    # prop slot because it hangs on a wall: it has no footprint on the
    # ground, no collision, and nothing for the navmesh to carve.
    # resolved by the caller when there is one (`write_godot_scene`), and
    # read here when a probe calls this writer directly
    if signs is None:
        signs, _sign_findings = building_signs(site_spec)
    for b in site_spec.get("buildings", []) or []:
        sign = signs.get(b["id"])
        if not sign:
            continue
        spot = sign_placement(b, street_roads)
        if spot is None:
            continue
        sx, sy, yaw, facade = spot
        bl, sr = _sign_node(f"sign_{b['id']}", (sx, SIGN_Z, -sy),
                            sign_facing(yaw), sign, sign_size(facade))
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

    # Outdoor skins: the spec names a Pixelcoat pack per family, and a pack
    # that cannot be read is said out loud and left flat (roadmap 152).
    skins, skin_findings = ground_skins(site_spec)
    for code, msg in skin_findings:
        print(f"[lot] {code}: {msg}")
    # Declare only the maps a body will reference: a spec with no courtyard
    # gets no courtyard textures in its header.
    present = {"ground": bool(site_spec.get("ground")),
               "path": bool(site_spec.get("paths")),
               "courtyard": bool(site_spec.get("courtyards")),
               "road": bool(site_spec.get("roads")),
               "sidewalk": any(r.get("sidewalk") for r in site_spec.get("roads") or []),
               # the markings' paint: wherever there is a road to paint.
               # Cold run 9028 named the pack and shipped flat markings,
               # because this table did not know the family and the
               # filter below dropped it in silence.
               "paint": bool(site_spec.get("roads"))}
    skins = {fam: sk for fam, sk in skins.items() if present.get(fam)}
    res_lines += _skin_ext_lines(skins, os.path.dirname(os.path.abspath(out_path)),
                                 prefix)
    # THE SHOP SIGNS (roadmap 153): one pack per building, hung on the
    # facade that faces the street.
    signs, sign_findings = building_signs(site_spec)
    for code, msg in sign_findings:
        print(f"[lot] {code}: {msg}")
    res_lines += _sign_ext_lines(signs, os.path.dirname(os.path.abspath(out_path)),
                                 prefix)
    # Cover modules (roadmap 22): the pieces Zoo built stand in for their
    # boxes; a piece with no module keeps its box and says so.
    cover_refs, cover_ext, cover_findings = cover_module_refs(
        site_spec, prefix, os.path.dirname(os.path.abspath(out_path)))
    for code, msg in cover_findings:
        print(f"[lot] {code}: {msg}")
    res_lines += cover_ext

    outdoor_body, outdoor_sub = _outdoor_nodes(
        site_spec, preview=preview, self_flooring=self_flooring, skins=skins,
        cover_refs=cover_refs, signs=signs)

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


def _lasertag_hook_plan(pos, site_spec=None, enemy_count=6, lateral=1.5,
                        solids=None, bounds=None, enemies=None) -> dict:
    """The positions the walk scene will be written from, before it is written.

    `_lasertag_hook_nodes` does not place anything where its caller pointed. It
    seats the nav hooks onto floor, clears the crew spawn off the wall it is
    standing against, and only then spreads the enemies along the route those
    two steps produced. That is correct and stays. What was wrong is that it
    returned only the scene body, so the one question worth asking of it --
    "are the positions in the scene the positions that were planned" -- could
    be asked only by re-running the derivation by hand.

    `tests/test_site_spawns.py` did exactly that and drifted. It planned from
    the RAW route dict, and on `BAIE_DORE`, whose crew spawn sits at the dead
    centre of a 44 x 44 shell, `clear_crew_spawn` moves the spawn 23.5 m and
    every enemy spread along the route with it -- 19.242 planned against 37.735
    written on the first pair, all six disagreeing. Read as the scene losing
    the plan, filed as roadmap 48's family. The scene carried its own plan to
    0 of 18 failing pairs at `abs_tol=1e-3`; the plan the test held was of a
    route this tool never uses.

    Returning the resolved values is what stops that recurring: a caller
    checking the scene against the plan asks which plan was used instead of
    reproducing how it was derived, so a THIRD preprocessing step added here
    cannot silently desync anybody.
    """
    import site_spawns

    # The nav hooks first: a destination on top of a counter has no route to
    # it, and every point below is derived from these three. `solids` is the
    # site's collision reading when the caller has one -- without it the hook
    # is only floored, not moved off whatever it is standing in.
    pos = site_spawns.seat_destinations(
        pos, solids=solids, bounds=bounds)[0]
    # And then off the wall it is standing against. Seating answers "is there
    # floor under this point"; this answers "will the bake leave a polygon on
    # it", which is a different question and the one the bot actually needs.
    pos = site_spawns.clear_crew_spawn(site_spec or {}, pos)[0]
    # PLACED ONCE, HERE OR ABOVE, NEVER BOTH. `assemble` places the enemies
    # before its site report closes -- a placement Lot could not honour has to
    # travel with the site rather than sit in a .tscn nobody diffs -- and then
    # hands the result down. Roadmap 3 asked for exactly this: "place once,
    # thread the result through, or assert the two agree". An assertion would
    # detect a disagreement; threading makes one impossible to express, because
    # there is no second call left to drift.
    #
    # `enemies=None` still places, so the standalone callers in
    # `tests/test_site_spawns.py` behave as they always have.
    #
    # `solids` matters for the same reason `seat_destinations` gets it above:
    # a placement that judged cover differently from the one in the site report
    # would make the report describe a map nobody plays. Threading removes that
    # risk rather than managing it.
    if enemies is None:
        enemies = site_spawns.place_enemies(
            site_spec or {}, pos, enemy_count=enemy_count,
            lateral=lateral, solids=solids).positions
    enemies = [tuple(e) for e in enemies]
    return {"positions": pos,
            "route": [pos["spawn"], pos["objective"], pos["extraction"]],
            "enemies": enemies}


def _lasertag_hook_nodes(pos, site_spec=None, enemy_count=6, lateral=1.5,
                         solids=None, bounds=None, enemies=None):
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

    # Every position this scene is written from, resolved by the tool rather
    # than by whoever is reading it afterwards. `_lasertag_hook_plan` carries
    # why that distinction is worth a function.
    _plan = _lasertag_hook_plan(pos, site_spec, enemy_count=enemy_count,
                                lateral=lateral, solids=solids, bounds=bounds,
                                enemies=enemies)
    pos = _plan["positions"]
    route = _plan["route"]
    enemies = _plan["enemies"]

    def _hook(name, parent, world, lift=0.0):
        return [f'[node name="{name}" type="Node3D" parent="{parent}"]',
                f'transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, '
                f'{_v3(world, lift)[8:-1]})', '']

    # ONE NODE PER CREW MEMBER. This wrote a single `LT_PlayerSpawn` and
    # `LT_MapEvalHarness.spawn_players` puts every crew member on
    # `player_spawns[i % size()]` -- so a crew of four landed four capsules on
    # one coordinate, interpenetrating, and `lot_demo_001` graded 10/BROKEN with
    # 116 stuck events and not one shot fired in 25 runs.
    #
    # The harness matches these with `begins_with`, so the suffixed names are
    # found with no change to Laser Tag. Index 0 keeps the bare name and the
    # position `clear_crew_spawn` chose: `_sort_by_name` puts it first, and it
    # is still the mission's spawn.
    crew = site_spawns.crew_spawns(
        site_spec or {}, pos["spawn"],
        int((site_spec or {}).get("crew_size", 1) or 1))
    body = []
    for i, member in enumerate(crew):
        body += _hook("LT_PlayerSpawn" if i == 0 else f"LT_PlayerSpawn_{i}",
                      ".", member, 1.0)
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
            # THE COVER'S OWN ELEVATION, not the objective's. `at` is a
            # ground-plan XY and carries no height, and this used to fill the
            # third component with `oz` -- so every cover test point inherited
            # whatever height the OBJECTIVE happened to sit at.
            #
            # It is invisible while the objective is at grade and wrong the
            # moment it is not. Measured on a five-building street whose
            # objective sits in a basement at -3.10: the eight cover BODIES
            # were written at y 1.00, standing on the street, and their eight
            # test points at y -3.10, three metres under it. Level Factory's
            # ground-contact preflight refused the map -- correctly -- with
            # "8 of 19 mission point(s) have no ground beneath them", and no
            # firefight was ever evaluated.
            #
            # The BODY has always taken its height from its own size
            # (`_box_node(..., (cx, sy / 2, -cy))` above). Reading the same
            # size here is what makes the two agree; two writers of one thing
            # disagreeing is what produced this.
            # `size` is written in the GODOT frame -- (x, height, y) -- which
            # `site_cover.Cover.as_spec` states explicitly, so the height is
            # the SECOND component and not the third.
            size = piece.get("size") or ()
            if len(size) >= 2:
                height = float(size[1])
            else:
                import site_cover
                height = site_cover.COVER_HEIGHT
            body += _hook(f"Cover_{i}", "LT_CoverTestPoints",
                          (cx, cy, height / 2.0))
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
                     addon_dir="addons/lot", portable=False, solids=None,
                     enemies=None):
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
    # Same push the hook nodes get, on the same inputs, so the walk scene and
    # the evaluated scene put the crew in the same place. Two answers for one
    # spawn is the defect the comment above this one is about.
    pos = site_spawns.clear_crew_spawn(site_spec or {}, pos)[0]
    _p = "" if portable else "res://"
    _a = "" if portable else addon_dir + "/"
    ladder_body, ladder_subs = _ladder_volume_nodes(merged)
    lt_body = _lasertag_hook_nodes(
        pos, site_spec, solids=solids,
        bounds=_destination_bounds(merged, pos), enemies=enemies)
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
def assemble(site_spec_path, out_dir=None, walkable=False, navqa=False,
             preview=False, portable=False):
    """Read a site spec, write <name>.site.gameplay.json and <name>.tscn.

    With portable=True the SHIPPED scenes (the site scene and, with
    --walkable, the walk scene) reference their contents relative to
    themselves rather than through res://, so the out dir is a folder a
    consumer can drop anywhere in their own project. res:// is rooted at
    the project directory, so a res:// ref only resolves for a consumer
    who reproduces this layout at their own root -- and an ABSOLUTE path
    behind res:// (res://C:/...) asks for a folder named 'C:' inside the
    project and resolves nowhere at all.

    The nav-QA scene is deliberately excluded: it is consumed by Lot's
    own walktest harness, which supplies addons/lot/ and resolves the
    res:// form today.
    """
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
    # ...and then off the wall, BEFORE anything is planned against where the
    # crew stands. `write_walk_scene` clears the crew spawn and ships the
    # cleared one; this did not, so the cover was planned for a crew standing
    # where the scene does not put it. On the `test_site_cover` fixture that is
    # (-70.0, 30.0), the dead centre of `b0` -- from inside a shell almost every
    # sightline reads as already broken, `plan_cover` returned open_lines=0,
    # and the shipped scene still opened with 51.9 m of clear ground to
    # Enemy_5. `clear_crew_spawn` returns a new dict and leaves its input
    # alone, and seat+clear is idempotent, so the shipped spawn does not move --
    # only what gets planned against it.
    #
    # The findings ARE reported here: `write_walk_scene` drops them on the
    # stated grounds that "assemble runs the same call on the same inputs and
    # reports them", and until this line existed assemble did not make the
    # call, so a pushed crew spawn was reported by nobody.
    walk_pos, clear_findings = site_spawns.clear_crew_spawn(site_spec, walk_pos)
    # The collision reading read four lines up. It was already going to
    # `seat_destinations`; the enemies are placed against sightlines and had
    # been getting declared footprints instead.
    spawn_plan = site_spawns.place_enemies(site_spec, walk_pos, solids=solids)

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
    # THE STREET FIRST (roadmap 153): the kerb line and the parked cars are
    # planned before the cover planner runs, and stand in its measurement,
    # so a truck in the road is the exception -- a line nothing on the
    # street could break -- rather than the rule.
    import site_furniture
    import site_parking
    import site_streets
    furniture_findings = []
    furniture = site_furniture.plan_furniture(site_streets.roads(site_spec),
                                              site_spec.get("buildings") or [],
                                              list(cover_points.values()),
                                              furniture_findings)
    site_spec.setdefault("cover", []).extend(furniture)
    merged["furniture_plan"] = {"placed": furniture, "findings": furniture_findings}
    # a junction approach whose control could not be stood by the street
    # rules (docs/STREET_RULES.md) is said, not silently left bare
    for f_ in furniture_findings:
        print(f"[lot] {f_}")
    standing = []
    for cv in site_spec["cover"]:
        sx, _sy, sz = cv.get("size", COVER)
        standing.append((cv["at"][0] - sx / 2.0, cv["at"][1] - sz / 2.0,
                         cv["at"][0] + sx / 2.0, cv["at"][1] + sz / 2.0))
    parked = site_parking.plan_parking(site_streets.roads(site_spec), standing,
                                       list(cover_points.values()))
    site_spec["cover"].extend(parked)
    merged["parking_plan"] = {"placed": parked}
    for cv in parked:
        sx, _sy, sz = cv["size"]
        standing.append((cv["at"][0] - sx / 2.0, cv["at"][1] - sz / 2.0,
                         cv["at"][0] + sx / 2.0, cv["at"][1] + sz / 2.0))
    if parked:
        print(f"[lot] LOT_PARKING_PLACED: {len(parked)} car(s) parked in the "
              f"kerb lanes' bays")
    if furniture:
        from collections import Counter as _Counter
        _by = _Counter(f["species"] for f in furniture)
        print("[lot] LOT_FURNITURE_PLACED: " + ", ".join(
            f"{n} {s}" for s, n in sorted(_by.items())) + " along the kerb line")
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
               cover_points["LT_ExtractionPoint"]],
        # Species-shaped pieces, largest first (roadmap 22): a box truck, a
        # container, a car -- turned across the line they break -- instead
        # of a 3 m cube. Each is a slot the site's manifest carries.
        species=site_cover.COVER_SPECIES,
        # the kerb line and the parked cars, already standing
        standing=standing)
    site_spec["cover"].extend(c.as_site_cover() for c in cover_plan.cover)
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
    for f_ in (seat_findings + clear_findings + spawn_plan.findings
               + cover_findings):
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
                      portable=portable, self_flooring=self_flooring)
    # The site's own slot manifest: its cover, as prop slots Zoo builds to
    # (roadmap 22). Written beside the scene the way Deli Counter writes a
    # building's, so the same kit build serves both.
    slots_out = os.path.join(out_dir, f"{site_spec['name']}.slots.json")
    n_slots = write_site_slots(site_spec, slots_out)
    print(f"[lot] site slots -> {slots_out} ({n_slots} cover slot(s))")
    # The street's paint, as data (roadmap 153): the same rectangles the
    # scene draws as quads, for the decal layer to carry as decals when it
    # can, and for anything that wants to know where a crosswalk is.
    import site_streets
    marks = site_streets.manifest(site_spec)
    marks_out = os.path.join(out_dir, f"{site_spec['name']}.markings.json")
    with open(marks_out, "w", encoding="utf-8") as fh:
        json.dump(marks, fh, indent=2)
    print(f"[lot] site markings -> {marks_out} ({len(marks['roads'])} road(s), "
          f"{len(marks['markings'])} marking(s))")

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
        "interactives": len(merged["interactives"]),
        "tactical": tactical_report,
        "steps": result_steps,
        "pacing": merged["pacing"],
    }

    if walkable:
        walk_out = os.path.join(out_dir, f"{site_spec['name']}_walk.tscn")
        # The enemies this report already carries. Placing them again here
        # would be a second answer to a question already answered, which is
        # roadmap 3 and which cost a whole level's cover being planned against
        # a set the scene did not contain.
        result["walk_positions"] = write_walk_scene(
            site_spec, merged, walk_out, site_spec["name"], solids=solids,
            portable=portable, enemies=spawn_plan.positions)
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
    portable = "--portable" in sys.argv
    if not args:
        print("usage: python lot.py <site_spec.json> [out_dir] "
              "[--walkable] [--navqa] [--preview] [--portable]")
        raise SystemExit(2)
    out = args[1] if len(args) > 1 else None
    try:
        r = assemble(args[0], out, walkable=walkable, navqa=navqa,
                     preview=preview, portable=portable)
    except Exception as e:
        # site_tactical.SiteTacticalError and friends: fail loudly, like a gate
        print(f"[lot] BUILD FAILED: {e}")
        raise SystemExit(1)
    print(f"[lot] assembled '{os.path.basename(args[0])}': "
          f"{r['buildings']} buildings, {r['markers']} markers, "
          f"{r['rooms']} rooms, {r['interactives']} interactives")
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
