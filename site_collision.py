"""What the site's own geometry is solid at, in site space.

Lot has always known where its buildings *are* -- `site_spawns.footprint_rect`
keeps an enemy out of a building by treating the whole footprint as one solid
block. That model is right at the scale it was written for and blind one level
down: inside a footprint it cannot tell a floor from a counter, and the mission
nav hooks live inside footprints.

The site this module was written for put `LT_ObjectivePoint` at the exact centre
of a `cashier_cage`, which is also the exact centre of the `cage_counter` prop
Deli Counter bakes into that room -- a 6.0 x 1.0 m box 1.1 m tall. The previous
fix seated the hook's *height* on the floor, which was correct as far as it
went; the hook's *footprint* stayed on the counter. Laser Tag's navmesh reads
that cell's standing surface as the counter top, 1.1 m above a room floor that
is flat 0, with no step between -- so the cell is standable and is an island,
the bot has no route to it, and the whole map is refused with 0% completion for
a one-metre placement error. It is not seed-specific: the gameplay generator
places the objective marker at its room's centre and Deli Counter places the
counter at the same centre, on every building of this archetype.

So Lot reads the collision of the shells it assembles. Godot's glTF importer
generates a physics body for a node whose name ends in the `-col` family of
suffixes, and the position and extent of that body are fully described by the
file's JSON chunk: the node hierarchy carries the transforms, and each mesh
primitive's POSITION accessor carries min/max. The furniture inside a baked
shell can therefore be located without Blender, without Godot, and without
decoding a vertex buffer.

This is deliberately a *second* implementation of that published contract --
Level Factory reads the same suffixes on the other side of the gate. Sharing
one reader would mean a bug in it blinds the producer and the check that is
supposed to catch the producer at the same moment, which is the whole reason
the gate exists. The two agree because the contract is written down, not
because they are the same code.

Boxes are axis-aligned hulls of the collider meshes. For the slabs, walls and
counters Deli Counter bakes -- which are boxes -- the hull is the shape. For
anything concave the hull is larger, so this reader errs towards "something is
solid here", which moves a nav hook that did not need moving rather than
leaving one stranded on a prop. It says how far it moved anything.

Nothing here silently reports "clear" for geometry it could not read. A source
that fails to parse, or a scene that declares colliders in a form this module
does not model, comes back as *incomplete*, and a caller that cannot see is
required to say so rather than act on the emptiness.

Pure: bytes and dicts in, boxes and verdicts out. No Godot, no Blender, stdlib
only.
"""
from __future__ import annotations

import json
import math
import os
import re
import struct
from dataclasses import dataclass

#: Godot's glTF importer generates a physics body for a node whose name ends in
#: one of these (docs: "Importing 3D scenes / Node type customization").
COLLISION_SUFFIXES = ("-col", "-convcol", "-colonly", "-convcolonly",
                      "-rigid", "-vehicle", "-wheel")

_GLB_MAGIC = 0x46546C67   # 'glTF'
_GLB_JSON = 0x4E4F534A    # 'JSON'

#: Blender appends `.001` to duplicated names, after the suffix Godot matches.
_DUP = re.compile(r"\.\d+$")
_PHYSICS = re.compile(r'"?generate/physics"?\s*[:=]\s*true')

#: How close a nav hook may come to a solid and still have somewhere to stand.
#:
#: Touching the geometry is not the test. Recast erodes the walkable surface by
#: the agent radius from every obstacle during the bake (Lot authors 0.4 m), and
#: quantises what is left onto its voxel grid (0.15 m), so a hook a quarter of a
#: metre off a counter has clear air around it and no navmesh polygon beneath
#: it -- which is the same refusal as standing on the counter, arrived at more
#: confusingly. The margin covers the erosion, the voxel grid, and the coarser
#: 0.5 m grid Level Factory rasterises on the other side of the gate, so a
#: position this module calls clear is one every downstream reader agrees about.
CLEARANCE = 0.75

