"""Dressing has to be told where it may go, by someone who knows the site.

`level_factory/schemas/surface_dressing.v1.json` is explicit that zones are
"semantic regions from Deli Counter / Lot -- not invented here", that
`traversed` is "taken from Lot's walkable surfaces, not asserted by the
dressing planner", and that an exclusion nobody declared is a preference. So
Lot declares them, and these tests hold it to the part that is checkable: every
zone traces to a spec key, the zones tile the ground without double-counting
it, and the numbers come from modules that already derived them.

The fixture is the real `specs/coldrun_pawn_job.json`: a 150 x 110 plate, four
buildings, three 5 m paths, one courtyard, three cover pieces, and a spawn,
objective and extraction naming three of the buildings.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import site_cover                # noqa: E402
import site_steps                # noqa: E402
import site_surfaces as SS       # noqa: E402


def spec():
    return {
        "name": "fixture",
        "ground": {"size_x": 150, "size_y": 110},
        "spawn": "garage", "objective": "pawn", "extraction": "gas",
        "buildings": [
            {"id": "garage", "at": [-48, -28], "rot": 0},
            {"id": "deli", "at": [-6, 18], "rot": 90},
            {"id": "pawn", "at": [32, -22], "rot": 0},
            {"id": "gas", "at": [58, 26], "rot": 180},
        ],
        "paths": [
            {"from": "garage", "to": "deli", "width": 5},
            {"from": "deli", "to": "pawn", "width": 5},
            {"from": "pawn", "to": "gas", "width": 5},
        ],
        "courtyards": [{"at": [12, -2], "size_x": 22, "size_y": 16}],
        "cover": [{"at": [4, -6]}, {"at": [20, 4]}, {"at": [40, 2]}],
        "perimeter": {"height": 3},
    }


def footprinted():
    s = spec()
    for b in s["buildings"]:
        b["_footprint"] = [20.0, 14.0]
    return s


def _families(zones):
    return {z["surface_zone_id"]: SS._family_of(z) for z in zones}


# --- the capsule the honesty rule is for -----------------------------------

def test_capsule_carries_the_derived_step_limit_not_a_literal():
    cap = SS.capsule_block()
    assert cap["unassisted_step_max_m"] == round(
        site_steps.unassisted_step_max_m(0.4, 45.0), 5)
    assert abs(cap["unassisted_step_max_m"] - 0.117) < 0.001
    assert "site_steps" in cap["source"]


def test_a_different_capsule_moves_the_limit():
    """Falsification: if the number were a literal, this would not move."""
    small = SS.capsule_block(radius_m=0.25)
    assert small["unassisted_step_max_m"] < \
        SS.capsule_block()["unassisted_step_max_m"]


def test_zone_ceiling_is_the_step_limit():
    """A zone's box may not offer height the honesty rule forbids there."""
    cap = SS.capsule_block()
    zones, _ = SS.zones(spec(), capsule=cap)
    for z in zones:
        assert z["aabb"][5] == cap["unassisted_step_max_m"]


# --- every zone traces to a spec key ---------------------------------------

def test_each_spec_key_produces_its_zone():
    zones, _ = SS.zones(footprinted())
    fam = set(_families(zones).values())
    assert fam == {"path", "wall_base", "courtyard", "perimeter", "open"}


def test_dropping_a_spec_key_drops_its_zones():
    """Falsification. If zones survived a key's removal they were invented."""
    s = footprinted()
    s.pop("courtyards")
    s.pop("paths")
    fam = set(_families(SS.zones(s)[0]).values())
    assert "courtyard" not in fam and "path" not in fam
    assert "open" in fam


def test_zones_are_ordered_most_restrictive_first():
    zones, _ = SS.zones(footprinted())
    ranks = [SS.PRECEDENCE.index(SS._family_of(z)) for z in zones]
    assert ranks == sorted(ranks)


# --- the corridor bug this module was rewritten for ------------------------

