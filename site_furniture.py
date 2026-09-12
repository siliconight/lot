"""The kerb line: what stands on a sidewalk between the crossings.

Roadmap 153, the second layer. A street reads as ordered when its furniture
says where cars and people go: a lamp at a spacing, a hydrant and a sign at
the corner, a bin where people wait. This module places them along each
sidewalk band of every road in `site_streets`, between the kerb cuts, as
PROP SLOTS -- the same record the cover planner writes, so the site kit
builds them, the themed site stands the modules where the boxes stood, and
the honesty rule is kept by construction: every piece is taller than the
step limit and carries collision.

Placement is along the band's outer half (away from the road) so the kerb
edge stays clear for a body stepping off at a cut, and nothing is placed
inside a cut's span plus a clearance. Spacings are from practice, cited in
the table, and derived from nothing here -- they are what a Delco sidewalk
carries, not what a lane needs.

Frame: spec/Blender Z-up plan coordinates, like `site_streets`. Pure.
"""
from __future__ import annotations

import math

#: (species, width, depth, height) in the species' own frame, and the rule
#: that places it. Dims are the Zoo genomes' defaults.
#:   streetlight: one every 25 m (IES RP-8 residential spacing is 25-30 m
#:                at 8-9 m mounting; Zoo's lamp is 6 m, so the low end)
#:   fire_hydrant: one at each crossing, 2.5 m past the cut on the far side
#:                 (hydrants stand at corners, clear of the crosswalk)
#:   litter_bin:   one at each crossing, 1.5 m before the cut (where people
#:                 wait to cross)
#:   sign_post:    one at each crossing, at the cut's near edge, facing the
#:                 road (a stop sign for the spur)
SPECIES = {
    "streetlight": (0.7, 0.3, 6.0),
    "fire_hydrant": (0.35, 0.35, 0.75),
    "litter_bin": (0.6, 0.6, 1.0),
    "sign_post": (0.1, 0.1, 2.4),
}
LAMP_SPACING = 25.0
LAMP_START = 5.0
CUT_CLEARANCE = 0.8       # a piece stays this far from a dropped kerb's span
BAND_INSET = 0.45         # centre of a piece, in from the band's outer edge


def _clear_of_cuts(t, half_along, kerb, clearance=CUT_CLEARANCE):
    lo, hi = t - half_along - clearance, t + half_along + clearance
    for t0, t1, is_cut in kerb.spans:
        if is_cut and not (hi <= t0 or lo >= t1):
            return False
    return True


def _piece(name, species, road, kerb, t, offset, yaw_extra=0.0, breaks=""):
    w, d, h = SPECIES[species]
    x, y = road.point(t, offset)
    yaw = (road.angle_deg + yaw_extra) % 360.0
    # plan footprint after the yaw, quantised the way cover is
    sx, sy = (d, w) if int(round(yaw)) % 180 == 90 else (w, d)
    return {"name": name, "species": species, "at": [round(x, 3), round(y, 3)],
            "yaw": round(yaw, 3), "dims": [w, d, h], "size": [sx, h, sy],
            "base": "sidewalk", "road": road.index, "kerb": kerb.side,
            "source": "site_furniture", "breaks": breaks}


def plan_furniture(roads_list, sidewalk_h: float) -> list:
    """Pieces along every sidewalk band, as site-cover-shaped records with a
    ``base`` of ``sidewalk`` (the module stands on the band's top, not the
    plate). Returns the list; the caller extends the spec and the slots."""
    out = []
    n = 0
    for road in roads_list:
        if not road.sidewalk:
            continue
        for kerb in road.kerbs:
            outer = kerb.offset + kerb.sign * (road.sidewalk / 2.0 - BAND_INSET)
            # lamps at a spacing, skipping the cuts
            t = LAMP_START
            while t < road.length - LAMP_START:
                w, d, h = SPECIES["streetlight"]
                if _clear_of_cuts(t, d / 2.0, kerb):
                    out.append(_piece(f"Lamp_{n}", "streetlight", road, kerb, t, outer))
                    n += 1
                t += LAMP_SPACING
            # per cut: a hydrant past it, a bin before it, a sign at its edge
            for c in sorted(kerb.cuts, key=lambda c: c.t):
                half = c.span / 2.0 + CUT_CLEARANCE
                # offsets are from the dropped kerb's EDGE, which already
                # carries CUT_CLEARANCE; `_clear_of_cuts` adds it again, so a
                # piece nearer than that to the edge is refused by design
                for species, dt, yaw_extra in (("fire_hydrant", half + 2.5, 0.0),
                                               ("litter_bin", -(half + 1.5), 0.0),
                                               ("sign_post", half + 1.0, 90.0)):
                    w, d, h = SPECIES[species]
                    tt = c.t + dt
                    if 0.5 < tt < road.length - 0.5 and _clear_of_cuts(tt, d / 2.0, kerb):
                        out.append(_piece(f"{species}_{n}", species, road, kerb, tt,
                                          outer, yaw_extra, breaks=f"crossing@{c.t:.1f}"))
                        n += 1
    return out
