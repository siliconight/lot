# Quickstart — walk the vault job (no Blender)

## The one command (0.15+)

`cater.py` runs the whole pipeline — Blender builds (only what's stale),
output copies, addon sync, a fresh `project.godot` if the folder is empty,
and the Lot assemble:

    python cater.py specs\gs_heist.json "C:\path\to\GodotProject" --blender "C:\blender\blender.exe"

Add `--preview` on a machine with no Blender (buildings box from their specs).
Then open `<site>_walk.tscn` in Godot, F6. Edit any spec, re-run the same
command; only what changed rebuilds. The sections below are the manual steps
cater automates, kept for when you want just one of them.

You don't need to build anything in Blender to get into the level. `--preview`
boxes each building as labeled greybox massing and pulls the real heist flow
(crew spawn → vault → extraction, cover, cop pressure) straight from the Deli
Counter building *specs*. Walk the **level** — placement, routes, scale, nav —
now; swap in the detailed Blender buildings later.

## One-time setup
Copy into your Godot project's `addons/` folder:
- `lot/godot/addons/lot/`            (required — the player + harness)
- `addons/heist_nav_qa/`             (optional — only for the bot QA scene)

## Every time (one command)
From the `lot/` folder, point the output at your Godot project:

    python lot.py specs/vault_job.json "C:\path\to\GodotProject" --walkable --navqa --preview

Then in Godot open one of:
- `vault_job_walk.tscn`  → press play, walk it (WASD / mouse / Shift / Space, Esc frees the cursor)
- `vault_job_navqa.tscn` → press play, watch 16 cop bots stress-test it; report lands in `user://nav_qa_reports/`

That's it. Edit `specs/vault_job.json` (move a building, change a path, swap a
preset), re-run the one command, reopen. No Blender, no file shuffling.

## Make a *different* heist
1. Generate building specs (no Blender), one per building:

       python ..\deli_counter\new_level.py --preset casino_tower --name casino_tower

   Drop the resulting `.json` into `specs/<your_buildings>/`.
2. Copy `specs/vault_job.json` to `specs/<your_site>.json`, list your buildings
   with `"spec": "<your_buildings>/<id>.json"`, set `spawn` / `objective` /
   `extraction`, place them with `at`, and draw `paths` between them.
3. `python lot.py specs/<your_site>.json "C:\path\to\GodotProject" --walkable --navqa --preview`

## Upgrade to detailed interiors (later, per building)
When you want real walkable interiors instead of massing boxes:
1. Build the buildings in Deli Counter (Blender): `python build.py specs/<id>.json`
   → produces `<id>.glb` + `<id>.gameplay.json`.
2. Put those next to the site spec and set each building's `glb` (or `scene`).
3. Drop `--preview`. Everything else (the command, the scenes) is identical.
