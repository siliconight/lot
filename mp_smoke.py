#!/usr/bin/env python3
"""
mp_smoke.py  --  run the multiplayer runtime smoke test (host + N clients)
==========================================================================
Launches one headless Godot HOST and N-1 headless CLIENTS on localhost,
all loading the composed site scene, clients physically moving from the
crew spawn toward the objective while heartbeating the host. Verdict:
every client connected, moved >= 5 m through the actual site collision,
and no early disconnects.

    python mp_smoke.py <project_dir> <site_spec.json> [--players 4]
                       [--secs 20] [--port 39901]

<project_dir> needs project.godot plus the assembled site (cater.py / lot.py
put <site>.tscn and the .glb files there). The spec is read only for the
crew-spawn/objective positions (converted level Z-up -> Godot Y-up).

Writes <site>.mp_smoke.json into the project dir. Exit 0 = pass.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from walktest import find_godot  # shared discovery


def _to_godot(p):
    """level space (x, y_north, z_up) -> Godot (x, z_up, -y_north)"""
    return (p[0], p[2], -p[1])


def _positions(site_spec_path, project_dir):
    import lot as lot_mod
    with open(site_spec_path, "r", encoding="utf-8") as f:
        site_spec = json.load(f)
    name = site_spec["name"]
    gp_path = os.path.join(project_dir, f"{name}.site.gameplay.json")
    if not os.path.exists(gp_path):
        raise SystemExit(f"[mp-smoke] {gp_path} not found -- assemble the "
                         f"site into the project first (lot.py/cater.py)")
    with open(gp_path, "r", encoding="utf-8") as f:
        merged = json.load(f)
    pos = lot_mod._walk_positions(site_spec, merged)
    return name, _to_godot(pos["spawn"]), _to_godot(pos["objective"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("project", help="Godot project dir (has project.godot)")
    ap.add_argument("site_spec", help="the Lot site spec JSON")
    ap.add_argument("--players", type=int, default=4,
                    help="target player count incl. host (default 4)")
    ap.add_argument("--secs", type=float, default=20.0)
    ap.add_argument("--port", type=int, default=39901)
    ap.add_argument("--require", action="store_true")
    args = ap.parse_args(argv)

    godot, reason = find_godot()
    if godot is None:
        msg = f"[mp-smoke] SKIP: no usable Godot 4 binary ({reason})"
        if args.require:
            print(msg + " -- --require set, failing")
            return 1
        print(msg)
        return 0

    from walktest import ensure_project
    ensure_project(args.project)

    name, spawn, objective = _positions(args.site_spec, args.project)
    scene_res = f"res://{name}.tscn"
    out_json = os.path.join(args.project, f"{name}.mp_smoke.json")
    script_res = "res://addons/lot/mp_smoke.gd"

    # sync the full addon set + run the asset import pass (GLBs must be
    # imported before a scene can instance them headlessly)
    from walktest import sync_addon, import_pass
    sync_addon(args.project)
    import_pass(godot, args.project)

    n_clients = max(1, args.players - 1)
    base = [godot, "--headless", "--path", args.project, "--script", script_res, "--"]

    host_cmd = base + ["host", str(args.port), scene_res,
                       str(args.players), str(args.secs),
                       f"res://{name}.mp_smoke.json"]
    print(f"[mp-smoke] host: {name} @ :{args.port}, {args.players} players, "
          f"{args.secs:.0f}s")
    host = subprocess.Popen(host_cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    time.sleep(2.0)

    clients = []
    for i in range(n_clients):
        sp = (spawn[0] + i * 1.2, spawn[1], spawn[2])
        c = subprocess.Popen(
            base + ["client", str(args.port), scene_res,
                    ",".join(f"{v:.3f}" for v in sp),
                    ",".join(f"{v:.3f}" for v in objective),
                    str(args.secs)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        clients.append(c)

    deadline = time.time() + args.secs + 60
    procs = [("host", host)] + [(f"client{i}", c) for i, c in enumerate(clients)]
    codes = {}
    for label, p in procs:
        remain = max(5, deadline - time.time())
        try:
            out, _ = p.communicate(timeout=remain)
        except subprocess.TimeoutExpired:
            p.kill()
            out, _ = p.communicate()
            print(f"[mp-smoke] {label}: KILLED (timeout)")
        codes[label] = p.returncode
        lines = (out or "").splitlines()
        tagged = [l for l in lines if "[mp-smoke]" in l]
        for line in tagged:
            print(f"  {label}: {line.strip()}")
        if p.returncode != 0 and len(tagged) < 2:
            # the process died/hung without telling its story -- show the
            # raw tail so the real Godot error is never invisible
            print(f"  {label}: --- raw output tail ---")
            for line in lines[-15:]:
                print(f"  {label}: {line.rstrip()}")

    ok = codes.get("host") == 0 and \
        all(codes[k] == 0 for k in codes if k.startswith("client"))
    if os.path.exists(out_json):
        with open(out_json, "r", encoding="utf-8") as f:
            rep = json.load(f)
        ok = ok and bool(rep.get("ok"))
        print(f"[mp-smoke] host report: {json.dumps(rep.get('clients', {}))}")
    print(f"[mp-smoke] {name}: {'PASS' if ok else 'FAIL'} "
          f"(exit codes {codes}) -> {out_json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