def test_a_diagonal_path_does_not_swallow_the_site():
    """The first version emitted one AABB per path. Three diagonal 5 m paths
    produced boxes 47 x 51 m, every square metre of the site came back
    `gameplay_path`, and the density variation the guide asks for collapsed
    into one uniform sparse scatter. This is that bug, as a test."""
    zones, _ = SS.zones(spec())
    ground = 150.0 * 110.0
    for z in zones:
        if SS._family_of(z) != "path":
            continue
        a = z["aabb"]
        area = (a[3] - a[0]) * (a[4] - a[1])
        assert area <= ground * 0.01, \
            f"{z['surface_zone_id']} covers {area:.0f} m2 of a {ground:.0f} m2 site"


def test_corridor_boxes_cover_the_whole_centreline():
    """Stepped at half a width, the chain cannot leave a gap."""
    boxes = SS.corridor_boxes((0.0, 0.0), (30.0, 40.0), 5.0)
    for i in range(101):
        t = i / 100.0
        x, y = 30.0 * t, 40.0 * t
        assert any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes), \
            f"centreline point ({x:.1f}, {y:.1f}) is in no box"


def test_a_point_well_off_the_route_is_not_on_the_path():
    zones, _ = SS.zones(spec())
    z = SS.zone_for((0.0, 0.0), zones)
    assert SS._family_of(z) == "open"


def test_a_point_on_the_route_is_on_the_path():
    zones, _ = SS.zones(spec())
    z = SS.zone_for((12.0, -2.0), zones)
    assert SS._family_of(z) == "path"


# --- the perimeter is an annulus, not the whole plate ----------------------

def test_perimeter_does_not_contain_the_play_area():
    """Emitting the plate as the perimeter would make very_high density the
    reading for the entire site, which is not what an edge means."""
    zones, _ = SS.zones(footprinted())
    strips = [z for z in zones if SS._family_of(z) == "perimeter"]
    assert strips
    for z in strips:
        a = z["aabb"]
        assert not (a[0] <= 0.0 <= a[3] and a[1] <= 0.0 <= a[4]), \
            "a perimeter strip contains the site origin"


def test_perimeter_strips_do_not_overlap_each_other():
    """Overlapping strips would count one square metre against two budgets,
    which means counting it against neither."""
    zones, _ = SS.zones(footprinted())
    strips = [z["aabb"] for z in zones if SS._family_of(z) == "perimeter"]
    for i, a in enumerate(strips):
        for b in strips[i + 1:]:
            overlap = (min(a[3], b[3]) - max(a[0], b[0])) * \
                      (min(a[4], b[4]) - max(a[1], b[1]))
            assert (min(a[3], b[3]) <= max(a[0], b[0])
                    or min(a[4], b[4]) <= max(a[1], b[1])), \
                f"perimeter strips overlap by {overlap:.1f} m2"


def test_open_ground_and_perimeter_are_disjoint():
    zones, _ = SS.zones(footprinted())
    inner = [z["aabb"] for z in zones if SS._family_of(z) == "open"][0]
    for z in zones:
        if SS._family_of(z) != "perimeter":
            continue
        a = z["aabb"]
        assert (min(a[3], inner[3]) <= max(a[0], inner[0])
                or min(a[4], inner[4]) <= max(a[1], inner[1]))


# --- honesty about what could not be read ----------------------------------

def test_unreadable_footprints_are_reported_not_skipped():
    """A raw spec carries no footprint. Emitting no wall-base zones and
    saying nothing would look exactly like a site with no walls."""
    zones, findings = SS.zones(spec())          # no _footprint annotations
    assert "wall_base" not in set(_families(zones).values())
    codes = [f["code"] for f in findings]
    assert SS.CODE_FOOTPRINT_UNKNOWN in codes
    msg = [f["message"] for f in findings
           if f["code"] == SS.CODE_FOOTPRINT_UNKNOWN][0]
    for bid in ("garage", "deli", "pawn", "gas"):
        assert bid in msg


