"""Probe: every stop sign and every junction leg on a site, measured.

Reports, for a Lot site spec:

  STOP SIGNS -- every `stop_sign` piece: where it stands, the cut or junction
  its `breaks` tag names, which way its plate faces, the approach that face
  serves (a driver travelling +t or -t along the road the sign stands on, or
  none when the face looks across the road), which side of that driver it is
  on, its lateral offset from the pavement edge, its distance to the
  travelled-way edge of the junction ahead and to the near line of the next
  marked crosswalk ahead.

  JUNCTION LEGS -- every approach to a road-road junction: whether a marked
  crosswalk crosses that leg, the signal poles standing at the junction, the
  stop signs serving that approach, and whether a stop bar is painted in its
  lane.

  FOOTPATH CROSSINGS -- every path cut, and the stop signs tagged to it.

Frames and units: spec/Blender Z-up plan coordinates, metres. `t` is metres
along a road from its `a` end; an offset is metres across it, positive to
the LEFT of travel a->b. Offsets are measured from the pavement edge, which
is the kerb face at `road.width / 2`.

TRAFFIC KEEPS RIGHT. This is the probe's assumption, stated so it can be
argued with: a driver travelling +t has the R kerb on the right.

FACING, measured rather than recalled (2026-09-13, Godot 4.7 `str_to_var` on
the text `lot._godot_transform` writes): the 12 numbers are the basis ROWS,
so a slot yaw is a counterclockwise plan rotation of the module's own frame.
A Zoo `stop_sign` blade faces its Blender -Y, exported Y-up as glTF +Z, so
at slot yaw `y` the plate faces plan `(sin y, -cos y)`. This is derived here
independently of `site_furniture` so the probe can disagree with it.

Sources: the spec is re-planned with `site_streets.roads` and
`site_furniture.plan_furniture` (no mission markers unless `--gameplay`
names an assemble's `site.gameplay.json`, whose `furniture_plan.placed` is
then read instead -- the pieces that job actually wrote). A probe prints
what it measured; it does not name a cause.

    python tools/probe_street_control.py <site.json> [--gameplay <gameplay.json>] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import site_furniture   # noqa: E402
import site_streets     # noqa: E402


def _face(yaw_deg):
    r = math.radians(yaw_deg)
    return (math.sin(r), -math.cos(r))


def _local(road, xy):
    dx, dy = xy[0] - road.a[0], xy[1] - road.a[1]
    return (dx * road.along[0] + dy * road.along[1],
            dx * road.perp[0] + dy * road.perp[1])


def _crosswalk_bands(road, marks):
    """[(t0, t1)] of each marked crosswalk on ``road``: contiguous bars."""
    bars = []
    for m in marks:
        if m["kind"] != "crosswalk_bar" or m["road"] != road.index:
            continue
        t, _o = _local(road, m["at"])
        half = m["size"][0] / 2.0
        bars.append((t - half, t + half))
    bars.sort()
    bands = []
    gap = site_streets.BAR_GAP + 1e-3
    for b0, b1 in bars:
        if bands and b0 - bands[-1][1] <= gap:
            bands[-1] = (bands[-1][0], max(bands[-1][1], b1))
        else:
            bands.append((b0, b1))
    return bands


def _stop_bars(road, marks):
    """[(t0, t1, offset)] of the stop bars on ``road``."""
    out = []
    for m in marks:
        if m["kind"] != "stop_bar" or m["road"] != road.index:
            continue
        t, o = _local(road, m["at"])
        out.append((t - m["size"][0] / 2.0, t + m["size"][0] / 2.0, o))
    return out


def _junctions(road):
    """[(cut, lo, hi)] of the road-road crossings on ``road``."""
    return [(c,) + site_streets.crossing_box(c) for c in road.crossings
            if c.kind == "road"]


def _ahead(road, t, travel):
    """The junction on ``road`` nearest ahead of ``t`` for a driver
    travelling ``travel``: (cut, lo, hi) or None."""
    best = None
    for c, lo, hi in _junctions(road):
        near = lo if travel > 0 else hi
        d = travel * (near - t)
        if d >= -0.5 and (best is None or d < best[0]):
            best = (d, (c, lo, hi))
    return best[1] if best else None


def measure(spec, placed=None):
    roads = site_streets.roads(spec)
    by_index = {r.index: r for r in roads}
    if placed is None:
        placed = site_furniture.plan_furniture(roads, spec.get("buildings") or [])
    marks = site_streets.markings(roads)
    signs, legs, paths = [], [], []

    for p in placed:
        if p["species"] != "stop_sign":
            continue
        road = by_index[p["road"]]
        t, off = _local(road, p["at"])
        fx, fy = _face(p["yaw"])
        along = fx * road.along[0] + fy * road.along[1]
        row = {"name": p["name"], "road": road.index, "kerb": p.get("kerb"),
               "t": round(t, 2), "at": p["at"], "yaw": p["yaw"],
               "breaks": p.get("breaks", ""),
               "face": [round(fx, 3), round(fy, 3)]}
        kind = "?"
        tag = row["breaks"]
        if "@" in tag:
            st = float(tag.split("@")[1])
            if tag.startswith("crossing@"):
                cut = min((c for k in road.kerbs for c in k.cuts),
                          key=lambda c: abs(c.t - st), default=None)
                if cut is not None:
                    kind = f"{cut.kind} cut w={cut.width:g}"
            elif tag.startswith("junction@"):
                kind = "junction mouth"
        row["belongs"] = kind
        plate = site_furniture.SPECIES["stop_sign"][0]
        edge = road.width / 2.0
        row["offset_post"] = round(abs(off) - edge, 2)
        if abs(along) < 0.7:
            row.update(serves="across the road", side="n/a",
                       offset_plate=round(abs(off) - edge, 2),
                       to_junction=None, to_crosswalk=None, approach=None)
        else:
            travel = -1 if along > 0 else 1       # the driver looks at the face
            right_sign = -1 if travel > 0 else 1   # keep right: +t on the R half
            side = "right" if (off > 0) == (right_sign > 0) else "left"
            # the plate lies across the road, so its near edge is half its
            # width nearer the pavement than the post
            row.update(serves=f"travel {'+' if travel > 0 else '-'}t", side=side,
                       offset_plate=round(abs(off) - edge - plate / 2.0, 2))
            inside = [(c, lo, hi) for c, lo, hi in _junctions(road) if lo < t < hi]
            j = _ahead(road, t, travel)
            if inside:
                row.update(to_junction="in box", approach=None)
            elif j is None:
                row.update(to_junction=None, approach=None)
            else:
                c, lo, hi = j
                edge_t = c.t - travel * c.width / 2.0     # crosser's travelled way
                row["to_junction"] = round(travel * (edge_t - t), 2)
                row["approach"] = (road.index, round(c.t, 3), travel)
            cw = [travel * ((b0 if travel > 0 else b1) - t)
                  for b0, b1 in _crosswalk_bands(road, marks)]
            cw = [d for d in cw if d >= -0.5]
            row["to_crosswalk"] = round(min(cw), 2) if cw else None
        signs.append(row)

    for road in roads:
        bands = _crosswalk_bands(road, marks)
        bars = _stop_bars(road, marks)
        for c, lo, hi in _junctions(road):
            other = by_index.get(c.crosser)
            jx, jy = road.point(c.t)
            signals = [p["name"] for p in placed if p["species"] == "traffic_signal"
                       and p["road"] in (road.index, c.crosser)
                       and math.hypot(p["at"][0] - jx, p["at"][1] - jy)
                       <= c.width / 2.0 + c.sidewalk + road.width + road.sidewalk + 3.0]
            for travel in (1, -1):
                near = lo if travel > 0 else hi
                if travel > 0 and near <= road.slab[0] + 0.5:
                    continue
                if travel < 0 and near >= road.slab[1] - 0.5:
                    continue
                inside = (lambda b: lo - 0.05 <= b[0] and b[1] <= c.t) if travel > 0 \
                    else (lambda b: c.t <= b[0] and b[1] <= hi + 0.05)
                marked = any(inside(b) for b in bands)
                lane = -1 if travel > 0 else 1                # keep right
                stop_bar = [b for b in bars if (b[2] > 0) == (lane > 0)
                            and travel * (near - b[1 if travel > 0 else 0]) >= -0.05
                            and travel * (near - b[1 if travel > 0 else 0]) <= 3.0]
                wrong_bar = [b for b in bars if (b[2] > 0) != (lane > 0)
                             and travel * (near - b[1 if travel > 0 else 0]) >= -0.05
                             and travel * (near - b[1 if travel > 0 else 0]) <= 3.0]
                serving = [s for s in signs
                           if s.get("approach") == (road.index, round(c.t, 3), travel)]
                legs.append({
                    "road": road.index, "crosser": c.crosser,
                    "junction_t": round(c.t, 2), "travel": travel,
                    "terminal_here": (other is not None and c.terminal),
                    "ped_access": bool(road.sidewalk or c.sidewalk),
                    "crosswalk": marked, "signals": signals,
                    "stop_signs": [f"{s['name']}({s['side']},{s['to_junction']}m)"
                                   for s in serving],
                    "stop_bar_right_lane": bool(stop_bar),
                    "stop_bar_left_lane": bool(wrong_bar)})
        for k in road.kerbs:
            for cut in k.cuts:
                if cut.kind != "path":
                    continue
                tagged = [s["name"] for s in signs if s["road"] == road.index
                          and s["kerb"] == k.side
                          and s["breaks"] == f"crossing@{cut.t:.1f}"]
                paths.append({"road": road.index, "kerb": k.side,
                              "t": round(cut.t, 2), "width": cut.width,
                              "stop_signs": tagged})
    return {"signs": signs, "legs": legs, "paths": paths,
            "counts": {"stop_sign": len(signs),
                       "traffic_signal": sum(1 for p in placed
                                             if p["species"] == "traffic_signal")}}


def _table(rows, cols):
    if not rows:
        return "  (none)"
    cells = [[("-" if r.get(c) is None else str(r.get(c))) for c in cols] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]
    line = "  " + " | ".join(c.ljust(w) for c, w in zip(cols, widths))
    rule = "  " + "-+-".join("-" * w for w in widths)
    return "\n".join([line, rule] + ["  " + " | ".join(v.ljust(w) for v, w in zip(row, widths))
                                     for row in cells])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--gameplay", help="read furniture_plan.placed from this file")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    spec = json.load(open(a.spec, encoding="utf-8"))
    placed = None
    source = "re-planned by site_furniture.plan_furniture (no markers)"
    if a.gameplay:
        placed = json.load(open(a.gameplay, encoding="utf-8"))["furniture_plan"]["placed"]
        source = f"furniture_plan.placed from {a.gameplay}"
    res = measure(spec, placed)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"spec: {a.spec}")
    print(f"pieces: {source}")
    print(f"counts: {res['counts']}")
    print("\nSTOP SIGNS (plan metres; offsets from the pavement edge; distances "
          "along the road, + = before it)")
    print(_table(res["signs"], ["name", "road", "kerb", "t", "yaw", "belongs",
                                "face", "serves", "side", "offset_post",
                                "offset_plate", "to_junction", "to_crosswalk"]))
    print("\nJUNCTION LEGS (travel = direction of the approaching driver along the road)")
    print(_table(res["legs"], ["road", "crosser", "junction_t", "travel", "ped_access",
                               "crosswalk", "signals", "stop_signs",
                               "stop_bar_right_lane", "stop_bar_left_lane"]))
    print("\nFOOTPATH CROSSINGS")
    print(_table(res["paths"], ["road", "kerb", "t", "width", "stop_signs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
