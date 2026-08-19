"""Where dressing MAY go on an assembled site, and where it may not.

Layer 3 surface dressing (`docs/SURFACE_DRESSING.md`) needs to know two things
before it can place anything: which regions of the site are dressable and how
much of each must stay legible, and which regions are off limits because
something else already claimed them. The schema
(`level_factory/schemas/surface_dressing.v1.json`) is explicit about who
answers:

    zones       "Semantic regions from Deli Counter / Lot -- not invented here."
    traversed   "taken from Lot's walkable surfaces, not asserted by the
                 dressing planner."
    exclusions  "Every entry must name what declared it; an exclusion nobody
                 declared is a preference."

So Lot answers. This module is that answer, and its rule is that EVERY zone
and every exclusion traces back to a key in the site spec or to a constant
some other Lot module already derived. Nothing here invents a number about
the site.

    spec key        becomes
    ------------    ----------------------------------------------------
    ground          the open ground zone (via site_extent.resolve, which
                    is the module that decides the real plate rect --
                    five places used to assume it was centred and all
                    five were wrong)
    paths           one gameplay_path corridor per path, at its own width
    courtyards      one play_space zone each, at their own size
    buildings       a wall_base band around each footprint
    perimeter       everything outside site_extent.required_rect, which is
                    by definition beyond the content plus clearance
    cover           cover_edge exclusions at site_cover.MARKER_CLEARANCE
    spawn /         spawn and objective exclusions on the named buildings
    objective /
    extraction

WHAT IT DOES NOT DO. It does not place anything and it has no opinion about
what a zone should be dressed WITH -- that is the planner's job, one stage
later. It also does not decide the honesty rule; it carries the capsule so
whoever does can check it without re-deriving it.

Pure: a spec dict in, dicts out. No Godot, no Blender, stdlib only.
"""
from __future__ import annotations

import math

import site_cover
import site_extent
import site_steps

CATEGORY = "site_surfaces"

CODE_NO_GROUND = "LOT_SURFACE_NO_GROUND"
CODE_FOOTPRINT_UNKNOWN = "LOT_SURFACE_FOOTPRINT_UNKNOWN"
CODE_NO_DRESSABLE_ZONE = "LOT_SURFACE_NO_DRESSABLE_ZONE"
CODE_MARKER_UNRESOLVED = "LOT_SURFACE_MARKER_UNRESOLVED"
CODE_FOOTPRINTS_MERGED = "LOT_SURFACE_FOOTPRINTS_MERGED"

# The player this site is built for. Same defaults the rest of Lot uses; a
# caller with a different agent contract passes its own.
DEFAULT_CAPSULE_RADIUS_M = 0.4
DEFAULT_FLOOR_MAX_ANGLE_DEG = 45.0

# Height bands, verbatim from the Surface Dressing guide. Carried so the plan
# and the gate agree on what "low" means without either re-deciding it.
BANDS = {
    "micro": {"min_m": 0.02, "max_m": 0.10},
    "low": {"min_m": 0.10, "max_m": 0.30},
    "medium": {"min_m": 0.30, "max_m": 0.70},
    "tall": {"min_m": 0.70, "max_m": 1.50},
}

# Surface Visibility Budget: the fraction of a zone's gameplay surface that
# must still read from normal viewing angles. Hard surface is the visual
# truth; dressing interrupts it and must not replace it. The bands are
# gameplay_path 0.80-1.00, play_space 0.60-0.80, environmental_edge 0.30-0.60;
# these are the midpoints, so a planner has room in both directions and no
# zone starts at a limit.
VISIBILITY = {
    "gameplay_path": 0.90,
    "play_space": 0.70,
    "environmental_edge": 0.45,
    "decorative": 0.0,
}

# Density readings from the guide: sidewalk centre low, sidewalk edge medium,
# wall seam high, abandoned corner very_high.
DENSITY_BY_ZONE = {
    "path": "low",
    "wall_base": "high",
    "courtyard": "medium",
    "perimeter": "very_high",
    "open": "medium",
}

