#!/usr/bin/env python3
"""
walktest.py  --  run the automated site walktest headlessly (Godot 4)
=====================================================================
Runs a Lot `<site>_navqa.tscn` under headless Godot. The scene's NavQASetup
node bakes the navmesh and feeds the heist_nav_qa director (shipped in
godot/addons/heist_nav_qa/), which path-proves the mission spine and drives
simulated walkers, writes `<site>_navqa.walktest.json`, and exits 0/1.

    python walktest.py <project_dir> <site>_navqa.tscn
    python walktest.py <project_dir> --all
    python walktest.py <project_dir> --all --require   # missing Godot = fail

<project_dir> must contain project.godot (cater.py creates one). This runner
syncs the heist_nav_qa addon into the project first, so the director is
always the version shipped with this Lot checkout.

Godot discovery: $DC_GODOT / $LOT_GODOT, then godot4/godot on PATH.
Exit code: 0 = all pass (or skipped without --require), 1 = failures.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_SRC = os.path.join(HERE, "godot", "addons", "heist_nav_qa")
_CANDIDATES = ("godot4", "godot", "godot4-headless", "godot-headless")


def find_godot(env=None):
    env = env if env is not None else os.environ
    names = []
    for var in ("LOT_GODOT", "DC_GODOT"):
        if env.get(var):
            names.append(env[var])
    names += list(_CANDIDATES)
    tried = []
    for name in names:
        path = name if os.path.sep in name else shutil.which(name)
        if not path or not os.path.exists(path):
            tried.append(f"{name}: not found")
            continue
        try:
            out = subprocess.run([path, "--version"], capture_output=True,
                                 text=True, timeout=30)
            version = (out.stdout or out.stderr).strip().splitlines()[0] \
                if (out.stdout or out.stderr).strip() else ""
        except Exception as ex:                       # noqa: BLE001
            tried.append(f"{name}: {ex}")
            continue
        if version.startswith("4."):
            return path, version
        tried.append(f"{name}: version '{version}' is not Godot 4")
    return None, "; ".join(tried)


def ensure_project(project_dir, name="lot_site"):
    """Minimal project.godot so a bare out-dir runs headless (cater.py makes
    a fuller one; either works)."""
    pg = os.path.join(project_dir, "project.godot")
    if not os.path.exists(pg):
        with open(pg, "w", encoding="utf-8") as f:
            f.write('config_version=5\n\n[application]\n\n'
                    f'config/name="{name}"\n')
        print(f"[walktest] created minimal {pg}")


def sync_addon(project_dir):
    """Copy BOTH addons the navqa scene needs: lot (setup script) and
    heist_nav_qa (the director), so they are always this checkout's version."""
    for sub in ("heist_nav_qa", "lot"):
        src = os.path.join(HERE, "godot", "addons", sub)
        dst = os.path.join(project_dir, "addons", sub)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            if os.path.isfile(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), os.path.join(dst, f))


def run_one(godot, project_dir, scene, timeout=300):
    name = os.path.basename(scene)
    rel = os.path.relpath(scene, project_dir).replace(os.sep, "/")
    cmd = [godot, "--headless", "--path", project_dir, f"res://{rel}"]
    print(f"[walktest] {name} ...")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[walktest] {name}: TIMEOUT after {timeout}s")
        return False
    sys.stdout.write(proc.stdout)
    report_path = os.path.splitext(scene)[0] + ".walktest.json"
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                ok = bool(json.load(f).get("ok"))
        except Exception:
            ok = False
        print(f"[walktest] {name}: {'PASS' if ok else 'FAIL'} -> {report_path}")
        return ok
    print(f"[walktest] {name}: no report written (exit {proc.returncode})")
    if proc.stderr:
        sys.stderr.write(proc.stderr[-2000:])
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("project", help="Godot project dir (has project.godot)")
    ap.add_argument("scene", nargs="?", help="a *_navqa.tscn inside it")
    ap.add_argument("--all", action="store_true",
                    help="every *_navqa.tscn in the project")
    ap.add_argument("--require", action="store_true")
    args = ap.parse_args(argv)

    ensure_project(args.project)

    godot, reason = find_godot()
    if godot is None:
        msg = f"[walktest] SKIP: no usable Godot 4 binary ({reason})"
        if args.require:
            print(msg + " -- --require set, failing")
            return 1
        print(msg)
        return 0

    sync_addon(args.project)

    if args.all:
        targets = sorted(glob.glob(os.path.join(args.project, "**",
                                                "*_navqa.tscn"),
                                   recursive=True))
    elif args.scene:
        targets = [args.scene if os.path.isabs(args.scene)
                   else os.path.join(args.project, args.scene)]
    else:
        ap.error("give a scene or --all")
    if not targets:
        print("[walktest] no *_navqa.tscn found")
        return 1

    rc = 0
    for scene in targets:
        if not run_one(godot, args.project, scene):
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
