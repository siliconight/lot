"""The guide's adjacency as audit findings (Lot 0.111.0, roadmap 230): categories from an
archetype's words, the relation from geometry, the pair rules and the affinity matrix as
`S_ADJACENCY` findings, report-only."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_adjacency as SA  # noqa: E402
import site_audit  # noqa: E402

ROAD = [{"a": [-90.0, -23.0], "b": [90.0, -23.0], "width": 10.0}]


def _b(bid, archetype, x, y, fp=(30.0, 24.0), rot=0):
    return {"id": bid, "archetype": archetype, "at": [x, y], "_footprint": list(fp), "rot": rot}


def test_the_category_comes_from_the_archetypes_words_and_the_specific_row_wins():
    assert SA.category_of("county_hospital") == "civ"
    assert SA.category_of("strip_club") == "ngt"
    assert SA.category_of("country_club") == "rec"           # before the club row
    assert SA.category_of("gas_station") == "trn"
    assert SA.category_of("industrial_warehouse") == "lgt"
    assert SA.category_of("apartment_walkup") == "res"
    assert SA.category_of("deli") == "ret" and SA.category_of("") == "ret"


def test_the_affinity_matrix_is_the_guides_and_symmetric():
    assert SA.affinity("res", "hvy") == -2 and SA.affinity("hvy", "res") == -2
    assert SA.affinity("ret", "trn") == 2 and SA.affinity("ngt", "ret") == 2
    for a in SA.CATEGORIES:
        for b in SA.CATEGORIES:
            assert SA.affinity(a, b) == SA.affinity(b, a), (a, b)


def test_the_relation_is_geometry():
    a, b = _b("b0", "deli", 0.0, 0.0), _b("b1", "office", 31.0, 0.0)      # gap 1 m
    assert SA.relation(a, b, ROAD) == "shared_boundary"
    far = _b("b2", "office", 60.0, 0.0)                                   # gap 30 m, same side
    assert SA.relation(a, far, ROAD) == "same_block"
    over = _b("b3", "office", 0.0, -46.0)                                 # the road at y -23 between
    assert SA.relation(a, over, ROAD) == "across_local_street"
    turned = _b("b4", "office", 0.0, 28.0, fp=(30.0, 24.0), rot=90)      # 30 deep when turned: gap 1 m
    assert SA.relation(a, turned, ROAD) == "shared_boundary"


def test_a_pair_rule_matches_either_way_round_at_its_relations():
    assert [r[0] for r in SA.rules_for("strip_club", "school", "shared_boundary")] == ["P07"]
    assert [r[0] for r in SA.rules_for("school", "strip_club", "across_local_street")] == ["P07"]
    assert SA.rules_for("school", "strip_club", "same_block") == []
    assert [r[0] for r in SA.rules_for("rail_station", "deli", "same_block")] == ["P17"]


def test_a_conflict_is_a_med_finding_and_a_fit_a_quiet_one():
    site = {"buildings": [_b("b0", "county_hospital", 0.0, 0.0), _b("b1", "strip_club", 31.0, 0.0)],
            "roads": ROAD}
    found = SA.findings(site)
    assert [f[0] for f in found] == ["MED"] and "P21" in found[0][2] and "shared_boundary" in found[0][2]
    quiet = {"buildings": [_b("b0", "deli", 0.0, 0.0), _b("b1", "office", 60.0, 0.0)], "roads": ROAD}
    assert SA.findings(quiet) == []


def test_a_preferred_pair_says_why_at_info():
    site = {"buildings": [_b("b0", "rail_station", 0.0, 0.0), _b("b1", "deli", 60.0, 0.0),
                          _b("b2", "office", 120.0, 0.0)], "roads": ROAD}
    found = SA.findings(site)
    assert len(found) == 2 and all(f[0] == "INFO" and "P17 prefer" in f[2] for f in found)


def test_the_matrix_speaks_when_no_rule_does():
    site = {"buildings": [_b("b0", "mansion", 0.0, 0.0), _b("b1", "foundry_heist_vertical", 60.0, 0.0)],
            "roads": ROAD}
    found = SA.findings(site)
    assert found and found[0][0] == "MED" and "affinity -2" in found[0][2]
    weak = {"buildings": [_b("b0", "deli", 0.0, 0.0), _b("b1", "foundry_heist_vertical", 60.0, 0.0)],
            "roads": ROAD}
    assert [f[0] for f in SA.findings(weak)] == ["INFO"]


def test_the_site_audit_carries_the_findings():
    site = {"name": "t", "buildings": [_b("b0", "county_hospital", 0.0, 0.0), _b("b1", "strip_club", 31.0, 0.0)],
            "roads": ROAD, "site_markers": [], "paths": [], "cover": []}
    res = site_audit.audit(site)
    codes = [f[1] for f in res["findings"]]
    assert "S_ADJACENCY" in codes
