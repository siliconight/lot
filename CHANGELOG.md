# Changelog — Lot

## [0.2.0] — Phase 2: box-vocabulary outdoor
- Generate outdoor connective geometry as Godot primitive nodes (BoxMesh +
  BoxShape3D collision), NOT a baked .glb — keeps Lot offline (no Blender) and
  blockout-honest. Strictly axis-aligned boxes / flat regions; no terrain.
- New optional site-spec fields: `paths` (flat strips between buildings or
  explicit endpoints, with width), `courtyards` (flat rectangular regions),
  `perimeter` (four walls around the ground at a height), `cover` (crates).
- Ground is now a real slab mesh (was an empty StaticBody in Phase 1).
- Tests: outdoor node generation, path-length geometry, load_steps sanity
  (7 tests total, all offline).

## [0.1.0] — Phase 1: placement + merge
- Deterministic placement of built Deli Counter buildings on a shared site.
- Merged, world-offset, namespaced site `gameplay.json` (markers/rooms/
  objectives/loot/zones/surfaces/surface_roles), so buildings don't collide.
- Generated Godot `.tscn` instancing each building `.glb` at its placement.
- Buildings stay separate assets — rebuild one and the site picks it up.
- Tests: determinism, world offset+rotation, namespacing, valid scene.
