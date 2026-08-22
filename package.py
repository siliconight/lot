#!/usr/bin/env python3
"""
package.py  --  build a shareable SITE PACK from a Lot site spec
================================================================
The deliverable for collaborators: one self-contained, drop-anywhere folder
they can put at ANY path inside their own Godot project and instance. Not a
.pck (that's Godot's opaque runtime-DLC container, wrong for teammates who
need to inspect, re-import, and re-theme source assets) -- a folder of source:

    <site>_pack/
      <site>.tscn                  the composed site (RELATIVE refs -> works
                                   at res://levels/, res://maps/x/, anywhere)
      <building>.glb ...           every building + facade shell it instances
      <site>.site.gameplay.json    the integration contract: spawns, rooms,
                                   objectives, loot, zones, per-door rarity
                                   anchors, tactical/pacing intel
      PACK_README.md               how to instance + how to bind to the data
      <site>_walk.tscn             self-contained QA: F6 to walk the pack
      lot_site_walk.gd, lot_player.gd   (copied in; no addon install needed)

USAGE
-----
    python package.py specs/gs_heist.json                # -> dist/<site>_pack_<ver>.zip
    python package.py specs/gs_heist.json --out somedir
    python package.py specs/gs_heist.json --keep-folder  # also leave the folder

.glb resolution order per building/shell: next to the site spec, then the
Deli Counter build/ folder (found like cater.py finds it). Missing .glbs fail
loudly with the cater command that produces them -- a pack of preview boxes
is not a deliverable, so there is no --preview here on purpose.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lot                      # noqa: E402
from version import LOT_VERSION  # noqa: E402
from cater import find_dc        # noqa: E402


def _pack_sources(site_spec):
    """Every geometry file the site instances: building sources + blocker
    shells, deduped, order-stable."""
    seen, out = set(), []
    for b in site_spec.get("buildings", []):
        src = b.get("scene") or b.get("glb")
        if src and src not in seen:
            seen.add(src)
            out.append(src)
    for bk in site_spec.get("blockers", []):
        src = bk.get("scene") or bk.get("glb")
        if src and src not in seen:
            seen.add(src)
            out.append(src)
    return out


def _find_asset(name, base_dir, dc_dir):
    """Locate a .glb/.tscn by name: next to the site spec, then DC build/."""
    local = os.path.join(base_dir, name)
    if os.path.exists(local):
        return local
    if dc_dir:
        built = os.path.join(dc_dir, "build", name)
        if os.path.exists(built):
            return built
    return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _site_version(site_spec):
    return str(site_spec.get("version", "0.0.0"))


def _dc_provenance(asset_path):
    """If the asset came with a Deli Counter build manifest sitting next to it
    (<stem>.manifest.json), chain its provenance into the pack manifest."""
    stem = os.path.splitext(asset_path)[0]
    mp = stem + ".manifest.json"
    if not os.path.exists(mp):
        return None
    try:
        with open(mp, encoding="utf-8") as f:
            m = json.load(f)
        return {k: m[k] for k in ("kit_name", "kit_version", "schema_version",
                                  "spec", "spec_sha256_16", "built_utc")
                if k in m}
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _write_zip_deterministic(zip_path, pack_dir, out_dir):
    """Same inputs -> byte-identical zip: sorted entries, fixed timestamps
    (zip epoch), fixed permissions. The pack is a pure function of its inputs,
    so a collaborator (or future you) can verify a pack by hash alone."""
    entries = []
    for root, _, files in os.walk(pack_dir):
        for fn in files:
            full = os.path.join(root, fn)
            entries.append((os.path.relpath(full, out_dir).replace(os.sep, "/"),
                            full))
    entries.sort()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for arcname, full in entries:
            zi = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(full, "rb") as f:
                z.writestr(zi, f.read())


def _readme(site_spec, merged):
    name = site_spec["name"]
    n_obj = len(merged.get("objectives", []))
    n_loot = len(merged.get("loot", []))
    n_mark = len(merged.get("markers", []))
    rarities = [f"{b['id']}: {b['rarity']} ({b['rarity_color']['hex']})"
                for b in merged.get("buildings", []) if b.get("rarity")]
    rline = "; ".join(rarities) if rarities else "none set"
    ver = _site_version(site_spec)
    return f"""# {name} — site pack v{ver}