#: A shell that nests deeper than this is malformed, or is trying to be a graph.
MAX_NODE_DEPTH = 64
#: How far to follow a .tscn's instanced sub-scenes. Matches site_ground.
MAX_SCENE_DEPTH = 6

#: Collider declarations a .tscn can carry that this module does not turn into
#: boxes. Finding one does not make the reading wrong -- it makes it *partial*,
#: and the difference has to survive to the caller.
_TSCN_OWN_COLLIDER = re.compile(
    r'type="(CollisionShape3D|CollisionPolygon3D|GridMap|CSGBox3D|CSGPolygon3D|'
    r'CSGMesh3D|CSGCombiner3D|HeightMapShape3D)"')
_TSCN_EXT_SCENE = re.compile(
    r'\[ext_resource[^\]]*type="PackedScene"[^\]]*path="([^"]+)"[^\]]*'
    r'id="([^"]+)"')
_TSCN_EXT_SCENE_ALT = re.compile(
    r'\[ext_resource[^\]]*id="([^"]+)"[^\]]*type="PackedScene"[^\]]*'
    r'path="([^"]+)"')
_TSCN_NODE = re.compile(r'^\[node\s+(.*)\]\s*$')
_TSCN_INSTANCE = re.compile(r'instance=ExtResource\(\s*"?([^")]+)"?\s*\)')
_TSCN_ATTR = re.compile(r'(\w+)="([^"]*)"')
_TSCN_TRANSFORM = re.compile(r'^transform\s*=\s*Transform3D\(([^)]*)\)')

_IDENTITY = ((1.0, 0.0, 0.0, 0.0),
             (0.0, 1.0, 0.0, 0.0),
             (0.0, 0.0, 1.0, 0.0))


# ---------------------------------------------------------------------------
# what a solid is
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Box:
    """An axis-aligned solid in Lot's site space: x east, y north, z up."""

    name: str
    centre: tuple
    size: tuple

    @property
    def top(self) -> float:
        return self.centre[2] + abs(self.size[2]) / 2.0

    @property
    def bottom(self) -> float:
        return self.centre[2] - abs(self.size[2]) / 2.0

    def covers(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (abs(x - self.centre[0]) <= abs(self.size[0]) / 2.0 + margin
                and abs(y - self.centre[1]) <= abs(self.size[1]) / 2.0 + margin)

    def as_dict(self) -> dict:
        return {"name": self.name, "centre": list(self.centre),
                "size": list(self.size)}


@dataclass(frozen=True)
class Reading:
    """The solids Lot could find, and an honest account of what it could not.

    ``complete`` is the part that matters downstream. A site that parsed and
    holds no furniture is a confident "nothing is in the way"; a site with one
    unreadable shell is "cannot tell", and a caller must not treat the two the
    same. Anything that acts on this reading acts only where ``complete`` is
    true, or says which building it could not see into.
    """

    boxes: tuple = ()
    complete: bool = True
    unread: tuple = ()
    detail: str = ""

    def covering(self, x: float, y: float, margin: float = 0.0) -> list:
        """Every solid whose footprint contains ``(x, y)``, tallest last."""
        hits = [b for b in self.boxes if b.covers(x, y, margin)]
        hits.sort(key=lambda b: b.top)
        return hits


# ---------------------------------------------------------------------------
# the glTF container
# ---------------------------------------------------------------------------
def glb_document(data: bytes):
    """The glTF JSON document out of a binary ``.glb``, or ``None``.

    Malformed or truncated input yields ``None`` rather than raising: a site
    assembly must not die on one bad asset it can report and route around.
    """
    if len(data) < 20:
        return None
    try:
        magic, _version, _length = struct.unpack_from("<III", data, 0)
    except struct.error:
        return None
    if magic != _GLB_MAGIC:
        return None
    offset = 12
    while offset + 8 <= len(data):
        try:
            length, kind = struct.unpack_from("<II", data, offset)
        except struct.error:
            return None
        if kind == _GLB_JSON:
            try:
                doc = json.loads(
                    data[offset + 8: offset + 8 + length].decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return None
            return doc if isinstance(doc, dict) else None
        offset += 8 + length + (-length % 4)
    return None


def name_generates_collision(name: str) -> bool:
    """Godot matches the suffix case-insensitively and tolerates `-col.001`."""
    return _DUP.sub("", str(name).strip().lower()).endswith(COLLISION_SUFFIXES)


def import_requests_physics(path: str) -> bool:
    """A ``.glb`` can also be given collision by its sibling ``.import`` file.
    When it is set, every mesh becomes a collider, not just the suffixed ones."""
    try:
        with open(str(path) + ".import", encoding="utf-8", errors="replace") as f:
            return bool(_PHYSICS.search(f.read()))
    except OSError:
        return False


# ---------------------------------------------------------------------------
# transforms, in the file's own Y-up space
# ---------------------------------------------------------------------------
def node_matrix(node: dict):
    """glTF gives a node either a 4x4 ``matrix`` or a TRS triple."""
    raw = node.get("matrix")
    if isinstance(raw, list) and len(raw) == 16:
        # glTF stores it column-major.
        return tuple(tuple(float(raw[4 * col + row]) for col in range(4))
                     for row in range(3))
    tx, ty, tz = (list(node.get("translation") or ()) + [0.0, 0.0, 0.0])[:3]
    qx, qy, qz, qw = (list(node.get("rotation") or ()) + [0.0, 0.0, 0.0, 1.0])[:4]
    sx, sy, sz = (list(node.get("scale") or ()) + [1.0, 1.0, 1.0])[:3]
    rot = ((1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)),
           (2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)),
           (2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)))
    scale = (float(sx), float(sy), float(sz))
    origin = (float(tx), float(ty), float(tz))
    return tuple(tuple(rot[r][c] * scale[c] for c in range(3)) + (origin[r],)
                 for r in range(3))


