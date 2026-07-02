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


def build_pack(site_spec_path, out_dir=None, keep_folder=False, dc=None,
               note=None):
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

    with open(os.path.join(pack_dir, f"{name}.site.gameplay.json"), "w",
              encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    lot.write_godot_scene(site_spec, merged,
                          os.path.join(pack_dir, f"{name}.tscn"),
                          portable=True)
    lot.write_walk_scene(site_spec, merged,
                         os.path.join(pack_dir, f"{name}_walk.tscn"),
                         name, portable=True)

    for src, p in resolved.items():
        shutil.copy2(p, os.path.join(pack_dir, os.path.basename(src)))
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
    for fn in sorted(os.listdir(pack_dir)):
        full = os.path.join(pack_dir, fn)
        manifest["files"][fn] = {"sha256": _sha256(full),
                                 "bytes": os.path.getsize(full)}
    with open(os.path.join(pack_dir, "pack.manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    zip_path = os.path.join(out_dir, f"{name}_pack_v{ver}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    _write_zip_deterministic(zip_path, pack_dir, out_dir)
    zip_hash = _sha256(zip_path)
    with open(zip_path + ".sha256", "w", encoding="utf-8") as f:
        f.write(f"{zip_hash}  {os.path.basename(zip_path)}\n")
    if not keep_folder:
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
    a = ap.parse_args(argv)
    build_pack(a.site_spec, a.out, a.keep_folder, a.dc, note=a.note)


if __name__ == "__main__":
    main()