Drop this folder anywhere inside your Godot 4.x project (e.g.
`res://levels/{name}_pack/`) and instance **`{name}.tscn`**. All internal
references are relative, so the folder works at any path. Let Godot's import
pass finish on first open (the .glb files import as scenes).

## Quick QA
Open `{name}_walk.tscn` and press F6 — first-person walk with objective /
extraction beacons, no addon install needed (its two scripts are in this
folder).

## The integration contract: `{name}.site.gameplay.json`
Everything gameplay binds to lives here, world-space and namespaced by
building id ({n_mark} markers, {n_obj} objectives, {n_loot} loot spawns):

- `markers`    — spawns (crew/attacker), cover_low/high, objective, loot,
                 extraction, camera sockets, DOOR_SOCKET / BREACH_PANEL anchors
- `rooms`      — per-building room rects with roles (objective_room, etc.)
- `objectives` / `loot` / `zones` — the heist beats (zones include extraction)
- `openings`   — every door/window/breach with world position, dims, tags,
                 breach_class, and (when set) the building's rarity + colour
- `interactives` — the replicable state machines (INTERACTIVES.md): stable
                 `id`, `states`, `default`, `transitions`, world `transform`.
                 The netcode's input — one replicated node per `id`; ids are
                 carried verbatim from the building's gameplay.json
- `site_markers` — site-level crew_spawn, extraction, responder/horde spawns
- `buildings[]` — placement (`at`, `rot`) and per-building `rarity` +
                 `rarity_color` (this pack: {rline})
- `tactical` / `enterability` / `pacing` / `encounters` — offline intel

**Rarity reveal contract:** rarity is a value, not an effect. Fire your
reveal (light/sound/HUD) ONCE per building when the squad first enters
through any valid opening; read the colour from the opening's or the
building's `rarity_color` (`hex` or Godot-ready `rgb`).

## Axis mapping
Site/gameplay coords are Blender-style Z-up: site `(x, y, z)` → Godot
`(x, z, -y)`. All positions in the gameplay JSON are site coords.

## Rebuilds
This pack is generated output. The source of truth is the Deli Counter
building specs + the Lot site spec; ask for a regenerated pack rather than
hand-editing the .tscn.

Provenance for this exact pack (per-file sha256, source spec hash, the
Deli Counter build each .glb came from) is in `pack.manifest.json`. The pack
zip is deterministic: identical inputs produce a byte-identical zip, so its
sha256 (sidecar `.sha256` file) identifies the release.

— {name} v{ver}, packed by Lot {LOT_VERSION}
"""


#: A host project for walking a pack in place. The pack ships WITHOUT this by
#: default: its contract is to be dropped inside someone else's project, and a
#: nested project.godot breaks that. --walkable opts in, for local validation.
_WALK_PROJECT = """; Host project for walking this site pack locally.
;
; NOT part of the pack's contract. The pack is a drop-in folder for your own
; Godot project -- DELETE THIS FILE before dropping the folder in, or you will
; have two project.godot files and Godot will complain about the nested one.
;
; Written by `package.py --walkable`.

config_version=5

[application]

config/name="{name} (site pack walk)"
run/main_scene="res://{scene}"
{features}
[navigation]

; The baked navmesh in this pack uses the agent contract's nav_bake grid. Godot's
; project-wide navigation map defaults to 0.25/0.25, and the engine warns that a
; map coarser than the mesh it carries "can cause rasterization errors with
; navigation mesh edges" -- edges in the wrong place, which is the whole class of
; defect a walk test exists to catch. A consumer dropping this pack into their own
; project has to set these there; the pack cannot set them for you.
3d/default_cell_size={cell_size}
3d/default_cell_height={cell_height}

[debug]

gdscript/warnings/inference_on_variant=1

[rendering]

