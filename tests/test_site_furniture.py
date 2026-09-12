"""The kerb line (roadmap 153): lamps at a spacing, a hydrant, a bin and a
sign at every crossing, on the sidewalk bands, as prop slots the site kit
builds. Every piece is taller than the step limit and carries collision,
so the honesty rule holds by species rather than by a check.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "specs")


def _probe():
    return json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))


def test_every_piece_stands_on_a_band_clear_of_the_cuts():
    roads = site_streets.roads(_probe())
    pieces = site_furniture.plan_furniture(roads, lot.SIDEWALK_H)
    assert pieces
    (road,) = roads
    for p in pieces:
        assert p["base"] == "sidewalk" and p["source"] == "site_furniture"
        x, y = p["at"]
        # the probe road runs along X at y = 0; bands are 5..8 and -8..-5
        assert 5.0 <= abs(y) <= 8.0, p
        assert -110.0 <= x <= 110.0
        t = x + 110.0
        kerb = road.kerb(p["kerb"])
        w, d, h = p["dims"]
        assert h > lot.STEP_MAX          # never a thing a body walks through
        for t0, t1, is_cut in kerb.spans:
            if is_cut:
                assert t + d / 2 <= t0 + 1e-6 or t - d / 2 >= t1 - 1e-6, (p, (t0, t1))


def test_lamps_at_the_spacing_and_the_corner_set_at_every_cut():
    roads = site_streets.roads(_probe())
    pieces = site_furniture.plan_furniture(roads, lot.SIDEWALK_H)
    by = {}
    for p in pieces:
        by.setdefault(p["species"], []).append(p)
    lamps = sorted(p["at"][0] for p in by["streetlight"] if p["kerb"] == "L")
    gaps = [b - a for a, b in zip(lamps, lamps[1:])]
    assert gaps and all(abs(g - site_furniture.LAMP_SPACING) < 1e-6
                        or g > site_furniture.LAMP_SPACING for g in gaps)
    (road,) = roads
    cuts = sum(len(k.cuts) for k in road.kerbs)
    for species in ("fire_hydrant", "litter_bin", "sign_post"):
        assert 1 <= len(by[species]) <= cuts, species
    assert all(p["yaw"] == 90.0 for p in by["sign_post"])     # faces the road


def test_assemble_writes_the_furniture_as_slots_standing_on_the_kerb(tmp_path):
    lot.assemble(os.path.join(SPECS, "coldrun_kerb_probe.json"), str(tmp_path))
    doc = json.loads((tmp_path / "coldrun_kerb_probe.slots.json").read_text(encoding="utf-8"))
    lamps = [s for s in doc["slots"] if s["species"] == "streetlight"]
    assert lamps
    for s in lamps:
        assert abs(s["transform"]["translation"][2] - (lot.SIDEWALK_H + 3.0)) < 1e-6
        assert s["fit"]["collision"] == "convex"
    g = json.loads((tmp_path / "coldrun_kerb_probe.site.gameplay.json").read_text(encoding="utf-8"))
    assert g["furniture_plan"]["placed"]
    # and the box the scene draws for a lamp stands on the band's top
    txt = (tmp_path / "coldrun_kerb_probe.tscn").read_text(encoding="utf-8")
    i = txt.index('name="cover_%d"' % (len(g["cover_plan"]["placed"])))
    assert f", {lot.SIDEWALK_H + 3.0:g}, " in txt[i:].split("\n")[1]
