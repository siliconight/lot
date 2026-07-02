# Lot — site assembler for Deli Counter buildings

Lot composes several already-built [Deli Counter](https://github.com/siliconight/deli-counter)
buildings into a single **site** — a PAYDAY-scale compound of multiple buildings
with space between them — which a single Deli Counter spec cannot make (Deli
Counter produces one monolithic building per spec).

Lot places each building on a shared ground, merges their gameplay data into one
site-level file, and emits a Godot scene that instances them. **It never
re-generates or edits the buildings.** Each stays an untouched, independently
re-buildable `.glb` — the disposable-`.glb` / iterate-the-spec loop keeps working
per building. Lot is a composition layer *above* the buildings; it consumes their
public contract (`.glb` + `.gameplay.json`), never their internals.

## Why a separate tool (thesis alignment)

This keeps Deli Counter's "we make models, not levels" line intact. Deli Counter
makes buildings; Lot makes sites. Each building remains a deterministic,
replication-free monolithic shell. The site is deterministic too — the same site
spec produces byte-identical output every run — but it's a *placement +
composition* of shells, not a new mega-building. Buildings are atoms; the site
spec is the molecule.

## Status: walkable site assembler (Phase 2 + tactical/pacing + city grain + traversal)

Since the Phase 2 baseline below, Lot has grown the pieces that make a site
actually *playable in one command*:

- **The whole pipeline (`cater.py`)** — one command from site spec to walkable
  Godot project: incremental headless Blender builds of stale buildings +
  facade shells, output copies, addon sync, `project.godot` bootstrap, then
  the assemble. See Usage.

- **Walk it (`--walkable`)** — emits `<name>_walk.tscn`: the whole site under a
  baked `NavigationRegion3D`, a first-person player at the crew start, and
  objective/extraction beacons + HUD. Open it and press F6 to walk the level.
- **No Blender needed (`--preview`)** — buildings render as labeled greybox
  *massing* (a walkable pad + a see-through box) with the real heist anchors
  pulled from each building's Deli Counter **spec**, so you can lay out and walk
  a whole level before any building is built in Blender. One command, zero
  Blender.
- **City grain (`roads` + `blockers`)** — flat asphalt `roads` with optional
  raised sidewalks, and solid `blockers` (StaticBody3D massing you can't enter)
  to wall streets and funnel the crew toward the heist fronts. A `blocker` can
  also point at a Deli Counter **facade shell** (`glb`/`scene`) so a street wall
  becomes themed facades instead of plain boxes (dormant until the art pass).
- **Step-up player** — `lot_player.gd` now auto-steps curbs, sidewalks, ledges,
  and steep stair noses (so the 0.11 raised sidewalks don't catch you).
- **Nav-QA feed (`--navqa`)** — emits a scene wired to feed an in-engine nav-QA
  bot harness (decoupled: opens and walks with or without that addon present).

Deli Counter makes the buildings; Lot composes them into a PAYDAY-scale **site**
and lets you walk it. A heist level = 1–4 Deli Counter buildings = one Lot site.

---

### Phase 2 baseline

**Phase 1 (done):** deterministic placement + ground manifest + merged,
world-offset, namespaced `gameplay.json` + a generated Godot `.tscn` that
instances each building at its placement. No geometry merging — buildings stay
separate files, composed at load time.

**Phase 2 (done):** box-vocabulary outdoor — a real ground slab, paths,
courtyards, perimeter walls, and cover — generated as Godot primitive nodes
(`BoxMesh` + `BoxShape3D` collision), NOT a baked `.glb`. This keeps Lot offline
(no Blender needed) and blockout-honest: strictly axis-aligned boxes and flat
regions (flat strips, rectangular regions, crates). No terrain.

Real terrain / organic outdoor is explicitly **out of scope** — that would break
the monolithic/deterministic thesis and belongs to a separate terrain tool your
assembled site sits inside.

**Building rarity (carried through):** if a building was built with a Deli
Counter `rarity`, each `buildings[]` entry in the merged site `gameplay.json`
gains `rarity` + `rarity_color`, and the stamped entry openings (door/window/breach) pass through untouched — so a compound carries a per-building rarity index and every
networked door pops its building's colour. Lot doesn't assign rarities itself;
each comes from its building's spec. (See Deli Counter's `docs/RARITY.md`.)

## Outdoor (Phase 2) spec fields

All optional. Added alongside `buildings`:

```json
{
  "paths": [
    {"from": "bank", "to": "warehouse", "width": 4}
  ],
  "courtyards": [
    {"at": [20, -15], "size_x": 16, "size_y": 12}
  ],
  "perimeter": {"height": 3},
  "cover": [
    {"at": [10, -5]},
    {"at": [30, 5], "size": [2, 1, 1]}
  ]
}
```

- `paths` — flat strips between two buildings (`from`/`to` building ids) or
  explicit endpoints (`a`/`b` as `[x,y]`), with a `width`. Rendered as a yaw'd
  box following the line between them.
- `courtyards` — flat rectangular regions at `at` with `size_x`/`size_y`.
- `perimeter` — four walls around the ground footprint at the given `height`.
- `cover` — 1m crates (or custom `size`) at positions. Reuses the crate
  vocabulary.

## Tactical layer (pathing + the three modes, at site scale)

Lot understands reachability and the three level modes the same way Deli Counter
does — just one scale up:

```
Deli Counter:  reachability + modes  WITHIN a building   (rooms, doors)
Lot:           reachability + modes  ACROSS the site      (buildings, paths)
```

It analyzes what you **declared** — the buildings and the `paths` between them,
plus the merged markers — never a computed navmesh. This is intel plus light
gates, deterministic and offline. The in-engine walk stays the real validator (an
offline graph can't prove you can physically cross a courtyard; it can prove you
never declared a route to a building at all).

**Intel** (never fails the build), emitted into the site `gameplay.json` under
`tactical`: the site connectivity graph, **isolated-building detection** (the
site echo of Deli Counter's "no isolated rooms"), spawn→objective distance, and
the count of distinct approaches to the objective.

**Gates** (fail the build) — only when you declare a site `mode`:

```json
{
  "mode": "heist",
  "spawn": "bank",
  "objective": "warehouse",
  "extraction": "warehouse"
}
```

- `assault` — the `objective` building must be reachable by **≥2 distinct
  approaches** (multiple routes in — the site echo of an assault objective room
  needing ≥2 access).
- `heist` — `spawn → objective → extraction` must be path-connected.
- `survival` — the `safe` building must be path-connected to the holdout
  (`objective`).

The `objective` / `spawn` / `extraction` / `safe` fields are building-id
designations. With no `mode`, you get pure intel and no gates. These designations
also answer "which building's objective is *the* site objective."

## Enterability (can you REACH the doors?)

Deli Counter guarantees each building is enterable on its own. Lot checks the
thing only it can see: once placed, can you actually get *to* a building's
entries? It's the approach-side sibling of the tactical gate, same rule — **gate
the clear-cut case, warn the rest**. A building whose every entrance is blocked
by a neighbour's footprint or the perimeter wall is *walled in*, and `assemble`
refuses it (with a message telling you to move it, rotate it so an entry faces
open ground, or clear the approach). Softer cases — reachable but with no
authored path/courtyard leading to a clear entry — warn. It never moves your
buildings or reroutes paths, and a clean pass means "the spec doesn't wall it
in," not "certified walkable" (swing/vault clearance is a walk-test fact). The
per-building approach report attaches to the site gameplay.json under
`enterability`.

## Pacing estimate & encounter intel

Two structural analyses that help you judge **how long** a compound plays and
**where** its combat opportunities are — without pretending to measure fun. Fun
is a feel property only a playthrough reveals; these describe structure, and
every number is shown as an estimate from declared inputs, never a verdict. This
is not a simulation — no agents move, no shots fire.

**Pacing** estimates time-to-complete for the mode's critical route as a
min/expected/max range, checked against a target window (default **7–15 min**,
overridable). It sums traversal (path lengths ÷ move speed), setup, objective
work, loot trips, and survival holdout time — with a transparent breakdown that
adds up to the estimate. Emitted under `pacing` in the site gameplay.json, plus a
status line: *within target* / *too short* / *too long* / *straddles the window*.

Timings are **derived from the mode + distances** and individually overridable:

```json
{
  "pacing": {
    "move_speed": 4.0,
    "objective_secs": 120,
    "wave_secs": 35,
    "waves": 6,
    "target_minutes": [7, 15]
  }
}
```

So you might see *"~2.7 min, likely TOO SHORT vs target — travel 12s, objective
120s"* and respond by spreading the buildings out, adding objectives, or
lengthening the holdout — in the same iterate-the-spec loop.

**Encounter intel** reports per-leg geometric **facts** under `encounters`: route
length, distinct approaches, open-ground distance, and nearby cover count. It
describes *opportunity*, not quality — it never grades a firefight. Whether a leg
plays well is for the walk to tell you.

## Site spec

```json
{
  "name": "big_oil",
  "ground": {"size_x": 120, "size_y": 80},
  "buildings": [
    {"id": "bank",      "glb": "bank.glb",      "gameplay": "bank.gameplay.json",
     "at": [0, 0],   "rot": 0},
    {"id": "warehouse", "glb": "warehouse.glb", "gameplay": "warehouse.gameplay.json",
     "at": [45, 10], "rot": 90}
  ],
  "site_markers": [{"type": "extraction", "at": [60, -30]}]
}
```

- `at` is the building's `[x, y]` position on the site ground (metres, same
  convention as Deli Counter).
- `rot` is yaw in degrees about the building's origin.
- Each building references a `.glb` and its `.gameplay.json` (Deli Counter
  output).

### Referencing a `.tscn` building (scene-composed)

A building may instead be referenced by `scene` — a Godot `.tscn` Deli Counter
emits with `--format tscn`, which instances shared modules from
`res://art/zoo/`:

```
{"id": "bank", "scene": "bank.tscn", "gameplay": "bank.gameplay.json",
 "at": [0, 0], "rot": 0}
```

`scene` takes precedence over `glb` when both are present; a building needs one
of them. Both are instanced the same way in the site `.tscn`. Composing `.tscn`
buildings means editing one shared module propagates across every building in the
site, and theming applies at compound scale — the baked `.glb` stays the
self-contained, single-file option. Everything else (the merged `gameplay.json`,
tactical, pacing, enterability) is identical either way.

## Usage

### The whole pipeline, one command (`cater.py`, 0.15+)

`cater.py` sits above lot.py and runs the full spec→Godot flow: it finds the
Deli Counter repo, headless-builds every **stale** building and every
blocker-referenced facade shell (incremental — only when a `.glb` is missing
or older than its spec), copies each `.glb` into the Godot project and each
`.gameplay.json` next to the site spec, syncs `godot/addons/lot`, writes a
minimal `project.godot` if the target folder is fresh, then runs lot.py:

```
python cater.py specs/gs_heist.json "C:\path\to\GodotProject"

  --preview       no Blender: buildings box from their specs (same command,
                  Blender-free machine)
  --blender PATH  blender executable (else $BLENDER / PATH / DC's guesses)
  --dc PATH       Deli Counter repo (else $DELI_COUNTER / ../deli_counter /
                  C:\Projects\deli_counter)
  --force-build   rebuild everything even if fresh
  --skip-build    no Blender launch; copy existing DC outputs + assemble
```

Edit any spec, re-run the same command; only what changed rebuilds. Everything
below is the underlying step cater automates — reach for lot.py directly when
you want just the assemble.

### Site packs: sharing a level with collaborators (`package.py`)

The deliverable for someone integrating your level into THEIR game is a
**site pack**: one self-contained folder they can drop at any path inside
their Godot project and instance -- the composed `<site>.tscn` (all refs
relative), every instanced `.glb`, the merged `site.gameplay.json` (the
integration contract: spawns, rooms, objectives, loot, zones, per-door
rarity anchors), a PACK_README stating that contract, and a self-contained
QA walk scene (F6, no addon install). Deliberately a folder of source, not a
`.pck` -- teammates need inspectable, re-importable assets.

Packs are **reproducible releases**: the site spec's own `"version"` names
the zip (`gs_heist_pack_v0.1.0.zip` -- bump it per walked release),
`pack.manifest.json` records the spec hash, every file's sha256, and each
.glb's Deli Counter build provenance, and the zip is deterministic (identical
inputs -> byte-identical zip, sidecar `.sha256`).

#### Cutting a release, start to finish

1. **Build + walk.** Get the level into your own Godot project and validate
   it on foot -- full route, every entry, extraction:

   ```
   python cater.py specs/gs_heist.json "C:\path\to\YourProject"
   ```

   (F6 `gs_heist_walk.tscn`. If anything snags, fix the DC building spec or
   the site spec and re-run -- only what changed rebuilds.)

2. **Version the cut.** In the site spec, set or bump the level's own
   version -- this is the release number collaborators will see:

   ```json
   { "name": "gs_heist", "version": "0.2.0", ... }
   ```

3. **Cut the pack**, recording what you validated:

   ```
   python package.py specs/gs_heist.json --note "walked full route + all entries 2026-07-01"
   ```

   -> `dist/gs_heist_pack_v0.2.0.zip` + sidecar `.sha256`. (Or do steps 1
   and 3 in one command: `cater ... --package --note "..."`. Missing .glbs
   fail loudly with the command that builds them.)

4. **Send the zip** (the `.sha256` too, if you want receipts). Their side:
   unzip anywhere inside their Godot project (e.g. `res://levels/`), let the
   import pass finish, instance `<site>.tscn`, bind game code to
   `<site>.site.gameplay.json`. `PACK_README.md` inside the pack tells them
   all of this; `<site>_walk.tscn` gives them an F6 tour with zero setup.

Re-cutting with identical inputs reproduces the identical zip, so the
`.sha256` alone identifies a release; any content change without a version
bump shows up as a hash mismatch.

### The assemble step (`lot.py`)

```
python lot.py specs/big_oil.json [out_dir]
```

**Flags** (combine freely):

```
# walk the level in one command, no Blender — greybox massing + the real anchors:
python lot.py specs/vault_job.json "C:\path\to\GodotProject" --walkable --preview
# then open <name>_walk.tscn in Godot and press F6.

  --walkable   also emit <name>_walk.tscn (navmesh + first-person player + beacons)
  --preview    buildings as labeled greybox massing from their DC spec (no .glb / no Blender)
  --navqa      also emit <name>_navqa.tscn (feeds an in-engine nav-QA bot harness)
```

Writes:
- `<name>.site.gameplay.json` — every building's markers, rooms, objectives,
  loot, zones, surfaces, and surface_roles, **offset to world space and
  namespaced by building id** (so `bank/attacker_spawn` and
  `warehouse/attacker_spawn` don't collide). This merge is the high-value core:
  it's the genuinely fiddly-by-hand part, done deterministically.
- `<name>.tscn` — a Godot scene instancing each building `.glb` at its placement,
  with a ground body. Buildings stay separate assets referenced by path, so
  rebuilding one building just updates its `.glb` in place.

## How it fits the workflow

1. Build each building with Deli Counter (`spec -> .glb + .gameplay.json`).
2. Write a site spec placing them.
3. `python lot.py site.json` -> assembled scene + merged gameplay.
4. Open the `.tscn` in Godot; the compound is there, walkable.
5. Iterate: change a building's spec, rebuild it, the site picks up the new
   `.glb` at its placement. Change placement, re-run Lot.

Per-building determinism and the fast iterate-the-spec loop are preserved; the
site is just another deterministic layer on top.

## Axis mapping

Deli Counter is metres, Z-up; Godot is Y-up. Lot maps site ground XY -> Godot XZ
and site height Z -> Godot Y, with yaw about site-Z becoming yaw about Godot-Y.
The merged `gameplay.json` keeps Deli Counter's Z-up world convention (so it
matches each building's own data); the `.tscn` transforms are in Godot's frame.
