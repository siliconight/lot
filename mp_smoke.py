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
    from walktest import sync_addon, import_pass, check_buildings
    sync_addon(args.project)
    if check_buildings(args.project):
        return 1
    import_pass(godot, args.project)

    n_clients = max(1, args.players - 1)
    base = [godot, "--headless", "--path", args.project, "--script", script_res, "--"]

    host_cmd = base + ["host", str(args.port), scene_res,
                       str(args.players), str(args.secs),
                       f"res://{name}.mp_smoke.json"]
    print(f"[mp-smoke] host: {name} @ :{args.port}, {args.players} players, "
          f"{args.secs:.0f}s")
    ready_flag = os.path.join(args.project, "mp_host_ready")
    if os.path.exists(ready_flag):
        os.remove(ready_flag)
    # Each process writes to its OWN LOG FILE, never a pipe. A pipe nobody
    # drains fills its ~64KB buffer and BLOCKS the host mid-scene-load --
    # which is exactly what made the beacon appear 90+ seconds late while
    # the clients handshook against an unbound port and died.
    log_dir = os.path.join(args.project, "_mp_logs")
    os.makedirs(log_dir, exist_ok=True)

    def _launch(label, cmd):
        lp = os.path.join(log_dir, f"{label}.log")
        lf = open(lp, "w", encoding="utf-8", errors="replace")
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        return label, p, lf, lp

    procs = [_launch("host", host_cmd)]
    host = procs[0][1]
    # Wait on the BEACON FILE only. host.poll() lies on Windows: the
    # *_console.exe is a wrapper that spawns the real engine as a child and
    # can exit early, while the engine keeps running.
    t0 = time.time()
    while not os.path.exists(ready_flag) and time.time() - t0 < 90:
        time.sleep(0.5)
    if os.path.exists(ready_flag):
        print(f"[mp-smoke] host ready after {time.time() - t0:.1f}s")
        if sys.platform == "win32":
            _socket_forensics(args.port)   # host alive NOW: who owns the port?
    else:
        print("[mp-smoke] WARNING: host never signalled ready in 90s; "
              "launching clients anyway")

    for i in range(n_clients):
        if i:
            time.sleep(3.0)   # stagger boots: concurrent instances race the
                              # import cache on first touch
        sp = (spawn[0] + i * 1.2, spawn[1], spawn[2])
        procs.append(_launch(
            f"client{i}",
            base + ["client", str(args.port), scene_res,
                    ",".join(f"{v:.3f}" for v in sp),
                    ",".join(f"{v:.3f}" for v in objective),
                    str(args.secs)]))

    deadline = time.time() + args.secs + 75
    codes = {}
    outputs = {}
    for label, p, lf, lp in procs:
        remain = max(5, deadline - time.time())
        try:
            p.wait(timeout=remain)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
            print(f"[mp-smoke] {label}: KILLED (timeout)")
        lf.close()
        codes[label] = p.returncode
        with open(lp, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        outputs[label] = lines
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
    else:
        # no host report = no proof. Exit codes alone can't carry a PASS:
        # on Windows they are the console WRAPPER's codes, not the engine's.
        ok = False
        print("[mp-smoke] no host report written -- failing")
    print(f"[mp-smoke] {name}: {'PASS' if ok else 'FAIL'} "
          f"(exit codes {codes}) -> {out_json}")
    if not ok and sys.platform == "win32":
        _socket_forensics(args.port)
    return 0 if ok else 1


def _socket_forensics(port):
    """On failure, show who (if anyone) owns UDP :port -- settles whether the
    firewall rule targets the right binary. Best-effort, Windows only."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "UDP"],
                             capture_output=True, text=True, timeout=15).stdout
        rows = [l.strip() for l in out.splitlines() if f":{port}" in l]
        if not rows:
            print(f"[mp-smoke] forensics: NOTHING bound to UDP :{port} at "
                  f"teardown (host already gone -- timing, not firewall)")
            return
        for row in rows:
            print(f"[mp-smoke] forensics: {row}")
            pid = row.split()[-1]
            if pid.isdigit():
                tl = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/FO", "LIST"],
                    capture_output=True, text=True, timeout=15).stdout
                for tl_line in tl.splitlines():
                    if "Image Name" in tl_line or "Nom d" in tl_line:
                        print(f"[mp-smoke] forensics: pid {pid} = "
                              f"{tl_line.split(':', 1)[-1].strip()} "
                              f"<- firewall allow rule must name THIS exe")
    except Exception as e:  # noqa: BLE001 -- diagnostics must never crash the run
        print(f"[mp-smoke] forensics unavailable: {e}")


if __name__ == "__main__":
    sys.exit(main())