def compose(outer, inner):
    """``outer`` applied to ``inner``: the child's transform in the parent's
    space."""
    return tuple(
        tuple(sum(outer[r][k] * inner[k][c] for k in range(3)) for c in range(3))
        + (sum(outer[r][k] * inner[k][3] for k in range(3)) + outer[r][3],)
        for r in range(3))


def apply(matrix, point):
    return tuple(sum(matrix[r][c] * point[c] for c in range(3)) + matrix[r][3]
                 for r in range(3))


def hull(matrix, low, high):
    """The axis-aligned bounds of a box carried through ``matrix``."""
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for x in (low[0], high[0]):
        for y in (low[1], high[1]):
            for z in (low[2], high[2]):
                for axis, value in enumerate(apply(matrix, (x, y, z))):
                    lo[axis] = min(lo[axis], value)
                    hi[axis] = max(hi[axis], value)
    return tuple(lo), tuple(hi)


def to_site(low, high, name: str) -> Box:
    """A Y-up axis-aligned span -> a Lot site-space :class:`Box`.

    Lot writes site ``(x, y, z)`` into Godot as ``(x, z, -y)`` (``lot._v3``),
    so the inverse carries an engine-space point back: ``x`` unchanged, site
    ``y`` is ``-gz``, site ``z`` (up) is ``gy``. Extents are unsigned, so the
    two swapped axes simply trade places.
    """
    centre = ((low[0] + high[0]) / 2.0,
              -(low[2] + high[2]) / 2.0,
              (low[1] + high[1]) / 2.0)
    size = (abs(high[0] - low[0]), abs(high[2] - low[2]), abs(high[1] - low[1]))
    return Box(name, centre, size)