# Zone precedence, most restrictive first. Zones are AABBs and AABBs overlap,
# so a point can be inside several; `zone_for` resolves by this order and the
# emitted list is in it. A path crossing a wall base is still a path -- the
# thing that matters there is that the route stays legible.
PRECEDENCE = ("path", "wall_base", "courtyard", "perimeter", "open")


def annotate_footprints(site_spec, base_dir):
    """Fill in each building's `_footprint` from its gameplay.json.

    WHY THIS IS NEEDED AT ALL. `lot.merge_gameplay` writes
    `b["_footprint"] = gp.get("footprint")` onto the spec IN MEMORY during a
    Lot run, and nothing persists the annotated spec. So a site spec read off
    disk never has footprints, `rotated_footprint` returns None for every
    building, and every wall-base seam goes undressed -- reported, but
    undressed. Measured on the real coldrun_pawn_job spec: four buildings,
    four `LOT_SURFACE_FOOTPRINT_UNKNOWN` findings, zero wall_base zones, and
    the guide says the wall seam is where density should be HIGHEST.

    It calls Lot's own function rather than re-reading the gameplay files.
    `merge_gameplay` returns a merged site dict and annotates the spec as a
    side effect; only the side effect is wanted here, which is worth stating
    because calling a function for its side effect otherwise reads as a
    mistake. Re-implementing the read would put the same rule in two places,
    and this module's discipline is that every number traces to the one place
    that already derived it.

    ONE BUILDING AT A TIME, AND THAT IS NOT AN OPTIMISATION. Called on a whole
    spec, `merge_gameplay` raises ValueError on the first building that
    declares no `glb` or `scene` -- reasonable for its own job, since it is
    assembling geometry -- and every building AFTER that one goes unannotated.
    Measured: a four-building spec with one geometry-less entry annotated the
    first building, raised, and left three bare, which reads on the output as
    a site whose walls mostly do not exist. Merging each building through its
    own single-entry spec isolates the failure to the building that caused it.
    The building dict is passed by reference, so the annotation still lands on
    the caller's spec.

    Returns (annotated_count, total, findings). Never raises: a spec with no
    gameplay files is a legitimate greybox, and the existing
    FOOTPRINT_UNKNOWN finding already says what that costs.
    """
    buildings = site_spec.get("buildings") or []
    findings = []
    if not base_dir or not buildings:
        return 0, len(buildings), findings
    before = sum(1 for b in buildings if b.get("_footprint"))
    try:
        import lot as _lot                       # flat layout: same directory
    except ImportError as exc:
        findings.append(_finding(
            CODE_FOOTPRINT_UNKNOWN, "warn",
            f"could not import lot to merge footprints ({exc}); wall bases "
            "are reported as unreadable below"))
        return before, len(buildings), findings

    refused = []
    for b in buildings:
        if b.get("_footprint") or not b.get("gameplay"):
            continue
        one = {"name": site_spec.get("name", "site"), "buildings": [b],
               "ground": site_spec.get("ground", {})}
        try:
            _lot.merge_gameplay(one, str(base_dir))
        except (OSError, KeyError, ValueError, TypeError) as exc:
            refused.append(f"{b.get('id', '?')} ({exc.__class__.__name__})")
    after = sum(1 for b in buildings if b.get("_footprint"))
    if after > before:
        findings.append(_finding(
            CODE_FOOTPRINTS_MERGED, "info",
            f"read footprints for {after - before} of {len(buildings)} "
            f"buildings from {base_dir} via lot.merge_gameplay"))
    if refused:
        findings.append(_finding(
            CODE_FOOTPRINT_UNKNOWN, "warn",
            "lot.merge_gameplay refused " + ", ".join(sorted(refused))
            + " -- their footprints were not read. Each building is merged "
              "on its own, so this cost only the ones named."))
    return after, len(buildings), findings


def _agent_radius(nav_bake=None) -> float:
    """Agent radius in metres, from the nav bake when there is one.

    Same source `site_cover.min_passable_gap` reads, and the same fallback
    (0.4 m) it falls back to.
    """
    if nav_bake:
        try:
            return float(nav_bake.get("agent_radius_m") or 0.0) or \
                DEFAULT_CAPSULE_RADIUS_M
        except (TypeError, ValueError):
            pass
    return DEFAULT_CAPSULE_RADIUS_M


