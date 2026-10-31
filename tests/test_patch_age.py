"""A utility cut has an age (Lot 0.140.0).

Every patch wore one tint, 0.42 of the road's pack, so every cut on the slice's 1999 avenue read as laid last week:
in its sodium pools, a near-black bar across the lane, read as a painted shadow. Each patch now draws a seeded age and
wears `PATCH_TINT` fresh to `OLDEST_TINT` old, carried in its vertex colour on the one material.
FAILS ON 0.139.0: a patch record has no age and the meshes carry no colour.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

import lot            # noqa: E402
import site_patches   # noqa: E402
from test_site_patches import STREET, _bld, _plan   # noqa: E402


def _patches():
    blds = [_bld("b%d" % i, -70.0 + 20.0 * i, 14.0, 12.0, 10.0) for i in range(8)]
    return _plan(STREET, blds)[3]


def test_every_patch_has_a_seeded_age_and_the_ages_spread():
    a, b = _patches(), _patches()
    assert a == b and len(a) >= 8
    ages = [p["age"] for p in a]
    assert all(0.0 <= x < 1.0 for x in ages)
    assert min(ages) < 0.35 and max(ages) > 0.65            # some fresh, some old, on one street


def test_the_age_runs_from_the_fresh_tint_to_the_oldest():
    assert site_patches.tint_of(0.0) == site_patches.PATCH_TINT
    assert site_patches.tint_of(1.0) == site_patches.OLDEST_TINT
    mid = site_patches.tint_of(0.5)
    assert all(f < m < o for f, m, o in zip(site_patches.PATCH_TINT, mid, site_patches.OLDEST_TINT))


def test_the_age_rides_in_the_vertex_colour_on_one_material():
    """Colour-only variation is never a new material: one material, one mesh a cell, as before."""
    patches = _patches()
    skin = {"id": "road_pack", "albedo": "a.png", "meters_per_tile": 4.0}
    body, sub, files = site_patches.meshes(patches, 0.1, skin, lot.paint_offset, lot._mat_sub)
    assert "\n".join(sub).count("[sub_resource") == 1
    assert len(files) == "\n".join(body).count("MeshInstance3D")
    want = {}
    for p in patches:
        r = round(site_patches.tint_of(p["age"])[0] / site_patches.OLDEST_TINT[0], 4)
        for c in p["corners"]:
            want[(round(c[0], 6), round(-c[1], 6))] = r
    seen = 0
    for text in files.values():
        for ln in text.splitlines():
            if ln.startswith("v "):
                f = ln.split()
                assert len(f) == 7, ln
                assert abs(float(f[4]) - want[(round(float(f[1]), 6), round(float(f[3]), 6))]) < 1e-4
                seen += 1
    assert seen == 4 * len(patches)