# ---------------------------------------------------------------------------
# one glTF document
# ---------------------------------------------------------------------------
def boxes_in(doc: dict, *, every_mesh: bool = False, prefix: str = "") -> Reading:
    """The colliders in a glTF document, in Lot site space, at the file origin."""
    nodes = doc.get("nodes")
    if not isinstance(nodes, list):
        return Reading((), False, ("glTF document declares no nodes",),
                       "glTF document declares no nodes")
    meshes = doc.get("meshes") or []
    accessors = doc.get("accessors") or []
    scenes = doc.get("scenes") or []
    index = doc.get("scene", 0)
    roots = []
    if isinstance(index, int) and 0 <= index < len(scenes):
        roots = list(scenes[index].get("nodes") or [])
    if not roots:
        # A file with no scene declared is still a node list; walking every
        # node that nothing claims as a child recovers the same tree.
        claimed = {c for n in nodes if isinstance(n, dict)
                   for c in (n.get("children") or [])}
        roots = [i for i in range(len(nodes)) if i not in claimed]

    def bounds(mesh_index):
        if not isinstance(mesh_index, int) or not 0 <= mesh_index < len(meshes):
            return None
        low = [float("inf")] * 3
        high = [float("-inf")] * 3
        for prim in meshes[mesh_index].get("primitives") or []:
            ref = (prim.get("attributes") or {}).get("POSITION")
            if not isinstance(ref, int) or not 0 <= ref < len(accessors):
                continue
            lo = accessors[ref].get("min")
            hi = accessors[ref].get("max")
            if not (isinstance(lo, list) and isinstance(hi, list)
                    and len(lo) >= 3 and len(hi) >= 3):
                continue
            for axis in range(3):
                low[axis] = min(low[axis], float(lo[axis]))
                high[axis] = max(high[axis], float(hi[axis]))
        if any(v == float("inf") for v in low):
            return None
        return tuple(low), tuple(high)

    out = []
    unbounded = []
    stack = [(i, _IDENTITY, 0) for i in reversed(roots)]
    seen = set()
    while stack:
        i, parent, depth = stack.pop()
        if not isinstance(i, int) or not 0 <= i < len(nodes):
            continue
        if depth > MAX_NODE_DEPTH or i in seen:
            continue
        seen.add(i)
        node = nodes[i]
        if not isinstance(node, dict):
            continue
        world = compose(parent, node_matrix(node))
        name = str(node.get("name", "")) or f"node{i}"
        if "mesh" in node and (every_mesh or name_generates_collision(name)):
            span = bounds(node["mesh"])
            if span is None:
                unbounded.append(f"{prefix}{name}: no POSITION bounds")
            else:
                low, high = hull(world, span[0], span[1])
                out.append(to_site(low, high, f"{prefix}{name}"))
        for child in node.get("children") or []:
            stack.append((child, world, depth + 1))

    detail = f"{len(out)} collider(s) in {len(seen)} node(s)"
    if unbounded:
        detail += f", {len(unbounded)} with no readable bounds"
    return Reading(tuple(out), not unbounded, tuple(unbounded), detail)


# ---------------------------------------------------------------------------
# Godot scene text
# ---------------------------------------------------------------------------
def _godot_transform(numbers):
    """Godot's ``Transform3D`` argument order is basis *columns* then origin."""
    v = [float(n) for n in numbers]
    if len(v) < 12:
        return _IDENTITY
    return ((v[0], v[3], v[6], v[9]),
            (v[1], v[4], v[7], v[10]),
            (v[2], v[5], v[8], v[11]))


def _tscn_instances(text: str):
    """``(source path, transform)`` for every instanced PackedScene in a scene.

    Deli Counter's primary output is a ``.tscn`` that instances shared module
    scenes, so a reader that only understood ``.glb`` would see a building's
    furniture only when the building happened to be baked.
    """
    ext = {}
    for path, rid in _TSCN_EXT_SCENE.findall(text):
        ext[rid] = path
    for rid, path in _TSCN_EXT_SCENE_ALT.findall(text):
        ext.setdefault(rid, path)

    out = []
    pending = None
    for raw in text.splitlines():
        line = raw.strip()
        head = _TSCN_NODE.match(line)
        if head:
            attrs = dict(_TSCN_ATTR.findall(head.group(1)))
            ref = _TSCN_INSTANCE.search(head.group(1))
            pending = None
            if ref and ref.group(1) in ext:
                pending = [attrs.get("name", "?"), ext[ref.group(1)], _IDENTITY]
                out.append(pending)
            continue
        if pending is not None:
            matrix = _TSCN_TRANSFORM.match(line)
            if matrix:
                pending[2] = _godot_transform(matrix.group(1).split(","))
                pending = None
    return [(name, path, matrix) for name, path, matrix in out]


