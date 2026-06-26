## [0.5.0] - Carry building rarity through the site merge
- A building's optional `rarity` (from Deli Counter) now lands on its record in
  the merged `<site>.site.gameplay.json`: each `buildings[]` entry gains
  `rarity` + `rarity_color` when the building declares one (clean/absent when it
  doesn't). So a compound carries a per-building rarity index — every door on the
  block its own reveal.
- The breachable door/breach openings Deli Counter already stamps with the
  rarity colour pass through the openings merge untouched, so a networked door in
  the assembled site pops the right colour with no extra work here.
- Lot does not assign rarities across a run — each building's rarity comes from
  its own spec. Deterministic per-run assignment from the site seed remains a
  possible future feature.
- New test: rarity carry-through (record + stamped openings). 16 tests pass.

## [0.4.0] - Pacing estimate + structural encounter intel
- New site_pacing.py. Two offline STRUCTURAL analyses over the declared site.
  Neither predicts "fun" (fun is a feel property only a playthrough reveals);
  both describe structure, with every number shown as an estimate from declared
  inputs, never a verdict.
- PACING: estimates time-to-complete for the mode's critical route as a
  min/expected/max range, checked against a target window (default 7-15 min,
  overridable). Heist = spawn->objective(+dwell)->extraction; assault =
  spawn->objective + resolution; survival = reach holdout + waves x wave length.
  Timings DERIVED from mode + distances (move_speed, objective_secs, wave_secs,
  etc.), each overridable per-spec under "pacing". Emits a transparent phase
  breakdown that sums to the estimate, into the site gameplay.json under
  "pacing", and a one-line status (within / too short / too long / straddles).
- ENCOUNTER INTEL: per-leg geometric FACTS about combat opportunity (route
  length, distinct approaches, open-ground distance, nearby cover count) under
  "encounters". Describes opportunity, NOT quality - explicitly never a score.
- Not a simulation, not an AI, not a fun-meter. No agents move, no shots fire.
  The in-engine walk remains the only thing that tells you if it's actually fun.
- Tests: too-short detection, breakdown-sums-to-estimate, overrides, encounter-
  facts-not-score (15 tests total, all offline).

## [0.3.0] - Site tactical layer (pathing + 3 modes, at site scale)
- New site_tactical.py: the site-scale echo of Deli Counter's tactical layer.
  Reasons about reachability and the three modes ACROSS the site (over buildings
  and declared paths), as Deli Counter does WITHIN a building (over rooms and
  doors). Intel + light gates, deterministic, offline - analyzes what you
  DECLARED (building-to-building paths + merged markers), not a computed navmesh.
- INTEL (never fails): site connectivity graph, isolated-building detection
  ("no isolated buildings" - the site echo of "no isolated rooms"),
  spawn->objective distance, count of distinct objective approaches. Emitted
  into the site gameplay.json under "tactical".
- GATES (fail the build) only when a site "mode" is declared:
  assault = objective building reachable by >=2 distinct approaches;
  heist = spawn -> objective -> extraction path-connected;
  survival = safe building -> holdout path-connected.
- New optional site-spec fields: mode, objective, spawn, extraction, safe
  (building-id designations). No mode => pure intel, no gates. The designations
  also resolve "which building's objective is THE site objective."
- Tests: tactical intel + all three mode gates (11 tests total, all offline).

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
