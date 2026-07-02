#!/usr/bin/env python3
"""
cater.py  --  one command from site spec to walkable Godot project
==================================================================
The whole gs_heist flow, codified. You point it at a Lot site spec and a
Godot project folder; it does everything the hands did:

  1. finds the Deli Counter repo and, for every building in the site (and
     every blocker that references a facade shell), builds the DC spec in
     headless Blender -- but ONLY if the .glb is missing or older than its
     spec (incremental; --force-build to override)
  2. copies each .glb into the Godot project and each .gameplay.json next to
     where the site spec expects it
  3. syncs godot/addons/lot into the project (and writes a minimal
     project.godot if the folder is a fresh directory, so a brand-new empty
     folder becomes an openable project)
  4. runs lot.py on the site spec into the project (--walkable --navqa by
     default)

USAGE
-----
    python cater.py specs\\gs_heist.json "C:\\path\\to\\GodotProject"
    python cater.py specs\\gs_heist.json "C:\\...\\Proj" --preview
    python cater.py specs\\gs_heist.json "C:\\...\\Proj" --blender "C:\\blender\\blender.exe"
    python cater.py specs\\gs_heist.json "C:\\...\\Proj" --force-build
    python cater.py specs\\gs_heist.json "C:\\...\\Proj" --skip-build   # copies + assemble only

--preview skips Blender and the copies entirely (Lot boxes the buildings from
their specs), so the same command works before Blender is even installed.
Iteration loop: edit a building spec or the site spec, re-run the one command;
only what changed gets rebuilt.

RESOLUTION ORDER
----------------
Deli Counter repo : --dc flag  ->  $DELI_COUNTER env  ->  sibling ../deli_counter
                    (relative to this file)  ->  C:\\Projects\\deli_counter
Blender           : --blender flag  ->  $BLENDER env  ->  PATH  ->  DC build.py's
                    own guesses (it receives the flag/env pass-through)

Facade shells: a blocker with a "glb" ref (e.g. gs_facade_storefront.glb) maps
to the DC spec of the same stem (specs/gs_facade_storefront.json). Facades get
built + their .glb copied; they have no gameplay.json to place (they're
non-enterable filler by design).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------
def find_dc(explicit=None):
    """Locate the Deli Counter repo (the folder holding build.py + specs/)."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    if os.environ.get("DELI_COUNTER"):
        candidates.append(os.environ["DELI_COUNTER"])
    candidates.append(os.path.join(os.path.dirname(HERE), "deli_counter"))
    candidates.append(r"C:\Projects\deli_counter")
    for c in candidates:
        if c and os.path.exists(os.path.join(c, "build.py")):
            return os.path.abspath(c)
    return None


def needs_build(spec_path, glb_path, force=False):
    """True if the .glb must be (re)built: forced, missing, or older than its
    spec. The spec is the source of truth; the .glb is disposable output."""
    if force:
        return True
    if not os.path.exists(glb_path):
        return True
    return os.path.getmtime(spec_path) > os.path.getmtime(glb_path)


def facade_jobs(site_spec, dc_dir):
    """Blockers with a glb ref -> (dc_spec_path, glb_stem) build jobs, for the
    shells DC knows how to make. A blocker glb with no matching DC spec is
    left alone (it may be a hand-made asset) -- reported, not fatal."""
    jobs, unknown = [], []
    for bk in site_spec.get("blockers", []):
        ref = bk.get("scene") or bk.get("glb")
        if not ref:
            continue
        stem = os.path.splitext(os.path.basename(ref))[0]
        spec_path = os.path.join(dc_dir, "specs", stem + ".json")
        if os.path.exists(spec_path):
            jobs.append((spec_path, stem))
        else:
            unknown.append(ref)
    # dedupe, order-stable (the same shell may wall several blockers)
    seen, out = set(), []
    for j in jobs:
        if j[1] not in seen:
            seen.add(j[1])
            out.append(j)
    return out, unknown