def test_annotated_footprints_produce_wall_bases_and_no_finding():
    zones, findings = SS.zones(footprinted())
    walls = [z for z in zones if SS._family_of(z) == "wall_base"]
    assert len(walls) == 4
    assert SS.CODE_FOOTPRINT_UNKNOWN not in [f["code"] for f in findings]


def test_wall_base_band_comes_from_the_nav_bake():
    assert SS.wall_base_band_m({"agent_radius_m": 0.6}) == 0.6
    assert SS.wall_base_band_m() == 0.4          # site_cover's own fallback


def test_a_site_with_no_ground_says_so_instead_of_returning_nothing():
    s = spec()
    s.pop("ground")
    zones, findings = SS.zones(s)
    assert zones == []
    assert SS.CODE_NO_GROUND in [f["code"] for f in findings]


def test_an_unresolvable_marker_is_reported():
    s = spec()
    s["objective"] = "nowhere"
    _, findings = SS.exclusions(s)
    assert SS.CODE_MARKER_UNRESOLVED in [f["code"] for f in findings]


# --- exclusions -------------------------------------------------------------

def test_every_exclusion_names_what_declared_it():
    xs, _ = SS.exclusions(spec())
    assert xs
    for e in xs:
        assert e["declared_by"] == "lot"
        assert e["tag"] in {"path", "spawn", "objective", "interactable",
                            "door", "cover_edge", "readability"}


def test_spawn_objective_and_extraction_all_become_exclusions():
    tags = sorted(e["tag"] for e in SS.exclusions(spec())[0])
    assert tags.count("cover_edge") == 3
    assert tags.count("spawn") == 1
    assert tags.count("objective") == 2       # objective + extraction


def test_exclusion_radius_is_site_covers_number():
    xs, _ = SS.exclusions(spec())
    assert {e["radius_m"] for e in xs} == {site_cover.MARKER_CLEARANCE}


def test_excluded_reports_the_tags_it_tested():
    xs, _ = SS.exclusions(spec())
    assert SS.excluded((-48.0, -28.0), xs) == ["spawn"]
    assert SS.excluded((4.0, -6.0), xs) == ["cover_edge"]
    assert SS.excluded((0.0, 50.0), xs) == []


def test_a_placements_own_radius_widens_the_exclusion():
    """Falsification: if the radius argument were ignored, a wide object
    could straddle a spawn marker and clear the test."""
    xs, _ = SS.exclusions(spec())
    just_outside = (-48.0 + site_cover.MARKER_CLEARANCE + 0.5, -28.0)
    assert SS.excluded(just_outside, xs) == []
    assert SS.excluded(just_outside, xs, radius_m=1.0) == ["spawn"]


# --- the shape the planner receives ----------------------------------------

def test_surfaces_returns_manifest_blocks_and_declares_its_space():
    out = SS.surfaces(footprinted())
    assert out["space"] == "spec/Blender Z-up raw coords"
    assert set(out) == {"space", "capsule", "bands", "zones", "exclusions",
                        "findings"}
    assert set(out["bands"]) == {"micro", "low", "medium", "tall"}
    assert "orders" not in out          # the planner's job, one stage later


def test_every_zone_validates_against_the_schema_required_keys():
    required = {"surface_zone_id", "declared_by", "kind", "exposure_class"}
    for z in SS.surfaces(footprinted())["zones"]:
        assert required <= set(z)
        assert z["kind"] in {"floor", "ground", "roof", "ledge", "seam",
                             "wall_base", "negative_space"}
        assert z["exposure_class"] in SS.VISIBILITY
        assert z["density"] in {"none", "low", "medium", "high", "very_high"}
        assert len(z["aabb"]) == 6


def test_visibility_budget_matches_the_exposure_class():
    for z in SS.surfaces(footprinted())["zones"]:
        assert z["surface_visibility"] == SS.VISIBILITY[z["exposure_class"]]


