#!/usr/bin/env python3
"""Which enemy set does the pipeline plan cover for, and which does it ship?

READ-ONLY apart from a temp directory it makes for the fixture.

WHAT v1 ESTABLISHED, AND WHERE IT WAS WRONG

v1 tested the hypothesis that `tests/test_site_cover.py` diverges from the
pipeline because it omits `solids`. REFUTED: the test's no-solids set came back
identical to the pipeline's `solids=True` call from `lot.py:1257`, to every
decimal printed. The divergence is not the test's.

What it found instead: TWO `place_enemies` calls fire inside one `lot.assemble`,
from `lot.py:1874` and `lot.py:1257`, and they return DIFFERENT positions --

    1874: (-16.000, 31.500) (10.000, 28.500) (50.000, 31.500)
          (50.000, 27.500) (10.000, 32.500) (-30.000, 64.500)
    1257: ( -8.332, 43.500) (16.786, 28.500) (55.429, 31.500)
          (45.929, 31.500) ( 7.286, 28.500) (-31.357, -13.000)

and `lot.py:1892` builds `cover_points` from the FIRST while the walk scene is
written from the second. WHY the two differ is not established, which is what
this version measures: it records each call's INPUTS -- the positions dict, the
occluder set and its source, and how much `site_spec["cover"]` had grown by
then -- not just what came out.

v1 also reported `plan_cover ... pieces=0 still_open=?` because it read fields
off `CoverPlan` that do not exist. `CoverPlan` carries `cover`, `open_lines`,
`unbreakable`, `pinches`. That was a checker written against a guessed schema,
which is the failure `CLAUDE.md` names in its own third rule, and the `?` was
the only reason it did not read as a real zero. This version enumerates fields
with `dataclasses.fields()` so an unrecognised shape cannot be silently
reported as empty.

This prints what it measured and stops.

USAGE

    python tools\\probe_r51_cover_enemies.py
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import re
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
LOT = os.path.dirname(HERE)
TESTS = os.path.join(LOT, "tests")
for p in (LOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

SELF = os.path.basename(__file__)


def _fmt(pt, nd=3):
    return "(" + ", ".join(f"{v:.{nd}f}" for v in pt) + ")"


def _caller():
    for f in reversed(traceback.extract_stack()[:-1]):
        if os.path.basename(f.filename) != SELF:
            return f"{os.path.basename(f.filename)}:{f.lineno}"
    return "?"


def _describe(obj, label):
    """Every field the object actually declares, by name, with sizes.

    Enumerated rather than guessed. A field this probe does not know about
    still gets printed; a field it expects and cannot find is impossible to
    mistake for an empty one.
    """
    out = [f"    {label}: {type(obj).__name__}"]
    if not dataclasses.is_dataclass(obj):
        out.append(f"      (not a dataclass) repr={obj!r:.120}")
        return out
    for f in dataclasses.fields(obj):
        v = getattr(obj, f.name)
        if isinstance(v, (list, tuple)):
            out.append(f"      {f.name:14s} len={len(v)}")
        else:
            out.append(f"      {f.name:14s} = {v!r}")
    return out


def main() -> int:
    import site_cover
    import site_spawns
    import test_site_cover as T          # the fixture, from the file that owns it
    import lot

    place_calls, cover_calls = [], []
    real_place = site_spawns.place_enemies
    real_plan = site_cover.plan_cover

    def spy_place(site_spec, positions, **kw):
        solids = kw.get("solids", None)
        # Ask the module the same question it is about to ask itself, so the
        # occluder set is reported rather than inferred from `solids is None`.
        try:
            occ, src = site_spawns.sight_occluders(site_spec, solids)
            occ_n, occ_src = len(occ), src
        except Exception as exc:                       # pragma: no cover
            occ_n, occ_src = -1, f"<raised {type(exc).__name__}: {exc}>"
        rec = {
            "caller": _caller(),
            "kw": sorted(kw),
            "solids_is_none": solids is None,
            "solids_complete": getattr(solids, "complete", "<no attr>"),
            "occluders": occ_n,
            "occluder_source": occ_src,
            "spec_cover_len": len((site_spec or {}).get("cover", []) or []),
            "in_positions": {k: tuple(v) for k, v in (positions or {}).items()
                             if k in ("spawn", "objective", "extraction")},
        }
        plan = real_place(site_spec, positions, **kw)
        rec["positions"] = [tuple(p) for p in plan.positions]
        rec["plan_obj"] = plan
        place_calls.append(rec)
        return plan

    def spy_plan(points, *a, **kw):
        rec = {"caller": _caller(),
               "points": {k: tuple(v) for k, v in (points or {}).items()}}
        res = real_plan(points, *a, **kw)
        rec["result"] = res
        cover_calls.append(rec)
        return res

    tmp = tempfile.mkdtemp(prefix="r51probe_")
    site_spawns.place_enemies = spy_place
    site_cover.plan_cover = spy_plan
    try:
        spec_path = T._open_site(tmp)
        out = os.path.join(tmp, "out")
        result = lot.assemble(spec_path, out, walkable=True)
    finally:
        site_spawns.place_enemies = real_place
        site_cover.plan_cover = real_plan

    bar = "=" * 78
    print(f"\n{bar}\nplace_enemies calls during one lot.assemble\n{bar}")
    for i, c in enumerate(place_calls):
        print(f"\n  call {i}  from {c['caller']}   kwargs={c['kw'] or '(none)'}")
        print(f"    solids is None      : {c['solids_is_none']}"
              f"    .complete = {c['solids_complete']}")
        print(f"    occluders it will use: {c['occluders']} rect(s), "
              f"source = {c['occluder_source']}")
        print(f"    site_spec['cover']   : {c['spec_cover_len']} piece(s) at call time")
        print("    INPUT positions:")
        for k, v in c["in_positions"].items():
            print(f"      {k:11s} {_fmt(v)}")
        print("    OUTPUT enemies:")
        for j, p in enumerate(c["positions"]):
            print(f"      Enemy_{j}: {_fmt(p)}")

    # Which inputs differ between calls, stated rather than eyeballed.
    if len(place_calls) >= 2:
        print(f"\n  -- differences between call 0 and call 1")
        a, b = place_calls[0], place_calls[1]
        for key in ("solids_is_none", "solids_complete", "occluders",
                    "occluder_source", "spec_cover_len", "in_positions"):
            same = a[key] == b[key]
            print(f"    {key:16s} {'SAME' if same else 'DIFFERS'}"
                  f"{'' if same else f'   {a[key]!r}  vs  {b[key]!r}'}")
        print(f"    {'positions':16s} "
              f"{'SAME' if a['positions'] == b['positions'] else 'DIFFERS'}")

    print(f"\n{bar}\nplan_cover calls -- every declared field, none guessed\n{bar}")
    for i, c in enumerate(cover_calls):
        print(f"\n  call {i}  from {c['caller']}")
        print("    points it was given:")
        for k, v in sorted(c["points"].items()):
            print(f"      {k:18s} {_fmt(v)}")
        for line in _describe(c["result"], "result"):
            print(line)

    # Which recorded enemy set do plan_cover's Enemy_* points equal?
    if cover_calls:
        pts = cover_calls[0]["points"]
        cov_en = [pts[k] for k in sorted(
            (k for k in pts if k.startswith("Enemy_")),
            key=lambda s: int(s.split("_")[1]))]
        print("\n  cover_points' enemies match which place_enemies call?")
        for i, c in enumerate(place_calls):
            match = all(math.isclose(a, b, abs_tol=1e-9)
                        for e, p in zip(cov_en, c["positions"])
                        for a, b in zip(e, p[:2])) and \
                len(cov_en) == len(c["positions"])
            print(f"    call {i} ({c['caller']}): {'MATCH' if match else 'no'}")

    # What the shipped scenes actually carry.
    print(f"\n{bar}\nEnemy_ nodes in the scenes that were written\n{bar}")
    print(f"  result keys: {sorted(result)}")
    seen = set()
    for key, val in sorted(result.items()):
        if not isinstance(val, str) or not val.endswith(".tscn"):
            continue
        if not os.path.exists(val) or val in seen:
            continue
        seen.add(val)
        txt = open(val, encoding="utf-8").read()
        if "LT_EnemySpawnPoints" not in txt:
            continue
        blk = txt[txt.index('name="LT_EnemySpawnPoints"'):]
        end = blk.find('name="LT_ObjectivePoint"')
        blk = blk[:end] if end > 0 else blk
        vecs = [tuple(float(n) for n in
                      ln[len("transform = Transform3D("):-1].split(",")[9:12])
                for ln in blk.splitlines()
                if ln.startswith("transform = Transform3D(")]
        print(f"\n  {key} -> {os.path.basename(val)}")
        for j, (gx, gy, gz) in enumerate(vecs):
            # Godot (x, z+lift, -y) back to site (x, y)
            print(f"    Enemy_{j}: godot {_fmt((gx, gy, gz))}  "
                  f"-> site {_fmt((gx, -gz))}")
        for i, c in enumerate(place_calls):
            match = len(vecs) == len(c["positions"]) and all(
                math.isclose(gx, p[0], abs_tol=1e-3)
                and math.isclose(-gz, p[1], abs_tol=1e-3)
                for (gx, _gy, gz), p in zip(vecs, c["positions"]))
            print(f"      == place_enemies call {i} ({c['caller']})? "
                  f"{'MATCH' if match else 'no'}")

    # The failing assertion, against each candidate set.
    text = open(result["scene"], encoding="utf-8").read()
    rects = T._cover_rects_from_scene(text)
    spec = json.load(open(spec_path, encoding="utf-8"))
    walk_pos = result["walk_positions"]
    crew = tuple(walk_pos["spawn"][:2])
    sight = rects + site_spawns.footprints(spec, margin=0.0)

    print(f"\n{bar}\nthe failing assertion, per candidate enemy set\n{bar}")
    print(f"  crew (walk_pos['spawn']): {_fmt(crew)}")
    print(f"  cover rects read back from the scene: {len(rects)}")
    cands = [("TEST recomputation (no solids)", real_place(spec, walk_pos).positions)]
    cands += [(f"call {i} from {c['caller']}", c["positions"])
              for i, c in enumerate(place_calls)]
    for label, enemies in cands:
        print(f"\n  -- {label}")
        for i, e in enumerate(enemies):
            ex, ey = e[0], e[1]
            span = site_cover.open_span(crew, (ex, ey), sight)
            dist = math.dist(crew, (ex, ey))
            note = ("   <- span == dist, nothing between them"
                    if abs(span - dist) < 1e-9 else "")
            print(f"     Enemy_{i}: {_fmt((ex, ey))} dist={dist:9.5f} "
                  f"span={span:9.5f} {'ok' if span < dist - 1e-6 else 'FAILS'}{note}")

    print(f"\n(fixture left in {tmp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
