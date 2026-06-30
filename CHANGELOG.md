## [0.9.0] - Feed the Heist Nav QA addon (`--navqa`): bots stress-test the site
- `python lot.py <site>.json --navqa` emits `<name>_navqa.tscn` — the composed
  site under a baked `NavigationRegion3D` plus a `NavQASetup` node that tags the
  heist's real anchors into the [Heist Nav QA] addon's groups and runs the bot
  pass: crew_spawn / objective / loot / extraction -> `navqa_player_proxy`,
  cover_low / cover_high -> `navqa_cover`, responder/horde/defender spawns ->
  `navqa_bot_spawn`. So 16 mock cops stress-test the actual heist (where the crew
  stands, the real cover, the cop ingress) with zero hand-placement.
- Ships `godot/addons/lot/lot_navqa_setup.gd` (bakes nav, spawns the grouped
  anchor markers, then loads + runs the QA director). **Decoupled**: if the Heist
  Nav QA addon isn't installed the scene still opens and walks — you get a
  warning instead of a bot run. Lot never hard-depends on the third-party addon;
  it just feeds it if present. The addon itself stays standalone (it QAs single
  buildings too, so it isn't a Lot feature — it's the in-engine validator Lot's
  offline intel defers to).
- On the vault job (real 0.49 buildings) the feed resolves to 11 player proxies,
  12 cover points, 1 cop spawn. Cop spawns are thin because Deli Counter heist
  branches emit few responder/horde markers (the director rings the rest around
  the crew start) — first-class cop-ingress markers on the DC side would sharpen
  pressure-direction QA. Cover count reflects DC 0.49's cover enrichment.
- Base `<name>.tscn` and the `--walkable` scene are unchanged; `--navqa` is a
  separate additive scene.

## [0.8.0] - Walkable sites (`--walkable`): drop in and play the heist
- `python lot.py <site>.json --walkable` now also emits `<name>_walk.tscn` — a
  press-play scene that instances the composed site under a baked
  `NavigationRegion3D`, spawns a first-person player at the crew start, and
  beacons the objective + extraction. This is the missing in-engine piece between
  "Lot composes a heist" and "walk the heist start to finish."
- Ships `godot/addons/lot/lot_player.gd` (a self-contained FPS walker — WASD /
  mouse / sprint / jump, no project input map needed) and
  `godot/addons/lot/lot_site_walk.gd` (bakes site nav, drops waypoint beacons +
  a HUD). Copy `addons/lot/` into your Godot project; the walk scene references
  `res://addons/lot/`.
- Crew-spawn / objective / extraction world positions are resolved at assemble
  time from the merged site gameplay and baked into the walk scene, so it needs
  no JSON parsing at runtime. Robust to heist branches that emit only
  objective/loot *arrays* (no objective marker): falls back to the array entry
  offset by the objective building's placement.
- `specs/vault_job.json` — flagship 3-building heist example: gas_station
  (approach/staging) -> bank (the vault) -> warehouse (escape), with a path
  triangle giving the objective two approaches. Heist gates pass; pacing reads
  short (intel only — the felt length is the vault-drill duration + AI pressure,
  which arithmetic can't see).
- The one thing only your in-engine walk confirms: navmesh quality across
  instanced buildings + outdoor, and multi-floor linking (a single baked region
  is ground-plane biased — upper floors need stairs bridged with nav-link
  anchors, the known Deli Counter caveat). `lot_site_walk.gd` documents the bake
  knobs to turn if AI nav looks wrong.
- Base `<name>.tscn` (composition) is unchanged — `--walkable` is purely
  additive.

## [0.7.0] - Compose .tscn buildings (scene-referenced, not just baked .glb)
- A building in the site spec may now be referenced by `scene` (a Godot `.tscn`
  that instances shared modules) instead of `glb` (a baked file). `scene` wins
  when both are given. Both are instanced the same way (a PackedScene
  ExtResource), so the site .tscn composes either.
- Why: Deli Counter's primary output is now the `.tscn` (greybox scene that
  references shared `res://art/zoo/` modules). Composing those at the site level
  means editing one shared module propagates across every building in the site,
  and theming applies at compound scale — the .glb path stays for self-contained
  shippable buildings.
- Backward compatible: `glb`-only specs are unchanged and byte-identical. The
  merged record now carries `source` (the resolved file) and preserves
  `glb`/`scene` as given. A building with neither is a spec error.
- gameplay.json merge, tactical, pacing, and enterability are untouched — they
  read merged data + footprints, not the geometry file. +2 tests (21 total).

## [0.6.0] - Site enterability gate (can you REACH the doors?)
- New site_enterability.py + a gate in assemble(): the approach-side sibling of
  site_tactical's connectivity gate. A building that's enterable on its own can
  be unenterable in a compound — its only door faces the perimeter, or a
  neighbour is parked against that face, or no path leads to it. Only Lot can see
  this, because only Lot knows the placements.
- GATE THE CLEAR-CUT CASE, WARN THE REST: HARD GATE (assemble refuses) when a
  building has real entries but EVERY one's approach is blocked by a neighbour's
  footprint or the perimeter — walled in. WARN when it's reachable but no
  authored path/courtyard leads to a clear entry, or when a building's own
  gameplay.json has no usable entry (a Deli Counter problem to fix there).
- Never auto-fixes (doesn't move buildings or reroute paths) and doesn't claim a
  clean pass means walkable — swing/vault clearance stays a walk-test fact. The
  per-building approach report attaches to the site gameplay.json under
  "enterability".
- Building records now carry `footprint` (from Deli Counter's gameplay.json) so
  the neighbour-overlap test works. Body-fit thresholds mirror Deli Counter's
  enterability.py.
- 3 new tests (walled-in gate, outside-perimeter, no-route warning); 19 pass.

## [0.5.1] - Rarity multi-entry follow-through
- Tracks Deli Counter 0.33.0: every opening (door/window/breach) now carries the
  building's rarity + a `building` id, so a building's multiple entry points all
  resolve to the same building + rarity through the merge. Lot already namespaced
  and building-tagged openings + markers, so this needed no core change — the
  newly-stamped windows simply flow through.
- Test updated: the window in the carry-through fixture is now stamped (a window
  breach is a valid entry attempt), and asserts its `building` tag survives.
- Tier name in test fixture aligned to `very_rare` / `legendary` (gold). 16 tests
  pass.

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