def wall_base_band_m(nav_bake=None) -> float:
    """How wide the band of dressing hugging a wall is allowed to be.

    One agent radius. A band that narrow cannot obstruct passage even if every
    object in it were solid, which matters because these objects are NOT solid
    and the whole risk of the layer is looking like it should stop you. Taken
    from the nav bake rather than chosen, so it tracks the body the level is
    actually built for.
    """
    return _agent_radius(nav_bake)


def capsule_block(radius_m=DEFAULT_CAPSULE_RADIUS_M,
                  floor_max_angle_deg=DEFAULT_FLOOR_MAX_ANGLE_DEG) -> dict:
    """The manifest's `capsule` block, with the honesty number already solved.

    Carried in the artifact so the gate can check a placement without
    re-deriving `unassisted_step_max` -- and so a plan made for one body is
    obviously a plan for that body when someone changes the capsule later.
    """
    return {
        "radius_m": float(radius_m),
        "floor_max_angle_deg": float(floor_max_angle_deg),
        "unassisted_step_max_m": round(
            site_steps.unassisted_step_max_m(radius_m, floor_max_angle_deg), 5),
        "source": "lot/site_steps.py:unassisted_step_max_m",
    }


def _finding(code, severity, message):
    return {"category": CATEGORY, "code": code, "severity": severity,
            "message": message}


# Five decimals, matching `capsule_block`. Four rounded the zone ceiling to
# 0.1172 against an unassisted_step_max of 0.11716 -- forty microns of height
# the honesty rule does not allow, offered by the artifact that carries the
# rule. The amount is absurd and the direction is the point: a box must never
# advertise more room than the number it was cut from.
AABB_DIGITS = 5


def _aabb(rect, z_lo, z_hi):
    """Schema aabb: [xmin,ymin,zmin,xmax,ymax,zmax] in spec/Blender Z-up."""
    r = AABB_DIGITS
    return [round(rect[0], r), round(rect[1], r), round(z_lo, r),
            round(rect[2], r), round(rect[3], r), round(z_hi, r)]


def _zone(zone_id, kind, family, rect, z_lo, z_hi, exposure, tags):
    return {
        "surface_zone_id": zone_id,
        "declared_by": "lot",
        "kind": kind,
        "traversed": True,
        "aabb": _aabb(rect, z_lo, z_hi),
        "tags": sorted(set(tags) | {f"zone_family:{family}"}),
        "exposure_class": exposure,
        "surface_visibility": VISIBILITY[exposure],
        "density": DENSITY_BY_ZONE[family],
    }


def _path_segments(site_spec):
    """Path endpoints in SPEC/PLAN space.

    Deliberately not `site_steps.routes`, which returns the same segments in
    GODOT space (x, -y_plan) because that is what its caller needs. This
    manifest declares `spec/Blender Z-up raw coords`, and silently mixing the
    two is the exact class of bug this repo has already paid for twice.
    """
    bld = {b["id"]: b for b in site_spec.get("buildings", []) or []}
    out = []
    for i, p in enumerate(site_spec.get("paths", []) or []):
        try:
            a = bld[p["from"]]["at"] if "from" in p else p["a"]
            b = bld[p["to"]]["at"] if "to" in p else p["b"]
        except (KeyError, TypeError):
            continue
        label = (f"{p.get('from', 'a')}_{p.get('to', 'b')}"
                 if "from" in p else f"seg{i}")
        out.append((label, (float(a[0]), float(a[1])),
                    (float(b[0]), float(b[1])), float(p.get("width", 6.0))))
    return out