def _resolve_res(ref: str, base_dir: str, search_dirs=()):
    """A ``.tscn``'s ext_resource path -> a file on disk, or ``None``.

    ``res://`` names a project root Lot does not own, so it is tried relative
    to the scene's own directory and its ancestors -- which is where a staged
    pack puts it -- and then against the caller's search dirs.
    """
    rel = ref[len("res://"):] if ref.startswith("res://") else ref
    rel = rel.lstrip("/")
    if not ref.startswith("res://"):
        direct = os.path.join(base_dir, rel)
        if os.path.exists(direct):
            return direct
    here = base_dir
    for _ in range(MAX_SCENE_DEPTH):
        cand = os.path.join(here, rel)
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    for d in search_dirs:
        cand = os.path.join(d, rel)
        if os.path.exists(cand):
            return cand
    return None


def _transform_boxes(boxes, matrix):
    """Carry site-space boxes through a Godot (Y-up) transform.

    The boxes are already in site space, so the transform is converted rather
    than the geometry: a Godot basis column acting on ``(x, y, z)_godot`` acts
    on ``(x, z, -y)_site``. Re-hulling the eight corners keeps the result
    axis-aligned for any rotation, at the cost of growing the box off the right
    angles -- the conservative direction (see the module docstring).
    """
    out = []
    for box in boxes:
        cx, cy, cz = box.centre
        hx, hy, hz = (abs(box.size[0]) / 2.0, abs(box.size[1]) / 2.0,
                      abs(box.size[2]) / 2.0)
        lo = [float("inf")] * 3
        hi = [float("-inf")] * 3
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    px, py, pz = cx + sx * hx, cy + sy * hy, cz + sz * hz
                    gx, gy, gz = apply(matrix, (px, pz, -py))
                    for axis, value in enumerate((gx, -gz, gy)):
                        lo[axis] = min(lo[axis], value)
                        hi[axis] = max(hi[axis], value)
        out.append(Box(box.name,
                       tuple((lo[a] + hi[a]) / 2.0 for a in range(3)),
                       tuple(hi[a] - lo[a] for a in range(3))))
    return out


def read_source(path, *, search_dirs=(), prefix: str = "", _depth: int = 0,
                _seen=None) -> Reading:
    """Every collider the geometry at ``path`` brings, in its own site space."""
    label = os.path.basename(str(path)) or str(path)
    seen = set(_seen or ())
    if not path:
        return Reading((), False, (f"{prefix}{label}: no geometry declared",),
                       "no geometry declared")
    real = os.path.abspath(str(path))
    if real in seen:
        return Reading((), True, (), "scene instances itself; stopped")
    seen.add(real)

    if not os.path.exists(path):
        note = f"{prefix}{label}: geometry file not found on disk"
        return Reading((), False, (note,), note)

    lower = str(path).lower()
    if lower.endswith((".glb", ".gltf")):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as exc:
            note = f"{prefix}{label}: unreadable ({exc})"
            return Reading((), False, (note,), note)
        if lower.endswith(".gltf"):
            try:
                doc = json.loads(data.decode("utf-8", errors="replace"))
            except ValueError:
                doc = None
            if not isinstance(doc, dict):
                doc = None
        else:
            doc = glb_document(data)
        if doc is None:
            note = f"{prefix}{label}: glTF JSON could not be read"
            return Reading((), False, (note,), note)
        return boxes_in(doc, every_mesh=import_requests_physics(path),
                        prefix=f"{prefix}{label}:")

    if lower.endswith(".scn"):
        note = f"{prefix}{label}: binary scene is not readable as text"
        return Reading((), False, (note,), note)

    if not lower.endswith(".tscn"):
        note = f"{prefix}{label}: unrecognised geometry format"
        return Reading((), False, (note,), note)

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as exc:
        note = f"{prefix}{label}: unreadable ({exc})"
        return Reading((), False, (note,), note)

    boxes = []
    unread = []
    if _TSCN_OWN_COLLIDER.search(text):
        # The scene declares collision this module does not turn into boxes.
        # Reading the instanced shells anyway is still worth doing -- it is the
        # furniture -- but the answer is partial and has to say so, or a hook
        # gets moved onto a shape nobody looked at.
        unread.append(f"{prefix}{label}: declares collision shapes in the scene "
                      f"text, which this reader does not model")
    if _depth >= MAX_SCENE_DEPTH:
        unread.append(f"{prefix}{label}: instanced scenes nested deeper than "
                      f"{MAX_SCENE_DEPTH}")
        return Reading((), False, tuple(unread), "; ".join(unread))

    base = os.path.dirname(os.path.abspath(str(path)))
    for name, ref, matrix in _tscn_instances(text):
        child = _resolve_res(ref, base, search_dirs)
        if child is None:
            unread.append(f"{prefix}{label}/{name}: {ref} did not resolve")
            continue
        sub = read_source(child, search_dirs=search_dirs,
                          prefix=f"{prefix}{label}/", _depth=_depth + 1,
                          _seen=seen)
        boxes.extend(_transform_boxes(sub.boxes, matrix))
        unread.extend(sub.unread)

    detail = f"{len(boxes)} collider(s) from instanced scenes"
    if unread:
        detail += f", {len(unread)} source(s) unread"
    return Reading(tuple(boxes), not unread, tuple(unread), detail)


