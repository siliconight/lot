"""Does a building floor its own footprint? (ground-hole policy)

Lot cuts an inset hole in the site ground under every building. The reason is
sound: a solid ground slab running through a footprint seals the basement
stairwell, and the building's own slabs are supposed to floor its interior.

That reasoning has an unstated premise -- that the building's geometry file
actually brings collision. A baked `shell.glb` does not. Godot's glTF importer
generates collision bodies only for nodes whose names carry the `-col` family
of suffixes (or when the .import file asks for physics); a plain export is
MeshInstance3D and nothing else. So a site assembled from plain shells cut a
hole under every building and put nothing in it, and four adjacent footprints
merged into one contiguous void with the spawn, the objective, the extraction
and every enemy standing over it.

Nothing said so. The scene loaded, the ground slabs were there (a ring of
streets around the block), and the hole was only visible as a downstream
refusal: Laser Tag's `validate_map()` rays down from the spawn, hits nothing,
and reports NO_WORLD_COLLISION.

So the premise gets checked. A hole is cut only where a building demonstrably
floors itself; everywhere else the ground stays and Lot says why. Keeping the
ground can never create a fall -- the worst case is a floor under a building
that had one already.

Pure: text and bytes in, verdicts out. No Godot, no Blender, stdlib only.
"""
from __future__ import annotations

import json
import os
import re

# Godot's glTF importer generates a physics body for a node whose name ends in
# one of these (docs: "Importing 3D scenes / Node type customization").
COLLISION_SUFFIXES = ("-col", "-convcol", "-colonly", "-convcolonly",
                      "-rigid", "-vehicle", "-wheel")

# Collision a .tscn brings on its own, without following instances.
_TSCN_COLLIDERS = re.compile(
    r'type="(StaticBody3D|RigidBody3D|CharacterBody3D|AnimatableBody3D|'
    r'CollisionShape3D|CollisionPolygon3D|GridMap|CSGBox3D|CSGPolygon3D|'
    r'CSGMesh3D|CSGCombiner3D)"')
_TSCN_EXT_SCENE = re.compile(
    r'\[ext_resource[^\]]*type="PackedScene"[^\]]*path="([^"]+)"')

# How far to follow a .tscn's instanced sub-scenes before giving up. Deli
# Counter nests modules a couple of levels; a cap keeps a cyclic or pathological
# pack from turning a scene write into a graph walk.
MAX_SCENE_DEPTH = 6

PRESENT = "present"
ABSENT = "absent"
UNKNOWN = "unknown"



class Collision:
    """What a building's geometry file contributes to world collision."""

    __slots__ = ("source", "state", "detail")

    def __init__(self, source: str, state: str, detail: str = ""):
        self.source = source
        self.state = state
        self.detail = detail

    @property
    def present(self) -> bool:
        return self.state == PRESENT

    @property
    def floors_itself(self) -> bool:
        """Only a demonstrated collider earns a hole in the ground."""
        return self.state == PRESENT

    def as_dict(self) -> dict:
        return {"source": self.source, "state": self.state, "detail": self.detail}

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Collision({self.source!r}, {self.state!r}, {self.detail!r})"


# ---------------------------------------------------------------------------
# glTF binary
# ---------------------------------------------------------------------------
def glb_node_names(data: bytes) -> list:
    """Node names from a .glb's JSON chunk, or [] if it cannot be read.

    A malformed or truncated file yields [] rather than raising: the caller
    treats "cannot tell" as "do not cut a hole", which is the safe answer, and
    a site assembly must not die on a bad asset it can route around.

    The container walk itself lives in `site_collision`, which needs the same
    chunk to read collider extents out of. One reader for the glTF envelope
    means "this file parses" cannot come out differently depending on which
    module asked.
    """
    import site_collision

    doc = site_collision.glb_document(data)
    if doc is None:
        return []
    return [str(n.get("name", "")) for n in doc.get("nodes", []) or []
            if isinstance(n, dict)]


def name_generates_collision(name: str) -> bool:
    """Godot matches the suffix on the node name, case-insensitively, and
    tolerates the `name-col.001` form Blender appends on duplicate names."""
    base = re.sub(r"\.\d+$", "", str(name).strip().lower())
    return base.endswith(COLLISION_SUFFIXES)