def corridor_boxes(a, b, width, *, step_frac=0.5):
    """A fat segment as a chain of axis-aligned boxes.

    A corridor is not a box. The first version of this emitted one AABB per
    path, and on a real spec three diagonal 5 m paths produced boxes 47 x 51 m
    that swallowed the entire site -- every square metre inherited
    `gameplay_path`, the strictest visibility budget, and the density
    variation the guide asks for (sidewalk centre low, wall seam high,
    abandoned corner very high) disappeared into one uniform sparse scatter.
    Being "conservative" is not free when the conservative answer is applied
    to everything.

    So the corridor ships as `width x width` boxes centred on its centreline
    and stepped at half a width, which cannot leave a gap. A 45-degree
    corridor still over-claims by about 0.2 of its width at the diagonal --
    an axis-aligned box cannot do better -- but that is metres instead of
    tens of metres, and the zones stay where the route is.
    """
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    half = float(width) / 2.0
    length = math.hypot(bx - ax, by - ay)
    if length <= 1e-9:
        return [(ax - half, ay - half, ax + half, ay + half)]
    step = max(1e-6, float(width) * step_frac)
    n = max(1, int(math.ceil(length / step)))
    out = []
    for i in range(n + 1):
        t = min(1.0, (i * step) / length)
        cx, cy = ax + (bx - ax) * t, ay + (by - ay) * t
        out.append((cx - half, cy - half, cx + half, cy + half))
    return out


def _intersect(a, b):
    """Overlap of two rects, or None when they do not touch."""
    r = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return r if r[0] < r[2] and r[1] < r[3] else None


def _annulus_strips(outer, inner):
    """`outer` minus `inner`, as up to four non-overlapping boxes.

    South and north span the full width; west and east take only the band
    between them, so no square metre of ground belongs to two perimeter
    strips and the visibility budget stays countable.
    """
    if inner is None or inner == outer:
        return []
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    out = []
    if iy0 > oy0:
        out.append((ox0, oy0, ox1, iy0))
    if iy1 < oy1:
        out.append((ox0, iy1, ox1, oy1))
    if ix0 > ox0:
        out.append((ox0, max(oy0, iy0), ix0, min(oy1, iy1)))
    if ix1 < ox1:
        out.append((ix1, max(oy0, iy0), ox1, min(oy1, iy1)))
    return [r for r in out if r[0] < r[2] and r[1] < r[3]]


def zones(site_spec, *, ground=None, nav_bake=None, capsule=None):
    """Dressable regions, most restrictive first. Returns (zones, findings)."""
    cap = capsule or capsule_block()
    z_hi = cap["unassisted_step_max_m"]      # the tallest legal thing here
    z_lo = 0.0
    findings = []
    out = []

    g = ground or site_extent.resolve(site_spec)
    if g.rect is None:
        findings.append(_finding(
            CODE_NO_GROUND, "info",
            "site declares no ground plate; only interior surfaces exist and "
            "this module has nothing outdoors to offer"))
        return out, findings

    # --- paths: the routes someone is meant to walk -------------------------
    for label, a, b, width in _path_segments(site_spec):
        for j, rect in enumerate(corridor_boxes(a, b, width)):
            out.append(_zone(f"path_{label}_s{j:02d}", "ground", "path", rect,
                             z_lo, z_hi, "gameplay_path",
                             ["route", f"path:{label}"]))

    # --- wall bases: the seam where ground meets a building -----------------
    band = wall_base_band_m(nav_bake)
    unknown = []
    for b in site_spec.get("buildings", []) or []:
        fp = site_extent.rotated_footprint(b)
        if fp is None:
            unknown.append(str(b.get("id", "?")))
            continue
        out.append(_zone(f"wall_base_{b['id']}", "wall_base", "wall_base",
                         site_extent.grow(fp, band), z_lo, z_hi,
                         "environmental_edge", ["seam", f"building:{b['id']}"]))
    if unknown:
        findings.append(_finding(
            CODE_FOOTPRINT_UNKNOWN, "warn",
            "no readable footprint for " + ", ".join(sorted(unknown))
            + " -- their wall bases are not offered for dressing. A raw site "
              "spec carries no footprint; run this on a spec merge_gameplay "
              "has annotated, or these seams stay bare and nothing says why."))

    # --- courtyards ---------------------------------------------------------
    for i, c in enumerate(site_spec.get("courtyards", []) or []):
        at = c.get("at") or (0.0, 0.0)
        rect = site_extent.rect_of(float(at[0]), float(at[1]),
                                   float(c.get("size_x", 0.0)),
                                   float(c.get("size_y", 0.0)))
        out.append(_zone(f"courtyard_{i}", "ground", "courtyard", rect,
                         z_lo, z_hi, "play_space", ["courtyard"]))

    # --- perimeter: outside the content, by definition -----------------------
    # `required_rect` is content + CLEARANCE. Anything beyond it is ground no
    # gameplay element asked for, which is what "environmental edge" means --
    # so the boundary is read off Lot's own extent maths, not eyeballed.
    #
    # The perimeter is an ANNULUS and a zone is a box, so it ships as the four
    # strips the annulus is made of. Emitting the whole plate instead would
    # have made the perimeter contain the play area, and "very_high density
    # everywhere" is not what an environmental edge means.
    required = site_extent.required_rect(site_spec)
    inner = g.rect
    if required is not None:
        inner = _intersect(g.rect, required) or g.rect
    for k, strip in enumerate(_annulus_strips(g.rect, inner)):
        out.append(_zone(f"perimeter_edge_{k}", "ground", "perimeter", strip,
                         z_lo, z_hi, "environmental_edge",
                         ["outside_required_rect"]))

    # --- everything else ----------------------------------------------------
    out.append(_zone("open_ground", "ground", "open", inner, z_lo, z_hi,
                     "play_space", ["remainder"]))

    order = {f: i for i, f in enumerate(PRECEDENCE)}
    out.sort(key=lambda z: order[_family_of(z)])
    if not out:
        findings.append(_finding(CODE_NO_DRESSABLE_ZONE, "warn",
                                 "no dressable zone on this site"))
    return out, findings