# ---------------------------------------------------------------------------
# placing a building on the site
# ---------------------------------------------------------------------------
def place_boxes(boxes, at, rot: float = 0.0):
    """Building-local boxes -> site space, matching ``lot._place_point``.

    Rotation is about the building origin in the ground plane, then a
    translation to the building's site position -- the same order the marker
    merge uses, so a box and the marker standing on it stay together. A
    rotation off the right angles is bounded by the enclosing box rather than
    approximated, which keeps this reader on the conservative side.
    """
    ax, ay = float(at[0]), float(at[1])
    deg = (float(rot) % 360 + 360) % 360
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    out = []
    for box in boxes:
        cx, cy, cz = box.centre
        sx, sy, sz = abs(box.size[0]), abs(box.size[1]), abs(box.size[2])
        rx, ry = cx * c - cy * s, cx * s + cy * c
        if deg % 180 == 0:
            ex, ey = sx, sy
        elif deg % 180 == 90:
            ex, ey = sy, sx
        else:
            ex = abs(sx * c) + abs(sy * s)
            ey = abs(sx * s) + abs(sy * c)
        out.append(Box(box.name, (rx + ax, ry + ay, cz), (ex, ey, sz)))
    return out


def read_site(site_spec: dict, search_dirs, resolved=None) -> Reading:
    """Every collider on the site, in site space, keyed by nothing but position.

    ``search_dirs`` and ``resolved`` mirror ``site_ground.audit`` so the bytes
    inspected here are the bytes that audit inspected and the site ships.
    """
    dirs = [d for d in search_dirs if d]
    known = dict(resolved or {})
    boxes = []
    unread = []
    cache = {}
    for b in site_spec.get("buildings", []) or []:
        bid = str(b.get("id", "?"))
        src = b.get("scene") or b.get("glb")
        if not src:
            unread.append(f"{bid}: declares no geometry")
            continue
        if src not in cache:
            path = known.get(src) or next(
                (os.path.join(d, src) for d in dirs
                 if os.path.exists(os.path.join(d, src))), None)
            cache[src] = read_source(path or src, search_dirs=dirs)
        sub = cache[src]
        boxes.extend(place_boxes(
            [Box(f"{bid}/{x.name}", x.centre, x.size) for x in sub.boxes],
            b.get("at", (0.0, 0.0)), b.get("rot", 0)))
        unread.extend(f"{bid}: {note}" for note in sub.unread)
    detail = f"{len(boxes)} collider(s) across {len(cache)} source(s)"
    if unread:
        detail += f", {len(unread)} unread"
    return Reading(tuple(boxes), not unread, tuple(unread), detail)


