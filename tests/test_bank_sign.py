"""A bank's time-and-temperature sign at its frontage (Zoo 1.138.0's `price_pylon` form `bank`), placed by the gas
pylon's planner and dressed in the door sign's name and colours. FAILS ON 0.131.0, which stands no bank sign.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import lot              # noqa: E402
import site_furniture   # noqa: E402
import site_streets     # noqa: E402

SPECS = os.path.join(HERE, "specs")
ZOO = os.environ.get("LOT_ZOO_ROOT") or os.path.join(os.path.dirname(HERE), "zoo")


def _probe():
    return json.load(open(os.path.join(SPECS, "coldrun_kerb_probe.json")))


def _zoo(module):
    if not os.path.isfile(os.path.join(ZOO, "zoo_keeper", "core", module + ".py")):
        pytest.skip("zoo %s not found at %s (set LOT_ZOO_ROOT; Zoo >= 1.138.0)" % (module, ZOO))
    if ZOO not in sys.path:
        sys.path.insert(0, ZOO)
    import importlib
    return importlib.import_module("zoo_keeper.core." + module)


def test_a_bank_is_read_from_the_words_its_sign_is():
    for b in ("bank_branch_a02", "bank_job", "credit_union_a01", "lf_bank_block_001_7 bank_branch"):
        assert site_furniture.is_bank_business(b), b
    for b in ("deli_a01", "pawn_shop_a01", "bankrupt_outlet", "", None):
        assert not site_furniture.is_bank_business(b), b


def test_the_variant_is_the_one_zoos_door_sign_picks():
    TF = _zoo("teller_line_forms")
    SN = _zoo("storefront_names")
    for b in ["bank_branch_a0%d" % i for i in range(1, 8)] + ["credit_union_a01", "bank_job", "bank"]:
        v = site_furniture.bank_sign_variant(b)
        assert v == TF.variant_for(b), b
        assert TF.bank_said(v)["text"] == SN.sign_for(b)["text"], b


def test_the_bank_signs_dims_are_in_zoos_range_and_its_form_is_listed():
    p = os.path.join(ZOO, "zoo_keeper", "genome", "species", "price_pylon.json")
    if not os.path.isfile(p):
        pytest.skip("no zoo checkout at %s" % ZOO)
    g = json.load(open(p, encoding="utf-8"))
    if "bank" not in g["params"]["form"]:
        pytest.skip("Zoo before 1.138.0 has no bank pylon")
    for k, v in zip(("width", "depth", "height"), site_furniture.BANK_PYLON_DIMS):
        assert g["dimensions"][k]["min"] <= v <= g["dimensions"][k]["max"], k
    assert g["module_variants"] == 16


def test_a_bank_sign_is_planned_at_its_dims_dressed_behind_the_band():
    roads = site_streets.roads(_probe())
    (road,) = roads
    got = site_furniture.plan_pylons(roads, [("bank", (76.0, 32.0))], dims=site_furniture.BANK_PYLON_DIMS,
                                     dress={"bank": {"form": "bank", "variant": 11}}, label="frontage")
    (p,) = got
    assert p["species"] == "price_pylon" and p["form"] == "bank" and p["variant"] == 11
    assert tuple(p["dims"]) == site_furniture.BANK_PYLON_DIMS and p["breaks"] == "frontage bank"
    x, y = p["at"]
    _sx, _h, sy = p["size"]
    assert y - sy / 2.0 >= 8.0 + site_furniture.PYLON_SETBACK - 1e-9, p
    # and a gas pylon is what it was
    (g,) = site_furniture.plan_pylons(roads, [("gas", (76.0, 32.0))])
    assert tuple(g["dims"]) == site_furniture.SPECIES["price_pylon"] and "form" not in g and "variant" not in g


def test_variant_zero_is_not_written():
    roads = site_streets.roads(_probe())
    (p,) = site_furniture.plan_pylons(roads, [("bank", (76.0, 32.0))], dims=site_furniture.BANK_PYLON_DIMS,
                                      dress={"bank": {"form": "bank", "variant": 0}})
    assert p["form"] == "bank" and "variant" not in p


def test_assemble_stands_a_bank_sign_for_a_building_whose_door_sign_is_a_banks(tmp_path):
    spec = _probe()
    for b in spec["buildings"]:
        for k in ("spec", "glb", "gameplay"):
            if k in b:
                b[k] = os.path.join(SPECS, b[k])
    bank = next(b for b in spec["buildings"] if b["id"] == "gas")
    lights = tmp_path / "bank.lights.json"
    # the probe's building at (76, 44) turned 180: its door sign 12 m on its local +y side lands at (76, 32)
    lights.write_text(json.dumps({"anchors": [{"id": "ext_0_S_sign", "type": "sign", "pos": [0.0, 12.0, 2.55],
                                               "rot_y": 270.0, "size": [2.6, 0.6],
                                               "business": "bank_branch_a02"}]}), encoding="utf-8")
    bank["lights"] = str(lights)
    assert lot.forecourts(spec, str(tmp_path)) == []
    assert lot.bank_fronts(spec, str(tmp_path)) == [("gas", (76.0, 32.0), "bank_branch_a02")]
    sp = tmp_path / "bank_probe.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    lot.assemble(str(sp), str(tmp_path / "out"))
    doc = json.loads((tmp_path / "out" / (spec["name"] + ".slots.json")).read_text(encoding="utf-8"))
    signs = [s for s in doc["slots"] if s.get("species") == "price_pylon"]
    assert len(signs) == 1, [s.get("species") for s in doc["slots"]]
    s = signs[0]
    assert s["form"] == "bank" and s["variant"] == site_furniture.bank_sign_variant("bank_branch_a02") == 11
    assert s["fit"]["dims"] == list(site_furniture.BANK_PYLON_DIMS)
    assert abs(s["transform"]["translation"][2] - site_furniture.BANK_PYLON_DIMS[2] / 2.0) < 1e-6
