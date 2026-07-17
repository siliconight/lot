# The Shared Coordinate Contract

**Status: ratified (Phase 0).** This is the one coordinate, scale, origin, and
orientation contract for the whole pipeline — Deli Counter, Zoo, Lot, Blender,
and Godot. Every generated asset, manifest, and marker obeys it; the round-trip
test (`roundtrip.py`) enforces it; changing it requires re-ratification and a
version bump here.

> **Ratification note (2026-07-17).** The Production Package spec's
> recommended contract says "Positive Y is up." The pipeline's authoring space
> is and remains **Blender-native Z-up**; conversion to Godot's Y-up happens
> exactly once, at the Godot import boundary, and is proven by the round-trip
> test rather than assumed. This preserves the spec's *intent* — a single
> enforced contract with a tested import — without rewriting every existing
> manifest, recipe, and test. Decision approved by the project owner.

## The contract

| Aspect | Rule |
|---|---|
| Measurement unit | **1 unit = 1 meter**, everywhere (spec, manifest, GLB, Godot) |
| Authoring space | **Z-up, right-handed** (Blender native) in every spec, `gameplay.json`, `slots.json`, `lights.json`, and Zoo module |
| Engine space | Godot **Y-up**; the glTF importer performs the Z-up→Y-up conversion at import. No tool bakes a pre-rotated "Godot space" asset |
| World origin | Lot's site ground plane at Z=0. Lot owns final world-space placement |
| Building origin | Footprint **center** at **ground level (Z=0)**. Basements extend below Z=0 |
| Primary entrance | Faces the wall declared in the spec; `rot_z`/`rot` are **degrees about the up axis**, counter-clockwise |
| Pivots | Per-kind, fixed: walls centered on thickness, floor slabs at the consistent corner, props/modules at footprint-center on their ground plane (see `docs/ASSET_SWAP_CONTRACT.md`) |
| Floor elevations | Story *n* floor top at `n × story_height`; floor 0 = ground = Z 0; basement = story −1 |
| Export scale | GLBs export at **1,1,1** with rotation and scale **applied**; no production asset carries unapplied or negative scale. Mirrored variants are re-meshed, never negative-scaled |
| Markers | `gameplay.json` marker positions are **building-local Z-up meters**; Lot transforms them to world space at merge (`site.gameplay.json` markers are world-space Z-up) |
| Transform hierarchy | Child markers inherit only the building placement transform Lot applies — nothing else scales or rotates them |
| Rotation units | Degrees, everywhere a manifest stores rotation (`rot_z`, `rot_y`, `rot`) |

## Who owns what

- **Deli Counter** emits building-local geometry + markers under this contract
  and records expected bounds/origin/entrances/elevations in the build manifest.
- **Zoo** emits modules whose dimensions exactly fit the requesting slot
  (`fit_*` validation), pivoted per-kind, in the same Z-up meter space; a
  module lands on its slot transform with **no** conversion.
- **Lot** owns world placement: offset + yaw about up. It never edits a
  building; it transforms references to it.
- **Godot import** is the only Z-up→Y-up crossing, and the round-trip test's
  engine leg (run where a Godot binary exists) proves positions survive it.

## Enforcement

1. **Build-time transform checks** — every production build asserts: unit
   scale, no negative scale, applied rotation/scale, origin within tolerance
   of the ground-floor reference, markers inside building bounds.
2. **Round-trip test (`roundtrip.py`)** — build → record expectations →
   re-import the exported GLB → compare bounds, origin, entrances, floor
   elevations, and marker positions against the tolerance table below. The
   engine leg re-runs the comparison after Godot import and after Lot
   placement with a known transform.
3. **Zoo `fit_*` validation** — module dims must match the slot request.

## Tolerances (Phase 0 starting values, spec §14)

| Check | Maximum difference |
|---|---|
| Structural alignment | 2 cm |
| Gameplay-marker placement | 5 cm |
| Floor elevation | 2 cm |
| Rotation | 0.5° |
| Modular seam gap | 1 cm |
| Imported building bounds | 2 cm |

Adjustments after the vertical slice must be documented here and applied
consistently; the values live in code in `roundtrip.py::TOLERANCES`.