# ---------------------------------------------------------------------------
# standing on it
# ---------------------------------------------------------------------------
def obstruction(reading: Reading, x: float, y: float, *, floor: float,
                climb: float, agent_height: float,
                margin: float = CLEARANCE):
    """The solid standing in an agent's way at ``(x, y)``, or ``None``.

    "In the way" is a solid that occupies the column an agent standing on
    ``floor`` would need -- reaching higher than it could step up, and starting
    below the top of its head. A kerb inside the climb limit is not in the way;
    a ceiling above head height is not either. ``margin`` widens each solid by
    the room the bake takes away around it; see ``CLEARANCE``.
    """
    worst = None
    for box in reading.boxes:
        if not box.covers(x, y, margin):
            continue
        if box.top <= floor + climb or box.bottom >= floor + agent_height:
            continue
        if worst is None or box.top > worst.top:
            worst = box
    return worst


def clear_at(reading: Reading, x: float, y: float, *, floor: float,
             climb: float, agent_height: float,
             margin: float = CLEARANCE) -> bool:
    return obstruction(reading, x, y, floor=floor, climb=climb,
                       agent_height=agent_height, margin=margin) is None


def _lattice(radius: float, step: float):
    """Offsets within ``radius`` on a ``step`` lattice, nearest first.

    Deterministic ordering all the way down -- distance, then angle -- so the
    same site resolves to the same position on every run and a candidate pack
    stays comparable to the one before it.
    """
    reach = max(1, int(math.ceil(radius / step)))
    out = []
    for iy in range(-reach, reach + 1):
        for ix in range(-reach, reach + 1):
            if ix == 0 and iy == 0:
                continue
            dx, dy = ix * step, iy * step
            d = math.hypot(dx, dy)
            if d <= radius:
                out.append((d, math.atan2(dy, dx), dx, dy))
    out.sort(key=lambda t: (round(t[0], 6), round(t[1], 6)))
    return [(dx, dy) for _d, _a, dx, dy in out]


@dataclass(frozen=True)
class Resolution:
    """Where a nav hook ended up, and why."""

    point: tuple
    moved: float = 0.0
    blocked_by: str = ""
    reason: str = ""

    @property
    def needed(self) -> bool:
        return bool(self.blocked_by)

    @property
    def resolved(self) -> bool:
        return bool(self.blocked_by) and self.moved > 0.0


def resolve_onto_floor(point, reading: Reading, *, floor: float = 0.0,
                       climb: float = 0.5, agent_height: float = 1.8,
                       radius: float = 6.0, step: float = 0.25,
                       margin: float = CLEARANCE, bounds=None) -> Resolution:
    """Move a nav hook off whatever prop it is standing in, or say why not.

    The search is local and bounded on purpose: a hook is meant to name a spot
    in a particular room, so walking it across the site to find open floor
    would trade a blocker for a mission that no longer happens where it was
    designed to. ``bounds`` keeps it in its own room when the caller knows one;
    ``radius`` caps it regardless.

    Returns the original point unchanged when nothing is in the way, and also
    when nothing near enough is clear -- with ``blocked_by`` set in the second
    case, so "nothing to do" and "nothing I could do" never read the same.
    """
    x, y = float(point[0]), float(point[1])
    z = float(point[2]) if len(point) > 2 else floor
    hit = obstruction(reading, x, y, floor=floor, climb=climb,
                      agent_height=agent_height, margin=margin)
    if hit is None:
        return Resolution((x, y, z))

    for dx, dy in _lattice(radius, step):
        cx, cy = x + dx, y + dy
        if bounds is not None and not (bounds[0] <= cx <= bounds[2]
                                       and bounds[1] <= cy <= bounds[3]):
            continue
        if clear_at(reading, cx, cy, floor=floor, climb=climb,
                    agent_height=agent_height, margin=margin):
            return Resolution((cx, cy, z), math.hypot(dx, dy), hit.name,
                              f"moved to clear floor {math.hypot(dx, dy):.2f} m "
                              f"away")
    return Resolution((x, y, z), 0.0, hit.name,
                      f"no clear floor within {radius:g} m")
