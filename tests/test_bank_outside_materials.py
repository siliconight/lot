"""The bank's outside pieces ask Zoo for their genomes' own material (0.134.0), so the stem Zoo builds is the stem Lot's
resolver asks for. FAILS ON 0.133.0: none of the three has a row, and each asked for `metal_painted`.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import lot  # noqa: E402

ZOO = os.environ.get("LOT_ZOO_ROOT") or os.path.join(os.path.dirname(HERE), "zoo")
SPECIES = ("drive_up_canopy", "drive_up_tube", "night_drop", "price_pylon")


def test_every_bank_outside_piece_has_a_row():
    for sp in SPECIES:
        assert sp in lot.COVER_MATERIALS, sp


@pytest.mark.parametrize("species", SPECIES)
def test_the_row_is_the_genomes_default(species):
    p = os.path.join(ZOO, "zoo_keeper", "genome", "species", species + ".json")
    if not os.path.isfile(p):
        pytest.skip("no Zoo >= 1.138.0 at %s (set LOT_ZOO_ROOT)" % ZOO)
    g = json.load(open(p, encoding="utf-8"))
    assert lot.COVER_MATERIALS[species] == g["materials"]["default"], species