def _import_file_requests_physics(path: str) -> bool:
    """A .glb can also be given collision by its sibling .import file, which is
    where the editor records per-node physics choices."""
    sidecar = path + ".import"
    try:
        with open(sidecar, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    return bool(re.search(r'"?generate/physics"?\s*[:=]\s*true', text))


# ---------------------------------------------------------------------------
# One source
# ---------------------------------------------------------------------------
def inspect_source(path: str, *, _depth: int = 0, _seen=None) -> Collision:
    """Whether the geometry at `path` brings collision of its own."""
    label = os.path.basename(path) or path
    seen = _seen if _seen is not None else set()
    real = os.path.abspath(path)
    if real in seen:
        return Collision(label, UNKNOWN, "scene instances itself")
    seen = seen | {real}

    if not os.path.exists(path):
        return Collision(label, UNKNOWN, "geometry file not found on disk")

    lower = path.lower()
    if lower.endswith(".glb") or lower.endswith(".gltf"):
        if _import_file_requests_physics(path):
            return Collision(label, PRESENT, "import settings generate physics")
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as exc:
            return Collision(label, UNKNOWN, f"unreadable: {exc}")
        if lower.endswith(".gltf"):
            try:
                doc = json.loads(data.decode("utf-8"))
                names = [str(n.get("name", "")) for n in doc.get("nodes", [])
                         if isinstance(n, dict)]
            except (UnicodeDecodeError, ValueError):
                return Collision(label, UNKNOWN, "glTF JSON could not be parsed")
        else:
            names = glb_node_names(data)
            if not names:
                return Collision(label, UNKNOWN, "glTF node list could not be read")
        hits = [n for n in names if name_generates_collision(n)]
        if hits:
            return Collision(label, PRESENT,
                             f"{len(hits)} collision node(s), e.g. {hits[0]}")
        return Collision(
            label, ABSENT,
            f"{len(names)} node(s), none named with a "
            f"{'/'.join(COLLISION_SUFFIXES[:2])} suffix")

    if lower.endswith(".tscn") or lower.endswith(".scn"):
        if lower.endswith(".scn"):
            return Collision(label, UNKNOWN, "binary scene is not readable as text")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as exc:
            return Collision(label, UNKNOWN, f"unreadable: {exc}")
        if _TSCN_COLLIDERS.search(text):
            return Collision(label, PRESENT, "scene declares a collision body")
        if _depth >= MAX_SCENE_DEPTH:
            return Collision(label, UNKNOWN,
                             f"instanced scenes nested deeper than {MAX_SCENE_DEPTH}")
        # No collider of its own -- it may instance one. Follow, and let a
        # single unreadable branch make the whole answer "unknown" rather than
        # letting it read as a confident "absent".
        base = os.path.dirname(os.path.abspath(path))
        unresolved = False
        for ref in _TSCN_EXT_SCENE.findall(text):
            child = _resolve_res(ref, base)
            if child is None:
                unresolved = True
                continue
            sub = inspect_source(child, _depth=_depth + 1, _seen=seen)
            if sub.present:
                return Collision(label, PRESENT,
                                 f"instanced {sub.source} brings collision")
            if sub.state == UNKNOWN:
                unresolved = True
        if unresolved:
            return Collision(label, UNKNOWN, "an instanced scene could not be read")
        return Collision(label, ABSENT, "no collision body in the scene or its instances")

    return Collision(label, UNKNOWN, "unrecognised geometry format")


def _resolve_res(ref: str, base_dir: str):
    """A .tscn's ext_resource path -> a file on disk, or None. `res://` is a
    project root Lot does not own, so it is tried relative to the scene's own
    directory and to its ancestors -- which is where a staged pack puts it."""
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
    return None


# ---------------------------------------------------------------------------
# The whole site
# ---------------------------------------------------------------------------
def audit(site_spec: dict, search_dirs, resolved=None) -> dict:
    """building id -> Collision, for every building in the spec.

    `search_dirs` are tried in order; the spec's own directory first is the
    usual call. `resolved` is an already-built source -> path map and wins over
    the search when it has an entry, so a caller that has done its own asset
    resolution (the pack builder does, and refuses to write without it) audits
    exactly the bytes it is about to ship rather than a same-named file that
    happened to sit earlier on the search path.

    A source that resolves nowhere is UNKNOWN, not ABSENT: "the file is
    missing" and "the file has no collision" are different problems and the
    operator needs to be told which one they have.
    """
    dirs = [d for d in search_dirs if d]
    known = dict(resolved or {})
    out = {}
    cache = {}
    for b in site_spec.get("buildings", []):
        src = b.get("scene") or b.get("glb")
        bid = str(b.get("id", "?"))
        if not src:
            out[bid] = Collision("(none)", UNKNOWN, "building declares no geometry")
            continue
        if src not in cache:
            path = known.get(src) or next(
                (os.path.join(d, src) for d in dirs
                 if os.path.exists(os.path.join(d, src))), None)
            cache[src] = inspect_source(path or src)
        out[bid] = cache[src]
    return out


def self_flooring_ids(reports: dict) -> set:
    """The buildings that have earned a hole cut in the ground beneath them."""
    return {bid for bid, rep in reports.items() if rep.floors_itself}


def findings(reports: dict) -> list:
    """Lot-shaped findings for the buildings that do not floor themselves.

    Emitted whether or not the ground was kept, because the operator needs the
    real fact: this building has no collision, so you walk through its walls.
    Filling the hole stops the fall; it does not make the shell solid.
    """
    out = []
    absent = sorted(bid for bid, r in reports.items() if r.state == ABSENT)
    unknown = sorted(bid for bid, r in reports.items() if r.state == UNKNOWN)
    if absent:
        detail = "; ".join(f"{bid}: {reports[bid].source} — {reports[bid].detail}"
                           for bid in absent)
        out.append({
            "code": "LOT_SHELL_NO_COLLISION",
            "severity": "major",
            "category": "collision",
            "message": (
                f"{len(absent)} building shell(s) bring no collision, so they "
                f"floor nothing and stop nothing: {detail}. Lot kept the site "
                f"ground under them rather than cutting a hole, so the site is "
                f"still walkable, but the shells are pass-through until they "
                f"are exported with -col nodes or physics enabled on import."),
        })
    if unknown:
        detail = "; ".join(f"{bid}: {reports[bid].source} — {reports[bid].detail}"
                           for bid in unknown)
        out.append({
            "code": "LOT_SHELL_COLLISION_UNKNOWN",
            "severity": "moderate",
            "category": "collision",
            "message": (
                f"{len(unknown)} building shell(s) could not be checked for "
                f"collision: {detail}. Lot kept the site ground under them; a "
                f"hole is only cut where a building is known to floor itself."),
        })
    return out
