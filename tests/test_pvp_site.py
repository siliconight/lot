"""Tests for the site-level pvp_heist profile (site_tactical pvp gates +
post-merge gates). Same offline, self-asserting style as test_lot.py."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import site_tactical as st


def _pvp_site():
    """A minimal well-formed pvp_heist site: attacker staging building,
    defended objective, separate extraction, two approach routes, and a
    site-level attacker staging marker."""
    return {
        "name": "pvp_t",
        "mode": "pvp_heist",
        "spawn": "stage",
        "objective": "bank",
        "extraction": "garage",
        "buildings": [
            {"id": "stage", "at": [0, 0]},
            {"id": "bank", "at": [60, 0]},
            {"id": "alley", "at": [30, 30]},
            {"id": "garage", "at": [90, 30]},
        ],
        "paths": [
            {"from": "stage", "to": "bank"},
            {"from": "stage", "to": "alley"},
            {"from": "alley", "to": "bank"},
            {"from": "bank", "to": "garage"},
        ],
        "site_markers": [
            {"type": "attacker_spawn", "at": [-10, 0]},
            {"type": "extraction", "at": [95, 35]},
        ],
    }


def _pvp_merged(defender_building="bank", defender_xy=(62.0, 2.0)):
    """A minimal merged-gameplay stand-in with a defender spawn."""
    return {
        "markers": [
            {"type": "defender_spawn", "name": f"{defender_building}/defender_spawn",
             "building": defender_building,
             "x": defender_xy[0], "y": defender_xy[1], "z": 0.0},
            {"type": "objective", "name": "bank/objective",
             "building": "bank", "x": 60.0, "y": 0.0, "z": 0.0},
        ],
    }


def test_pvp_gate_passes():
    st.gate(_pvp_site())
    print("  pvp_heist site gate (valid): OK")


def test_pvp_gate_requires_designations():
    for field in ("spawn", "objective", "extraction"):
        bad = _pvp_site()
        del bad[field]
        try:
            st.gate(bad)
            assert False, f"missing '{field}' should fail"
        except st.SiteTacticalError as ex:
            assert field in str(ex)
    print("  pvp_heist site gate (missing designations fail): OK")


def test_pvp_gate_requires_two_approaches():
    bad = _pvp_site()
    bad["paths"] = [{"from": "stage", "to": "bank"},
                    {"from": "bank", "to": "garage"}]
    try:
        st.gate(bad)
        assert False, "single-approach pvp site should fail"
    except st.SiteTacticalError as ex:
        assert "approach" in str(ex)
    print("  pvp_heist site gate (>=2 approaches): OK")


def test_pvp_gate_requires_extraction_route():
    bad = _pvp_site()
    bad["paths"] = [p for p in bad["paths"]
                    if not (p["from"] == "bank" and p["to"] == "garage")]
    try:
        st.gate(bad)
        assert False, "objective with no extraction route should fail"
    except st.SiteTacticalError as ex:
        assert "extraction" in str(ex)
    print("  pvp_heist site gate (extraction route): OK")


def test_pvp_gate_requires_staging_marker():
    bad = _pvp_site()
    bad["site_markers"] = [m for m in bad["site_markers"]
                           if m["type"] != "attacker_spawn"]
    try:
        st.gate(bad)
        assert False, "no attacker staging marker should fail"
    except st.SiteTacticalError as ex:
        assert "staging" in str(ex)
    print("  pvp_heist site gate (attacker staging marker): OK")


def test_pvp_merged_gate_passes():
    r = st.gate_merged(_pvp_site(), _pvp_merged())
    assert r is not None
    assert r["defender_spawns"] == 1
    assert r["defender_buildings"] == ["bank"]
    assert r["protected_hold"] is True
    assert r["min_spawn_separation"] and r["min_spawn_separation"] >= 25.0
    print("  pvp_heist merged gate (valid): OK")


def test_pvp_merged_gate_noop_other_modes():
    site = _pvp_site()
    site["mode"] = "heist"
    assert st.gate_merged(site, _pvp_merged()) is None
    print("  pvp_heist merged gate (no-op off-profile): OK")


def test_pvp_merged_gate_requires_defenders():
    merged = _pvp_merged()
    merged["markers"] = [m for m in merged["markers"]
                         if m["type"] != "defender_spawn"]
    try:
        st.gate_merged(_pvp_site(), merged)
        assert False, "no defender spawns should fail"
    except st.SiteTacticalError as ex:
        assert "defender" in str(ex)
    print("  pvp_heist merged gate (defenders required): OK")


def test_pvp_merged_gate_spawn_separation():
    # defender right on top of the attacker staging point (-10, 0)
    merged = _pvp_merged(defender_xy=(-8.0, 0.0))
    try:
        st.gate_merged(_pvp_site(), merged)
        assert False, "2 m opposing-spawn separation should fail"
    except st.SiteTacticalError as ex:
        assert "apart" in str(ex)
    # per-site override permits it
    site = _pvp_site()
    site["pvp"] = {"min_spawn_separation": 1.0}
    r = st.gate_merged(site, merged)
    assert r["min_spawn_separation"] < 25.0
    print("  pvp_heist merged gate (opposing-spawn separation): OK")


def test_pvp_merged_gate_protected_hold():
    # defenders in a building whose only route to the objective crosses the
    # attacker staging building
    site = _pvp_site()
    site["buildings"].append({"id": "annex", "at": [-40, 0]})
    site["paths"].append({"from": "annex", "to": "stage"})
    merged = _pvp_merged(defender_building="annex", defender_xy=(-40.0, 60.0))
    try:
        st.gate_merged(site, merged)
        assert False, "unprotected defender rotation should fail"
    except st.SiteTacticalError as ex:
        assert "protected" in str(ex) or "rotation" in str(ex)
    print("  pvp_heist merged gate (protected hold): OK")


def test_pvp_analyze_intel():
    r = st.analyze(_pvp_site())
    assert r["intel"]["attacker_site_markers"] == 1
    assert r["intel"]["defender_site_markers"] == 0
    assert r["intel"]["objective_approaches"] >= 2
    print("  pvp_heist analyze intel: OK")


def test_unknown_mode_message_lists_pvp():
    try:
        st.gate({"name": "t", "mode": "zombies", "buildings": [], "paths": []})
        assert False
    except st.SiteTacticalError as ex:
        assert "pvp_heist" in str(ex)
    print("  unknown-mode message lists pvp_heist: OK")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"running {len(fns)} pvp site tests")
    for fn in fns:
        fn()
    print("all pvp site tests passed")