renderer/rendering_method="gl_compatibility"
"""


def _godot_features(godot):
    """The `config/features` line, asked of the engine rather than guessed.

    Naming a version the local editor is not produces an upgrade prompt on open,
    and hardcoding one bakes whichever machine wrote this tool into every host
    project it emits. So: query the binary when there is one, and otherwise omit
    the line entirely and let Godot fill it in on first open.
    """
    import re
    import subprocess
    if godot and os.path.exists(godot):
        try:
            r = subprocess.run([godot, "--version"], capture_output=True,
                               text=True, timeout=30)
            m = re.search(r"(\d+)\.(\d+)", (r.stdout or "") + (r.stderr or ""))
            if m:
                return f'config/features=PackedStringArray("{m.group(1)}.'\
                       f'{m.group(2)}")\n'
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def _write_walk_project(pack_dir, name, godot=None):
    """project.godot in the pack, main scene = the QA walk scene."""
    scene = f"{name}_walk.tscn"
    if not os.path.exists(os.path.join(pack_dir, scene)):
        print(f"[package] --walkable asked for, but {scene} is not in the pack; "
              f"no project.godot written")
        return None
    path = os.path.join(pack_dir, "project.godot")
    with open(path, "w", encoding="utf-8") as f:
        nav = lot._agent()["nav_bake"]
        f.write(_WALK_PROJECT.format(
            name=name, scene=scene, features=_godot_features(godot),
            cell_size=float(nav["cell_size_m"]),
            cell_height=float(nav["cell_height_m"])))
    return path


def _engine_check(pack_dir, godot, name):
    """Import the pack and instantiate its walk scene, headless.

    A weaker claim than "a human walked it" on purpose: it proves the pack
    IMPORTS and its scene LOADS, which is the failure class a deterministic zip
    and a sha256 are silent about. The building packager has had this since day
    one; the site packager never did, so no site pack has ever been confirmed to
    open in Godot.
    """
    import subprocess
    if not os.path.exists(godot):
        print(f"[package] CHECK SKIPPED: no Godot at {godot} -- and a skipped "
              f"check is not a passing one")
        return False
    print(f"[package] engine check: {godot}")
    imp = subprocess.run([godot, "--headless", "--path", pack_dir, "--import"],
                         capture_output=True, text=True)
    run = subprocess.run([godot, "--headless", "--path", pack_dir,
                          "--quit-after", "120"],
                         capture_output=True, text=True)
    blob = "\n".join([imp.stdout or "", imp.stderr or "",
                       run.stdout or "", run.stderr or ""])
    errs = [ln for ln in blob.splitlines()
            if "ERROR" in ln or "SCRIPT ERROR" in ln or "Failed to load" in ln]
    ok = run.returncode == 0 and not errs
    print(f"[package]   import exit {imp.returncode}, "
          f"scene run exit {run.returncode}, {len(errs)} error line(s)")
    for ln in errs[:8]:
        print(f"[package]     {ln.strip()[:160]}")
    print(f"[package]   PACK LOADS IN GODOT = {ok}")
    if not ok:
        print(f"[package]   this is the only check that touches the engine. "
              f"A pack that\n[package]   fails here is not a deliverable, "
              f"however clean its manifest is.")
    return ok


def build_pack(site_spec_path, out_dir=None, keep_folder=False, dc=None,
               note=None, walkable=False, check_godot=None):
    site_spec_path = os.path.abspath(site_spec_path)
    base_dir = os.path.dirname(site_spec_path)
    with open(site_spec_path, encoding="utf-8") as f:
        site_spec = json.load(f)
    name = site_spec["name"]
    out_dir = os.path.abspath(out_dir or os.path.join(HERE, "dist"))
    pack_dir = os.path.join(out_dir, f"{name}_pack")

    dc_dir = find_dc(dc)

    # resolve every instanced asset BEFORE writing anything
    missing = []
    resolved = {}
    for src in _pack_sources(site_spec):
        p = _find_asset(src, base_dir, dc_dir)
        if p is None:
            missing.append(src)
        else:
            resolved[src] = p
    if missing:
        raise SystemExit(
            f"[package] missing built assets: {', '.join(missing)}. Build "
            f"them first, e.g.:\n  python cater.py "
            f"{os.path.relpath(site_spec_path, HERE)} <godot_project>\n"
            f"(a pack of preview boxes is not a deliverable, so there is no "
            f"--preview here)")

    if os.path.exists(pack_dir):
        shutil.rmtree(pack_dir)
    os.makedirs(pack_dir)

    # merged gameplay (also validates gates) + portable scenes into the pack
    import site_tactical
    site_tactical.gate(site_spec)
    merged = lot.merge_gameplay(site_spec, base_dir)
    merged["tactical"] = site_tactical.analyze(site_spec)
    import site_enterability
    merged["enterability"] = site_enterability.gate(site_spec, merged)
    import site_pacing
    adj = site_tactical.build_graph(site_spec)
    merged["pacing"] = site_pacing.estimate_pacing(site_spec, merged)
    merged["encounters"] = site_pacing.encounter_intel(site_spec, adj)

    # Same ground policy as assemble(): a hole is cut under a building only
    # where its geometry is known to bring collision. The pack has already
    # resolved every asset, so audit those exact files -- a pack that shipped a
    # void would take it to whoever opened it, with no source spec to re-check.
    import site_ground
    ground_reports = site_ground.audit(site_spec, [base_dir, dc_dir],
                                       resolved=resolved)
    self_flooring = site_ground.self_flooring_ids(ground_reports)
    merged["ground"] = {bid: rep.as_dict() for bid, rep in
                        sorted(ground_reports.items())}
    ground_findings = site_ground.findings(ground_reports)
    merged["tactical"].setdefault("findings", []).extend(ground_findings)
    for f_ in ground_findings:
        print(f"[package] {f_['code']}: {f_['message']}")

    with open(os.path.join(pack_dir, f"{name}.site.gameplay.json"), "w",
              encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    lot.write_godot_scene(site_spec, merged,
                          os.path.join(pack_dir, f"{name}.tscn"),
                          portable=True, self_flooring=self_flooring)
    lot.write_walk_scene(site_spec, merged,
                         os.path.join(pack_dir, f"{name}_walk.tscn"),
                         name, portable=True)

    for src, p in resolved.items():
        # Copy to the asset's OWN relative path, not its basename. The scene
        # emits `path="buildings/x.glb"` relative to itself (that relativity is
        # what lets this folder sit at any path in a consumer's project), and
        # basename() flattened it to "x.glb" -- one directory above where the
        # scene looks. Every site pack ever built failed to load for this reason,
        # and a manifest, a deterministic zip and a sha256 all describe such a
        # pack without complaint. Only the engine notices.
        rel = str(src).replace("\\", "/").lstrip("/")
        if os.path.isabs(str(src)) or ".." in rel.split("/"):
            # The scene would have emitted this same odd path, so flattening it
            # here would not save the pack -- say so rather than quietly
            # producing something that cannot load.
            print(f"[package] ASSET PATH NOT PACK-RELATIVE: {src!r}. The scene "
                  f"references it as written, so the pack will not resolve it. "
                  f"Use a path relative to the site spec, like "
                  f"buildings/<name>.glb.")
            rel = os.path.basename(str(src))
        dest = os.path.join(pack_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(p, dest)
    for gd in ("lot_site_walk.gd", "lot_player.gd"):
        shutil.copy2(os.path.join(HERE, "godot", "addons", "lot", gd),
                     os.path.join(pack_dir, gd))

    with open(os.path.join(pack_dir, "PACK_README.md"), "w",
              encoding="utf-8") as f:
        f.write(_readme(site_spec, merged))

    # provenance manifest: the pack is a traceable RELEASE, not a zip button.
    # No build timestamp on purpose -- the pack must be a pure function of its
    # inputs so identical inputs give a byte-identical zip (DC/gool ethos:
    # deterministic, hash-verifiable). Dates belong in --note if you want one.
    ver = _site_version(site_spec)
    manifest = {
        "site": name,
        "site_version": ver,
        "lot_version": LOT_VERSION,
        "site_spec": os.path.basename(site_spec_path),
        "site_spec_sha256": _sha256(site_spec_path),
        "note": note,
        "gates": {
            "mode": merged.get("tactical", {}).get("mode"),
            "pacing_status": merged.get("pacing", {}).get("status"),
            "enterability": [
                {"id": e.get("id"), "valid": e.get("valid_entries"),
                 "clear": e.get("clear_entries")}
                for e in merged.get("enterability", {}).get("buildings", [])],
        },
        "files": {},
        "assets": {},
    }
    for src_name, p in resolved.items():
        prov = _dc_provenance(p)
        manifest["assets"][os.path.basename(src_name)] = {
            "sha256": _sha256(p),
            **({"deli_counter": prov} if prov else {}),
        }
    # WALK the pack, do not list it. os.listdir returns names, and every name
    # used to be a file only because the pack was flat -- assets are now copied
    # to their own relative paths, so `buildings/` is a directory and
    # open(directory, "rb") is PermissionError on Windows.
    #
    # Recording POSIX relative paths also makes the manifest describe the pack as
    # the SCENE addresses it ("buildings/warehouse_a02.glb"), agree with the
    # deterministic zip, which has always stored nested paths, and stay correct
    # for any depth rather than for exactly one level.
    for root, dirs, files in os.walk(pack_dir):
        dirs.sort()
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, pack_dir).replace(os.sep, "/")
            if rel == "pack.manifest.json":
                continue        # written below; cannot hash itself
            manifest["files"][rel] = {"sha256": _sha256(full),
                                      "bytes": os.path.getsize(full)}
    with open(os.path.join(pack_dir, "pack.manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    # Written BEFORE the zip so a --walkable pack and its zip agree. It is not
    # part of the pack's contract, so the README says to delete it when nesting.
    if walkable:
        wp = _write_walk_project(pack_dir, name, check_godot)
        if wp:
            print(f"[package] walkable: project.godot -> main scene "
                  f"{name}_walk.tscn")

    zip_path = os.path.join(out_dir, f"{name}_pack_v{ver}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    _write_zip_deterministic(zip_path, pack_dir, out_dir)
    zip_hash = _sha256(zip_path)
    with open(zip_path + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{zip_hash}  {os.path.basename(zip_path)}\n")
    if check_godot:
        # The folder has to survive for the engine to look at it, whatever
        # --keep-folder said.
        _engine_check(pack_dir, check_godot, name)
    if not keep_folder and not walkable:
        shutil.rmtree(pack_dir)

    if "version" not in site_spec:
        print(f"[package] NOTE: site spec has no \"version\" field -- packed "
              f"as v0.0.0. Give the site a version and bump it per walked "
              f"release.")
    n = len(resolved)
    print(f"[package] {name} v{ver}: {n} asset(s), portable scenes, gameplay "
          f"contract, provenance manifest, QA walk")
    print(f"[package]   -> {zip_path}")
    print(f"[package]   sha256 {zip_hash[:16]}…  (sidecar .sha256; "
          f"deterministic: identical inputs give an identical zip)")
    if walkable:
        print(f"[package]   walk it:  <godot> --path \"{pack_dir}\"")
        print(f"[package]   then F6, or add --check <godot> to have package.py "
              f"load it headless")
    return zip_path


def main(argv=None):
    ap = argparse.ArgumentParser(description="build a shareable site pack")
    ap.add_argument("site_spec")
    ap.add_argument("--out", help="output dir (default: dist/)")
    ap.add_argument("--keep-folder", action="store_true",
                    help="leave the unzipped pack folder next to the zip")
    ap.add_argument("--dc", help="Deli Counter repo (for build/ .glb lookup)")
    ap.add_argument("--note", help="free-text release note recorded in "
                    "pack.manifest.json (e.g. 'walked full route 2026-07-01')")
    ap.add_argument("--walkable", action="store_true",
                    help="also write project.godot so the pack opens as a Godot "
                         "project and F6 walks it (delete that file before "
                         "dropping the folder into your own project); implies "
                         "--keep-folder")
    ap.add_argument("--check", metavar="GODOT", default=None,
                    help="import the pack and load its walk scene headless, "
                         "failing on a Godot error; implies --walkable")
    a = ap.parse_args(argv)
    walkable = a.walkable or bool(a.check)
    build_pack(a.site_spec, a.out, a.keep_folder, a.dc, note=a.note,
               walkable=walkable, check_godot=a.check)


if __name__ == "__main__":
    main()