def _family_of(zone) -> str:
    for t in zone["tags"]:
        if t.startswith("zone_family:"):
            return t.split(":", 1)[1]
    return "open"


def exclusions(site_spec):
    """Regions dressing must keep out of. Returns (exclusions, findings)."""
    out, findings = [], []
    bld = {b["id"]: b for b in site_spec.get("buildings", []) or []}

    for i, c in enumerate(site_spec.get("cover", []) or []):
        at = c.get("at")
        if not at:
            continue
        out.append({
            "tag": "cover_edge",
            "declared_by": "lot",
            "pos": [float(at[0]), float(at[1]), 0.0],
            # site_cover's own clearance for a placed marker. A cover piece
            # whose base is buried in scatter stops reading as cover, and
            # cover that does not read is the same as cover that is not there.
            "radius_m": site_cover.MARKER_CLEARANCE,
        })

    for key, tag in (("spawn", "spawn"), ("objective", "objective"),
                     ("extraction", "objective")):
        ref = site_spec.get(key)
        if not ref:
            continue
        b = bld.get(ref)
        if b is None or not b.get("at"):
            findings.append(_finding(
                CODE_MARKER_UNRESOLVED, "warn",
                f"{key}={ref!r} names no placed building; no exclusion "
                "emitted for it, so that ground is dressable and nothing "
                "says it should not be"))
            continue
        out.append({
            "tag": tag,
            "declared_by": "lot",
            "pos": [float(b["at"][0]), float(b["at"][1]), 0.0],
            "radius_m": site_cover.MARKER_CLEARANCE,
            })
    return out, findings


def surfaces(site_spec, *, nav_bake=None, radius_m=DEFAULT_CAPSULE_RADIUS_M,
             floor_max_angle_deg=DEFAULT_FLOOR_MAX_ANGLE_DEG, base_dir=None):
    """The `capsule`, `bands`, `zones` and `exclusions` blocks of a
    `surface-dressing/1` manifest, ready for a planner to add `orders` to.

    Returns those blocks plus `findings`. It is deliberately NOT a whole
    manifest: `site_id`, `source`, `seed` and `orders` belong to whoever
    plans, and a half-filled artifact that validates is worse than a fragment
    that obviously is one.
    """
    cap = capsule_block(radius_m, floor_max_angle_deg)
    # Annotate BEFORE computing zones: `zones` reads `_footprint` and reports
    # every building it cannot read, so merging afterwards would produce a
    # correct answer with a warning attached saying it was not.
    _, _, mf = annotate_footprints(site_spec, base_dir)
    zs, zf = zones(site_spec, nav_bake=nav_bake, capsule=cap)
    xs, xf = exclusions(site_spec)
    return {
        "space": "spec/Blender Z-up raw coords",
        "capsule": cap,
        "bands": {k: dict(v) for k, v in BANDS.items()},
        "zones": zs,
        "exclusions": xs,
        "findings": mf + zf + xf,
    }


