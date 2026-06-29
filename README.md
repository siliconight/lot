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

## Status: Phase 2 + site tactical + pacing layer

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

```
python lot.py specs/big_oil.json [out_dir]
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