# ---------------------------------------------------------------------------
# steps
# ---------------------------------------------------------------------------
def build_in_dc(dc_dir, spec_path, blender=None):
    """Run DC's build.py on one spec (headless Blender). Raises on failure."""
    cmd = [sys.executable, os.path.join(dc_dir, "build.py"), spec_path]
    if blender:
        cmd += ["--blender", blender]
    print(f"[cater] blender build: {os.path.basename(spec_path)}")
    r = subprocess.run(cmd, cwd=dc_dir)
    if r.returncode != 0:
        raise RuntimeError(
            f"Deli Counter build failed for {os.path.basename(spec_path)} "
            f"(exit {r.returncode}). Fix the spec / Blender setup and re-run; "
            f"already-built buildings won't rebuild.")


def ensure_project(project_dir, site_name):
    """Make the target folder an openable Godot project: create it if missing
    and write a minimal project.godot if there isn't one. Never overwrites an
    existing project.godot."""
    os.makedirs(project_dir, exist_ok=True)
    pg = os.path.join(project_dir, "project.godot")
    if not os.path.exists(pg):
        with open(pg, "w", encoding="utf-8") as f:
            f.write('config_version=5\n\n[application]\n\n'
                    f'config/name="{site_name}"\n'
                    'config/features=PackedStringArray("4.7")\n')
        print(f"[cater] wrote minimal project.godot ({site_name})")


def sync_addon(project_dir):
    """Copy godot/addons/lot into the project (idempotent refresh)."""
    src = os.path.join(HERE, "godot", "addons", "lot")
    dst = os.path.join(project_dir, "addons", "lot")
    shutil.copytree(src, dst, dirs_exist_ok=True)
    print("[cater] synced addons/lot")


def run_lot(site_spec_path, project_dir, walkable=True, navqa=True,
            preview=False):
    """Run lot.py exactly as by hand, so output/UX is byte-identical."""
    cmd = [sys.executable, os.path.join(HERE, "lot.py"),
           site_spec_path, project_dir]
    if walkable:
        cmd.append("--walkable")
    if navqa:
        cmd.append("--navqa")
    if preview:
        cmd.append("--preview")
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode != 0:
        raise RuntimeError(f"lot.py failed (exit {r.returncode})")