def zone_for(point, zone_list):
    """The zone a point belongs to, resolving overlap by PRECEDENCE.

    Zones are boxes and boxes overlap, so "which zone is this in" has to have
    one answer or the visibility budget is meaningless -- a placement counted
    against two budgets is counted against neither. The rule lives here, with
    the data, so the planner and any later gate cannot disagree about it.
    """
    x, y = float(point[0]), float(point[1])
    best, best_rank = None, len(PRECEDENCE) + 1
    order = {f: i for i, f in enumerate(PRECEDENCE)}
    for z in zone_list:
        a = z["aabb"]
        if a[0] <= x <= a[3] and a[1] <= y <= a[4]:
            rank = order.get(_family_of(z), len(PRECEDENCE))
            if rank < best_rank:
                best, best_rank = z, rank
    return best


def excluded(point, exclusion_list, *, radius_m=0.0):
    """Exclusion tags a point falls inside, given the placement's own radius.

    Returns the list of tags, so a caller can record `cleared_exclusions` with
    what it actually tested rather than an empty array that the schema warns
    means "untested, not clean".
    """
    x, y = float(point[0]), float(point[1])
    hit = []
    for e in exclusion_list:
        r = float(e.get("radius_m") or 0.0) + float(radius_m)
        pos = e.get("pos")
        if pos is not None and r > 0.0:
            if math.hypot(x - float(pos[0]), y - float(pos[1])) <= r:
                hit.append(e["tag"])
                continue
        box = e.get("aabb")
        if box and box[0] - r <= x <= box[3] + r and box[1] - r <= y <= box[4] + r:
            hit.append(e["tag"])
    return sorted(set(hit))


# ---------------------------------------------------------------------------
# CLI. level_factory adapters invoke tools as COMMANDS, so a module the
# pipeline needs to run has to be one. Kept at the bottom and importing
# nothing new, so importing this module stays as cheap as it was.
# ---------------------------------------------------------------------------

def main(argv=None):
    import argparse
    import json
    import os
    import sys

    ap = argparse.ArgumentParser(
        prog="site_surfaces",
        description="Dressable zones and exclusions for an assembled site.")
    ap.add_argument("spec", help="site spec JSON (post merge_gameplay, so "
                                 "building footprints are annotated)")
    ap.add_argument("--out", help="write here instead of stdout")
    ap.add_argument("--radius-m", type=float, default=DEFAULT_CAPSULE_RADIUS_M)
    ap.add_argument("--floor-max-angle-deg", type=float,
                    default=DEFAULT_FLOOR_MAX_ANGLE_DEG)
    ap.add_argument("--nav-bake", help="nav bake JSON, for the agent radius")
    ap.add_argument("--base-dir", default=None,
                    help="where the buildings' gameplay.json files live, so "
                         "footprints can be merged in and wall bases dressed. "
                         "Defaults to the spec's own directory, which is where "
                         "they sit for every spec in lot/specs. Pass an empty "
                         "string to skip the merge.")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if anything was reported. Unreadable "
                         "building footprints are a warn by default because a "
                         "raw spec legitimately has none; in a pipeline they "
                         "mean the wall seams silently went undressed.")
    a = ap.parse_args(argv)

    with open(a.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    nav = None
    if a.nav_bake:
        with open(a.nav_bake, encoding="utf-8") as fh:
            nav = json.load(fh)

    base = a.base_dir if a.base_dir is not None else os.path.dirname(
        os.path.abspath(a.spec))
    out = surfaces(spec, nav_bake=nav, radius_m=a.radius_m,
                   floor_max_angle_deg=a.floor_max_angle_deg,
                   base_dir=base or None)
    text = json.dumps(out, indent=1, sort_keys=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)

    for f in out["findings"]:
        sys.stderr.write(f"[{f['severity']}] {f['code']}: {f['message']}\n")
    if a.strict and out["findings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