def test_zone_ids_are_unique():
    ids = [z["surface_zone_id"] for z in SS.surfaces(footprinted())["zones"]]
    assert len(ids) == len(set(ids))


def test_paths_are_the_strictest_and_edges_the_loosest():
    v = SS.VISIBILITY
    assert v["gameplay_path"] > v["play_space"] > v["environmental_edge"]


def test_path_segments_are_in_plan_space_not_godot_space():
    """`site_steps.routes` returns the same segments with y negated because
    its caller works in Godot space. This manifest declares spec space, and
    mixing the two is a bug this repo has already paid for."""
    plan = SS._path_segments(spec())
    godot = site_steps.routes(spec())
    assert plan[0][1] == (-48.0, -28.0)
    assert godot[0][0] == (-48.0, 28.0)


# --- the CLI, because an adapter invokes tools as commands -----------------

def test_cli_writes_a_surfaces_file(tmp_path):
    import json
    spec_path = tmp_path / "site.json"
    spec_path.write_text(json.dumps(footprinted()), encoding="utf-8")
    out = tmp_path / "surfaces.json"
    rc = SS.main([str(spec_path), "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["space"] == "spec/Blender Z-up raw coords"
    assert data["zones"] and data["exclusions"]
    assert data["capsule"]["unassisted_step_max_m"] > 0


def test_cli_strict_fails_on_unreadable_footprints(tmp_path):
    """Default is a warn -- a raw spec legitimately has no footprints. In a
    pipeline it means the wall seams silently went undressed, so --strict
    makes it an exit code someone has to look at."""
    import json
    spec_path = tmp_path / "site.json"
    spec_path.write_text(json.dumps(spec()), encoding="utf-8")   # no footprints
    out = tmp_path / "s.json"
    assert SS.main([str(spec_path), "--out", str(out)]) == 0
    assert SS.main([str(spec_path), "--out", str(out), "--strict"]) == 1


def test_cli_capsule_is_overridable(tmp_path):
    import json
    spec_path = tmp_path / "site.json"
    spec_path.write_text(json.dumps(footprinted()), encoding="utf-8")
    out = tmp_path / "s.json"
    SS.main([str(spec_path), "--out", str(out), "--radius-m", "0.25"])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["capsule"]["radius_m"] == 0.25
    assert data["capsule"]["unassisted_step_max_m"] < 0.117


# --- footprints, without which no wall base is ever dressed -----------------

def _gameplay_dir(tmp_path, footprints=None):
    """A spec plus the gameplay.json files `merge_gameplay` reads."""
    import json
    fp = footprints or {"garage": [36.0, 28.0], "deli": [38.0, 28.0],
                        "pawn": [16.0, 14.0], "gas": [32.0, 22.0]}
    s = spec()
    for b in s["buildings"]:
        if b["id"] in fp:
            b["gameplay"] = f"{b['id']}.gameplay.json"
            b["glb"] = f"{b['id']}.glb"
            (tmp_path / b["gameplay"]).write_text(
                json.dumps({"footprint": fp[b["id"]]}), encoding="utf-8")
    return s


def test_footprints_are_merged_from_the_gameplay_files(tmp_path):
    s = _gameplay_dir(tmp_path)
    assert not any(b.get("_footprint") for b in s["buildings"])
    n, total, findings = SS.annotate_footprints(s, str(tmp_path))
    assert (n, total) == (4, 4)
    assert [b["_footprint"] for b in s["buildings"]] != [None] * 4
    assert SS.CODE_FOOTPRINTS_MERGED in [f["code"] for f in findings]


def test_merging_is_what_makes_wall_bases_appear(tmp_path):
    """The whole point. Without it the guide's densest band gets nothing."""
    bare, _ = SS.zones(spec())
    assert not [z for z in bare if z["kind"] == "wall_base"]
    out = SS.surfaces(_gameplay_dir(tmp_path), base_dir=str(tmp_path))
    walls = [z for z in out["zones"] if z["kind"] == "wall_base"]
    assert len(walls) == 4
    assert all(z["density"] == "high" for z in walls)
    assert SS.CODE_FOOTPRINT_UNKNOWN not in [f["code"] for f in out["findings"]]


def test_a_rotated_building_gets_a_rotated_wall_base(tmp_path):
    """deli is placed at rot 90, so its 38x28 footprint is 28x38 on the
    ground. If this ever comes back square-on, `rotated_footprint` stopped
    being consulted and every rotated building is dressed to the wrong box."""
    out = SS.surfaces(_gameplay_dir(tmp_path), base_dir=str(tmp_path))
    deli = next(z for z in out["zones"]
                if z["surface_zone_id"] == "wall_base_deli")
    a = deli["aabb"]
    assert (a[4] - a[1]) > (a[3] - a[0])


def test_a_building_with_no_gameplay_file_is_still_reported(tmp_path):
    """Partial data must not read as complete data."""
    s = _gameplay_dir(tmp_path, {"garage": [36.0, 28.0], "pawn": [16.0, 14.0]})
    out = SS.surfaces(s, base_dir=str(tmp_path))
    assert len([z for z in out["zones"] if z["kind"] == "wall_base"]) == 2
    codes = [f["code"] for f in out["findings"]]
    assert SS.CODE_FOOTPRINT_UNKNOWN in codes
    msg = [f["message"] for f in out["findings"]
           if f["code"] == SS.CODE_FOOTPRINT_UNKNOWN][0]
    assert "deli" in msg and "gas" in msg


def test_no_base_dir_leaves_the_spec_exactly_as_it_was(tmp_path):
    """Falsification: the merge must be opt-in at the API level, or calling
    `surfaces` would quietly rewrite a caller's spec."""
    s = _gameplay_dir(tmp_path)
    SS.surfaces(s)
    assert not any(b.get("_footprint") for b in s["buildings"])


def test_merging_is_idempotent(tmp_path):
    s = _gameplay_dir(tmp_path)
    SS.annotate_footprints(s, str(tmp_path))
    first = [b["_footprint"] for b in s["buildings"]]
    n, _, findings = SS.annotate_footprints(s, str(tmp_path))
    assert [b["_footprint"] for b in s["buildings"]] == first
    # Nothing NEW was learned, so nothing is claimed.
    assert SS.CODE_FOOTPRINTS_MERGED not in [f["code"] for f in findings]


def test_an_unreadable_base_dir_is_a_finding_not_a_crash(tmp_path):
    """A greybox spec with no gameplay files is legitimate. It must degrade to
    the existing FOOTPRINT_UNKNOWN, not take the run down."""
    s = _gameplay_dir(tmp_path)
    out = SS.surfaces(s, base_dir=str(tmp_path / "nope"))
    assert out["zones"]
    assert SS.CODE_FOOTPRINT_UNKNOWN in [f["code"] for f in out["findings"]]


def test_cli_defaults_base_dir_to_the_specs_own_directory(tmp_path):
    """Which is where they sit for every spec in lot/specs -- so the common
    case needs no flag, and the flag exists for the case that differs."""
    import json
    s = _gameplay_dir(tmp_path)
    (tmp_path / "site.json").write_text(json.dumps(s), encoding="utf-8")
    out = tmp_path / "surfaces.json"
    assert SS.main([str(tmp_path / "site.json"), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len([z for z in data["zones"] if z["kind"] == "wall_base"]) == 4


def test_cli_empty_base_dir_skips_the_merge(tmp_path):
    import json
    s = _gameplay_dir(tmp_path)
    (tmp_path / "site.json").write_text(json.dumps(s), encoding="utf-8")
    out = tmp_path / "surfaces.json"
    SS.main([str(tmp_path / "site.json"), "--base-dir", "", "--out", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert not [z for z in data["zones"] if z["kind"] == "wall_base"]
