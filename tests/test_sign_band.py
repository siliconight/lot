"""A shop sign hangs where its building has room for one (Lot 0.141.0).

The walker, 2026-10-31: "store signage still looks...wrong ... placement, size of font". The band hung at 3.6 m on
every building and stopped at 9 m: on the slice's self-storage (wall to 3.1 m, roof edge 3.4 m) it stood mostly over
the roof, and on a 36 m front it was a plaque. FAILS ON 0.140.0: there is no `facade_frame` or `sign_band`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot  # noqa: E402


def _slot(role, facing, story, z_top, h=3.0):
    return {"role": role, "facing": facing, "story": story,
            "transform": {"translation": [0.0, 0.0, z_top - h / 2.0]}, "fit": {"dims": [2.0, 0.3, h]}}


def _op(story, z, h, side="S"):
    return {"wall": "ext_%d_%s" % (story, side), "story": story, "z": z, "height": h}


def test_a_two_storey_shop_signs_its_fascia_between_the_shop_front_and_the_windows_above():
    """The card shop's own numbers: heads 2.2 m, the upper sills 4.4 m, its storey-0 wall to 3.15 m."""
    gp = {"openings": [_op(0, 1.1, 2.2), _op(0, 1.0, 2.0), _op(1, 5.1, 1.4)]}
    slots = {"slots": [_slot("wall", "S", 0, 3.15), _slot("wall", "S", 1, 6.55), _slot("roof", "up", 2, 6.8, 0.3)]}
    frame = lot.facade_frame(gp, slots)
    assert frame["S"]["head"] == 2.2 and abs(frame["S"]["sill1"] - 4.4) < 1e-9 and frame["S"]["top0"] == 3.15
    b = {"id": "b0", "rot": 0, "_facade": frame}
    z, (w, h), mount = lot.sign_band(b, 270.0, 20.0)
    assert mount == "fascia"
    assert 2.2 + lot.SIGN_GAP <= z - h / 2.0 and z + h / 2.0 <= 4.4 - lot.SIGN_GAP
    assert abs(w / h - lot.SIGN_ASPECT) < 1e-9 and w <= 20.0 * lot.SIGN_SPAN_MAX


def test_a_low_box_with_no_fascia_signs_its_roof_edge():
    """The self-storage: a garage head at 3.0 m, the wall to 3.1 m, the roof to 3.4 m -- no room under the eave, so
    the sign stands on the roof edge, its foot on the face's top; a 36 m front gets a sign bigger than 9 m."""
    gp = {"openings": [_op(0, 1.1, 2.2), _op(0, 1.5, 3.0)]}
    slots = {"slots": [_slot("wall", "S", 0, 3.1), _slot("doorway", "S", 0, 3.1), _slot("roof", "up", 1, 3.4, 0.3)]}
    b = {"id": "b3", "rot": 0, "_facade": lot.facade_frame(gp, slots)}
    z, (w, h), mount = lot.sign_band(b, 270.0, 36.0)
    assert mount == "roof"
    assert abs((z - h / 2.0) - 3.4) < 1e-9
    assert w > lot.SIGN_MAX_W and w <= lot.SIGN_MAX_W_FRAMED


def test_a_turned_building_reads_its_own_side_and_no_record_keeps_the_old_band():
    gp = {"openings": [_op(0, 1.1, 2.2, side="N")]}
    slots = {"slots": [_slot("wall", "N", 0, 3.9), _slot("roof", "up", 1, 4.2, 0.3)]}
    b = {"id": "b0", "rot": 180, "_facade": lot.facade_frame(gp, slots)}
    # turned half round, its local north faces plan south
    assert lot.sign_band(b, 270.0, 20.0)[2] == "fascia"
    assert lot.sign_band({"id": "b1", "rot": 0}, 270.0, 20.0) == (lot.SIGN_Z, lot.sign_size(20.0), "legacy")
