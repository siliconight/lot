# gs_heist — gas-station street-corner heist (site notes)

Built to the "Gas Station Heist Level Requirements" doc. Small, readable,
playable first: 2 enterable buildings, 2 facade shells, 1 street, 1 walk.

## The map (site coords, X east / Y north; ground 110 x 90)

```
 y=+40 ─┬────────────── north blocker row ──────────────┬─
        │  west     ┌──────────────┐  rear alley        │
        │  loop     │  GS STATION  │(roll door/breach)   │
        │   lane    │  32x22 @0,16 │   ┌───────────┐    │
        │ [blocker] │ office/safe NE│   │ AUTO SHOP │    │
        │           │              │   │ 26x18     │    │
        │           └──front doors─┘   │ @40,12    │    │
        │             forecourt        │ rot 270   │    │
        │             pump islands     │ bay faces W│   │
        │    cars →   (from DC spec)   └───────────┘    │
 y=-16 ═╪═══════════ road (10 m + 3 m sidewalks) ═══════╪═
        │ [EXTRACT]│storefront│ SPAWN │filler│rowhome│fill│
 y=-45 ─┴──pocket──┴──facade──┴alcove─┴──────┴facade─┴───┴─
       x=-55                                          x=+55
```

## The loop (requirements' heist flow)

1. Crew spawns in the south alcove (`crew_spawn` site marker, [-17,-28])
2. Cross the road + sidewalks, through the pumps — **approach beat**
3. Enter: 2 front doors, W service door, E stock door, N office door,
   N roll door, N soft-wall breach, vault window (10 valid entries)
4. Register grab (sales floor) → safe drill (NE back office)
5. Street pressure: responder spawns at both road ends + rear alley,
   horde spawns at shop apron + west road — **mid-heist beat**
6. Optional: the auto shop across the east lane — `very_rare` (purple
   #A335EE) on every one of its 12 openings; bay door faces the station
   so the crew *sees* the choice
7. Carry out SW across the road into the extraction pocket ([-43,-30],
   diagonal from the objective) — **extraction beat**

## Deliberate choices

- Auto shop objective is `required: false` — the level completes without it
  (its own spec was edited; it is *this site's* side score).
- Station rarity left unset for contrast with the purple reveal.
- Parked cars ON the road break the 106 m sniper lane; the road crossing
  itself is the "bad idea" open area.
- Pacing model inputs in the spec: target 7-12 min (from the requirements
  doc), objective_secs 150 (defended objective, not machine time).
  Estimate ~6.4 min expected, 4.1-8.6 range — a compact site straddling the
  window is honest; the walk is the real check.
- `--out-dir/` at the Lot repo root looks like stale accidental output from a
  past run (positional out_dir eaten by a flag-looking arg) — candidate for
  deletion before commit.

## Run it (Godot 4.7, no Blender)

    Copy-Item -Recurse godot\addons\lot "C:\path\to\GodotProject\addons\lot"
    python lot.py specs\gs_heist.json "C:\path\to\GodotProject" --walkable --navqa --preview

Open `gs_heist_walk.tscn`, F6. Nav-QA scene needs the heist_nav_qa addon.

## Upgrade to real interiors (per building, later)

    cd C:\Projects\deli_counter
    python build.py specs\gs_corner_station.json
    python build.py specs\gs_auto_shop.json
    python build.py specs\gs_facade_rowhome.json
    python build.py specs\gs_facade_storefront.json

Copy each `.glb` + `.gameplay.json` next to the site spec (gameplay files into
`gs_heist_buildings/`), then re-run the same lot.py command **without**
`--preview`. Facade shells land on the two street blockers automatically (their
`glb` refs are already wired).
