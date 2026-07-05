## [0.18.0] - Site lighting: merge building lights + exterior streetlights

- merge_lights(): merges every building's <name>.lights.json into one
  <site>.site.lights.json -- each anchor offset to world space and id-namespaced
  by building (mirrors merge_gameplay's offset+rotation+namespacing), plus the
  exterior lights Lot owns. Deterministic; consumed by Lux's light-anchor loader
  exactly like a single building's manifest. Written in assemble() next to
  .site.gameplay.json and .tscn.
- Exterior streetlights Lot derives (Deli Counter can't see outdoors): a
  streetlight row down each path (angle + count from the road), and a ring
  around the ground perimeter (one row per edge).
- Building lights resolved via each building's 'gameplay'/'glb' ref
  (<name>.lights.json), or an explicit 'lights' field; missing files skip
  cleanly. specs/bank.lights.json + warehouse.lights.json added for the demo.
- 4 new tests (35 total).

## [0.17.2] - primos_demo: the showcase site (Deli Counter PoC staging)
- specs/primos_demo.json + specs/primos_demo_buildings/: "Primo's Pizza &
  Social Club" (DC 0.59.0's showcase spec) staged as a one-building demo
  site. All green in preview end-to-end: site_audit 0 HIGH / 0 MED (three
  responder waves at true thirds around the building, backstopped spawn
  and exfil on opposite corners, parked-car cover along both legs), heist
  gates passed, pacing within target, walk scene emits all three climb
  volumes (cellar, dumbwaiter, roof), drift check clean vs DC.
- DEMO_PRIMOS.md: the one-command recipe -- cater --package cuts the
  shareable pack (dist/primos_demo_pack_v0.1.0.zip) on any machine with
  Blender.

## [0.17.1] - Spec drift guard + the gs_auto_shop copy actually synced
Found in the wild: the Lot copy of gs_auto_shop.json was still the
pre-0.56.0 spec (swapped story-1 axis, 1.1 m door, no parapet) -- the DC
fix never crossed the manual copy step, and the pipeline rebuilt and even
PACKAGED the broken upper floor without a peep. Two fixes:

- specs/gs_heist_buildings/gs_auto_shop.json is now the fixed DC spec
  (axis X, 1.4 m upper door, roof parapet). Run cater with --force-build
  so the auto_shop glb rebuilds from it.
- cater now hash-compares every building/blocker spec in the site folder
  against Deli Counter's spec of the same name and prints a loud SPEC
  DRIFT warning with the exact copy command when they differ. Warning,
  not a gate: freezing a level is a valid choice, but it should be a
  choice, not an accident.

## [0.17.0] - site_audit.py: the genre grammars between the buildings
Deli Counter 0.58.0 gave buildings the PayDay 2 / Ready or Not / L4D2 rule
packs; this is the same idea at site scale -- the run across open ground.
Report-only, printed at the end of every lot.py assembly; the walked
gs_heist sweeps 0 HIGH / 0 MED (calibration), with three fair INFOs (two
road crossings, few horde spawns).

- S_BACKTRACK (PayDay exfil shape): extraction within 18 m of the crew
  spawn AND within 35 deg of the entry bearing = the escape rewinds the
  entry. Same-side-different-corner passes (gs_heist does).
- S_RESPONDER_ARC / S_RESPONDER_CAMP (PayDay pressure): all responder
  spawns inside one arc = one-note waves; a responder spawn within 12 m of
  an anchor = spawn camping by construction.
- S_NAKED_ANCHOR (L4D2 safe anchors): spawn/extraction with no cover or
  building/blocker edge within 8 m. Blockers use their real size_x/size_y
  extents (the gs spawn alcove's south wall counts, as it should).
- S_BARE_LEG (L4D2 rhythm): critical legs >= 20 m with zero cover in a
  6 m corridor are sprints, not fights.
- S_STREET_CROSS (CQB at site scale, INFO): every road crossing on a
  critical leg is an exposure moment, reported per crossing.
- S_HORDE_ARC / S_FEW_HORDE and S_ONE_APPROACH (site-graph route
  diversity via site_tactical) where they apply.
- Wired into lot.py after pacing; standalone CLI: python site_audit.py
  specs/x.json [--json]. Tests: 30 -> 31.

## [0.16.1] - Ladders work in the site walk (Lot adopts its half of the contract)
Stairs worked, ladders didn't -- and it was NOT the .glb. DC's ladder contract
has three legs: DC bakes the LADDER_ anchor + climb metadata into the
glb/gameplay (working); a post-import turns the anchor into an Area3D climb
volume (only runs in projects with the DC addon -- cater projects don't have
it); the player implements climb mode (lot_player had none). Stairs are pure
geometry (the DC 0.51 ramp collider rides inside the glb), which is exactly
why they worked and ladders didn't.

- The generated walk scene now emits an Area3D climb volume (group "ladder")
  per gameplay ladder marker, placed through the building transform, sized
  like deli_counter_postimport.gd (+1 m dismount lip, base-anchored,
  generous square footprint so building rotation can't turn it edge-on).
- lot_player.gd gains climb mode, ported from DC's reference player: climb
  along where you LOOK (look up + W ascends, look down descends, look level
  + W steps off at the top), no gravity on the ladder, Space drops.
- Preview parity: preview.gameplay_from_spec synthesizes ladder markers from
  the spec's ladders array (mirrors deli_counter.py _ladders), so ladders
  work in --preview too, not just after a Blender build.
- Tests: 29 -> 30 (preview synthesis, volume placement/sizing/load_steps,
  player climb present).

## [0.16.0] - Site packs: the shareable deliverable for collaborators
`package.py` cuts a drop-anywhere folder-of-source (zipped) that a
collaborator can put at ANY path inside their own Godot project and instance
-- deliberately NOT a .pck (that's Godot's opaque runtime-DLC container;
teammates need inspectable, re-importable source).

- `python package.py specs/<site>.json` -> `dist/<site>_pack_<ver>.zip`
  containing: the composed `<site>.tscn` with RELATIVE ext_resource refs
  (works at res://levels/, res://maps/x/, anywhere), every instanced .glb
  (buildings + facade shells, resolved from next-to-spec then DC build/),
  `<site>.site.gameplay.json` (the integration contract), a PACK_README.md
  stating the contract (marker/opening/rarity semantics, axis mapping, the
  once-per-building reveal rule), and a self-contained QA walk scene with
  its two scripts copied in -- F6 with zero addon install.
- New `portable=True` mode on `write_godot_scene` / `write_walk_scene` /
  `write_navqa_scene`: relative refs instead of res://. Defaults unchanged.
- Missing .glbs fail loudly with the cater command that produces them; no
  --preview on purpose (a pack of massing boxes is not a deliverable).
- `cater.py --package`: cut the pack in the same one command, after the
  builds + assemble.
- **Reproducible releases:** the site spec gains a per-LEVEL `"version"`
  field -> pack named `<site>_pack_v<site_version>.zip` (bump it per walked
  release; the tool nudges if unset). Every pack carries
  `pack.manifest.json`: site spec sha256, per-file sha256 + sizes, each
  .glb's Deli Counter build provenance chained through (kit_version, spec
  hash, built_utc from the sibling DC manifest), the gate summary
  (pacing status, entries clear), and an optional `--note` ("walked full
  route ..."). The zip itself is DETERMINISTIC -- sorted entries, fixed
  timestamps, no build-time stamp anywhere -- so identical inputs give a
  byte-identical zip; a sidecar `.sha256` identifies the release.
- `cater.py --package --note "..."` passes the release note through.
- `gs_heist` site spec versioned `0.1.0` (first walked cut).
- Tests: 26 -> 29 (portable ref emission; pack contents + relative refs +
  missing-asset gate; deterministic release: byte-identical rebuilds,
  manifest hash integrity, provenance chain, sidecar).

## [0.15.1] - Lit walk/nav-QA scenes (the runtime was rendering unlit)
The generated `*_walk.tscn` / `*_navqa.tscn` carried no light and no
environment — in the editor the preview sun hid it, but at F6 the whole site
rendered as near-black flat mush (real .glb materials under zero light). DC's
own walk harness has always carried a proper rig, which is why solo building
walks looked right and site walks didn't.

- Both generated scenes now embed the exact rig from DC's
  `template/level_test.tscn`: shadowed `DirectionalLight3D` (same transform) +
  `WorldEnvironment` (ProceduralSky, sky ambient 0.6, filmic tonemap) — a Lot
  site walk lights identically to a DC building walk.
- `lot_site_walk.gd` HUD title is no longer a hardcoded "VAULT JOB": new
  `site_title` export, baked in by Lot from the site's name.
- Tests: 25 -> 26 (rig present in both scenes; load_steps stays in sync with
  the resource count; title baked).

## [0.15.0] - `cater.py`: site spec -> walkable Godot project, one command
The whole gs_heist hand-flow, codified. `python cater.py specs\<site>.json
"C:\path\to\GodotProject"` does everything the hands did: finds the Deli
Counter repo (--dc / $DELI_COUNTER / sibling ../deli_counter /
C:\Projects\deli_counter), builds every stale building AND every
blocker-referenced facade shell in headless Blender (incremental: only when
the .glb is missing or older than its spec; --force-build overrides), copies
each .glb into the project and each .gameplay.json next to the site spec,
syncs godot/addons/lot, writes a minimal Godot 4.7 project.godot into a fresh
folder, and runs lot.py (--walkable --navqa).

- `--preview` skips Blender + copies entirely — the same one command works on
  a machine with no Blender at all.
- `--skip-build` copies existing DC outputs + assembles (no Blender launch).
- Blocker shells map by stem (gs_facade_storefront.glb -> DC
  specs/gs_facade_storefront.json); a ref with no matching DC spec is assumed
  hand-made and reported, not fatal. Reused shells dedupe to one build.
- Missing outputs after the build phase fail loudly with the exact filenames;
  a failed Blender build stops the pipeline without touching what's already
  fresh.
- Tests: 23 -> 25 (incremental build decision; facade shell job mapping).

## [0.14.0] - Site-level heist staging + preview parity (rarity, openings) + `gs_heist`
Where the crew stages, where the cops arrive, and how long the route takes are
SITE concerns — a building's own spec shouldn't have to know street layout.
Plus two preview gaps closed: preview now speaks the same gameplay contract a
Blender build does, so the rarity index and the walled-in gate work in exactly
the mode where you're shuffling placements.

- `site_markers` gain `crew_spawn`: overrides building spawn markers for the
  walk scene (symmetric with the existing site-level `extraction` marker) and
  joins the nav-QA player proxies.
- `site_markers` gain bot spawns (`responder_spawn` / `horde_spawn` /
  `defender_spawn`): cop pressure arrives from the STREET — road ends, alleys —
  and now feeds the nav-QA harness without touching any building spec.
- `site_pacing` travel legs honor the site-level `crew_spawn` / `extraction`
  markers as route endpoints (building `at`s remain the fallback, so sites
  without the markers estimate byte-identically). Fixes the degenerate 0 m legs
  when spawn/objective/extraction all name the same building.
- `preview.gameplay_from_spec` stamps building `rarity` + `rarity_color`
  (mirror of the published DC contract table, docs/RARITY.md) and synthesizes
  exterior-wall `openings` from the spec (per-kind defaults mirror
  `spec_types.Opening.resolved()`), each carrying the building rarity. The
  site rarity index + `site_enterability`'s walled-in gate now work
  pre-Blender.
- New shipped site: `specs/gs_heist.json` — gas-station street-corner heist
  (2 enterable buildings, 2 facade-shell blockers, road + sidewalks, extraction
  pocket + spawn alcove in the south street wall, 10 cover pieces, 5 street bot
  spawns). Assembles clean: gates pass, 10+12 valid entries all clear, rarity
  `very_rare` on the auto shop end-to-end.
- Tests: 21 -> 23 (site crew_spawn resolution + nav-QA proxies; preview rarity
  contract).


## [0.13.0] - lot_player step-up (curbs, ledges, steep stairs)
- lot_player.gd now auto-steps short near-vertical obstacles after move_and_slide:
  raised sidewalks/curbs (0.11 roads), ledges, and steep stair noses it used to
  catch on. Raycast-probe step-up with a valid-direction check (only steps when
  walking INTO a face, not along it) and a head-clearance check (won't climb under
  low geometry). `max_step_height` export (default 0.45 m). Adapted from the
  standard FPS step-climbing approach; the DC stair RAMP collider (DC 0.51) still
  carries normal stairs, so this is for the curbs/ledges/steep cases.
## [0.12.0] - Blocker facade-shell hook (ready for the art pass; dormant now)
- A `blocker` may now carry an optional `glb` or `scene` ref (a DC facade shell),
  exactly like a real building. When present it's instanced at the blocker's
  placement instead of drawing a plain box; when absent it falls back to the box
  you have today, so every existing blocker is byte-identical.
- In `--preview` the shell is ignored and the blocker boxes — preview stays
  Blender-free and blockout-honest.
- Nothing in the shipped `vault_job.json` uses this yet. It's the hook so that,
  at art-pass time, DC can make a small family of cheap exterior-only facade
  shells (rowhome / storefront / industrial wall — collision + walls + windows,
  no interior, no gameplay markers, no nav) and the street's filler reuses them
  by reference, themed to match the heist buildings. DC makes the shells; Lot
  places them. Box-vocab stays Lot's; facade detail stays DC's.
- Additive; 21 tests unchanged.

## [0.11.0] - City grain: `roads` + `blockers` (street walls that guide the player)
- `roads`: flat asphalt strips with optional raised concrete `sidewalk`s, drawn
  between two points (`a`/`b` or `from`/`to` building ids). The street spine the
  block fronts onto -- DELCO/Philly grain instead of buildings floating in a
  field. `{ "a": [-90,-28], "b": [90,-28], "width": 10, "sidewalk": 3 }`.
- `blockers`: non-interactable filler buildings -- SOLID collision massing you
  cannot enter (`{at, size_x, size_y, height, rot?, color?}`). They wall the
  street and channel the player toward the real, enterable heist buildings. The
  deliberate contrast does the guiding: solid block = context you route around,
  see-through massing = a building you go into.
- `_box_node` / `_yaw_box_node` gained an optional `color` (a StandardMaterial3D
  override); roads/sidewalks/blockers are tinted, existing ground/path/cover are
  byte-identical (color defaults off).
- `specs/vault_job.json` rebuilt as a real city block: the three heist buildings
  front a main street; a row of rowhome blockers walls the far side and the backs,
  with alley gaps aligned to the building fronts so you're funneled down the
  street and into the heist buildings. Zero footprint overlaps; gates pass; 2
  objective approaches.
- All additive: composition, `--walkable`, `--navqa`, `--preview`, and 21 tests
  unchanged.

## [0.10.0] - `--preview`: walk the level with no Blender, one command
- `python lot.py <site>.json <out> --preview` composes the site with each
  building as labeled greybox **massing** (a walkable footprint pad + a
  see-through box you walk through + a floating id label) instead of a real
  `.glb`. The heist's real anchors (crew spawn / vault / extraction / cover /
  cop spawns) come from each building's Deli Counter **spec** via a bpy-free
  shim (`preview.py`), so `--walkable` and `--navqa` work fully — you walk the
  *level* (placement, routes, scale, nav, the flow) before building any geometry.
- Collapses the old five-step "build 3 buildings in Blender, shuffle 6 files,
  assemble, copy addons, open" down to: copy the addon once, run one command,
  open the scene. See `QUICKSTART.md`.
- A building record may now carry `"spec": "<dc_spec>.json"` (the JSON
  `new_level.py` writes without Blender). `--preview` reads it, synthesizes a
  `<id>.preview.gameplay.json` next to it (never clobbers a real `.gameplay.json`
  from a Blender build), and boxes the footprint. `specs/vault_job_buildings/`
  ships the three 0.49 building blockouts for the flagship example.
- `preview.py` is the one place Lot peeks at Deli Counter's authoring *spec*
  rather than the public `gameplay.json` contract — preview-only, mirrors the
  marker/room/objective shape, no acoustic surfaces, not authoritative. Swap in
  the Blender builds (set `glb`/`scene`, drop `--preview`) for the real walk.
- Non-preview composition, `--walkable`, `--navqa`, and all 21 tests are
  unchanged; `--preview` is purely additive.

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