# ---------------------------------------------------------------------------
# the pipeline
# ---------------------------------------------------------------------------
def cater(site_spec_path, project_dir, dc=None, blender=None, preview=False,
          skip_build=False, force_build=False, walkable=True, navqa=True):
    site_spec_path = os.path.abspath(site_spec_path)
    project_dir = os.path.abspath(project_dir)
    base_dir = os.path.dirname(site_spec_path)
    with open(site_spec_path, encoding="utf-8") as f:
        site_spec = json.load(f)
    site_name = site_spec.get("name", "site")

    ensure_project(project_dir, site_name)
    sync_addon(project_dir)

    if preview:
        # no Blender, no copies: Lot boxes the buildings from their specs
        run_lot(site_spec_path, project_dir, walkable, navqa, preview=True)
        print(f"[cater] PREVIEW served -> open {site_name}_walk.tscn in Godot, F6")
        return

    dc_dir = find_dc(dc)
    if dc_dir is None:
        raise SystemExit(
            "[cater] can't find the Deli Counter repo (looked at --dc, "
            "$DELI_COUNTER, ../deli_counter, C:\\Projects\\deli_counter). "
            "Pass --dc <path>, or use --preview to walk massing boxes "
            "without any builds.")
    print(f"[cater] deli counter: {dc_dir}")
    dc_build = os.path.join(dc_dir, "build")

    # -- gather jobs: enterable buildings (glb + gameplay) + facade shells (glb)
    jobs = []      # (dc_spec_path, glb_stem, gameplay_dest_dir_or_None)
    for b in site_spec.get("buildings", []):
        spec_ref = b.get("spec")
        glb_ref = b.get("glb")
        if not spec_ref or not glb_ref:
            print(f"[cater] building '{b.get('id')}' has no spec/glb ref -- "
                  f"leaving it to whatever is already in place")
            continue
        # the building spec may live in the Lot tree (a site-local copy) or be
        # named after a DC spec; DC's build wants the DC-side spec. Prefer the
        # DC spec of the same stem; fall back to the site-local copy.
        stem = os.path.splitext(os.path.basename(glb_ref))[0]
        dc_spec = os.path.join(dc_dir, "specs", stem + ".json")
        local_spec = os.path.join(base_dir, spec_ref)
        spec_path = dc_spec if os.path.exists(dc_spec) else local_spec
        gp_dest = os.path.dirname(os.path.join(base_dir, b["gameplay"])) \
            if b.get("gameplay") else base_dir
        jobs.append((spec_path, stem, gp_dest))

    shells, unknown = facade_jobs(site_spec, dc_dir)
    for spec_path, stem in shells:
        jobs.append((spec_path, stem, None))
    for ref in unknown:
        print(f"[cater] blocker shell '{ref}' has no DC spec of that stem -- "
              f"assuming it's a hand-made asset already in the project")

    # -- build what's stale, copy everything
    built = 0
    if not skip_build:
        for spec_path, stem, _ in jobs:
            glb_out = os.path.join(dc_build, stem + ".glb")
            if needs_build(spec_path, glb_out, force_build):
                build_in_dc(dc_dir, spec_path, blender)
                built += 1
            else:
                print(f"[cater] up to date: {stem}.glb")

    missing = []
    for spec_path, stem, gp_dest in jobs:
        glb_src = os.path.join(dc_build, stem + ".glb")
        if not os.path.exists(glb_src):
            missing.append(stem + ".glb")
            continue
        shutil.copy2(glb_src, os.path.join(project_dir, stem + ".glb"))
        if gp_dest:
            gp_src = os.path.join(dc_build, stem + ".gameplay.json")
            if os.path.exists(gp_src):
                os.makedirs(gp_dest, exist_ok=True)
                shutil.copy2(gp_src, os.path.join(gp_dest,
                                                  stem + ".gameplay.json"))
            else:
                missing.append(stem + ".gameplay.json")
    if missing:
        raise SystemExit(
            f"[cater] missing build outputs: {', '.join(missing)}. "
            f"Run without --skip-build (or with --force-build) so DC "
            f"produces them.")
    print(f"[cater] {built} built, {len(jobs) - built} already fresh, "
          f"{len(jobs)} copied into place")

    run_lot(site_spec_path, project_dir, walkable, navqa, preview=False)
    print(f"[cater] SERVED -> open {site_name}_walk.tscn in Godot, F6")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="site spec -> built buildings -> walkable Godot project, "
                    "one command")
    ap.add_argument("site_spec", help="Lot site spec (specs/<site>.json)")
    ap.add_argument("project", help="Godot project folder (created if missing)")
    ap.add_argument("--dc", help="Deli Counter repo path")
    ap.add_argument("--blender", help="blender executable (else $BLENDER/PATH)")
    ap.add_argument("--preview", action="store_true",
                    help="no Blender: box the buildings from their specs")
    ap.add_argument("--skip-build", action="store_true",
                    help="don't run Blender; copy existing outputs + assemble")
    ap.add_argument("--force-build", action="store_true",
                    help="rebuild every building even if fresh")
    ap.add_argument("--no-navqa", action="store_true")
    ap.add_argument("--no-walkable", action="store_true")
    a = ap.parse_args(argv)
    try:
        cater(a.site_spec, a.project, dc=a.dc, blender=a.blender,
              preview=a.preview, skip_build=a.skip_build,
              force_build=a.force_build,
              walkable=not a.no_walkable, navqa=not a.no_navqa)
    except (RuntimeError, OSError, json.JSONDecodeError) as e:
        print(f"[cater] FAILED: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
