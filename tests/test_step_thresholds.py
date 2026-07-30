"""The two step thresholds have to meet. Pure arithmetic, no Godot, no Blender.

A capsule of radius R meeting a step of height h < R contacts it on the bottom
HEMISPHERE, so the contact normal is sloped and its vertical component is

    n.y = (R - h) / R

Two separate pieces of the stack read that number, and until now they disagreed
about where the boundary was, leaving a band of step heights that nothing handled.

  * WALKING. CharacterBody3D calls a contact floor only while its angle stays
    inside floor_max_angle, so the tallest step a body walks up with no help is
    h_walk = R * (1 - cos(floor_max_angle)).  (site_steps.unassisted_step_max_m)

  * STEP-UP. lot_player.gd lifts the body onto a step only when the contact reads
    as a wall. It tested `absf(n.y) < 0.2`, a picked constant, which engages only
    for h > 0.8 * R -- so between h_walk and 0.8*R the body could neither walk up
    nor be stepped up, and it stopped dead. Gating on cos(floor_max_angle)
    instead makes the step-up's lower bound equal h_walk exactly, by algebra
    rather than by coincidence:

        n.y < cos(a)  <=>  (R - h)/R < cos(a)  <=>  h > R * (1 - cos(a))

These tests pin that identity, pin the dead band the old constant created, and
pin that Lot's emitted surface heights fall on the right side of both bounds.

    python -m pytest lot/tests/test_step_thresholds.py -q
"""
import json
import math
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
LOT = os.path.dirname(HERE)
ROOT = os.path.dirname(LOT)
CONTRACT = os.path.join(ROOT, "deli_counter", "agent_contract.json")
PLAYER_GD = os.path.join(LOT, "godot", "addons", "lot", "lot_player.gd")

FLOOR_MAX_ANGLE_DEG = 45.0          # Godot's CharacterBody3D default
OLD_PICKED_THRESHOLD = 0.2          # what lot_player.gd used to test n.y against


def normal_y(radius, step_h):
    """Vertical component of the contact normal, capsule vs a step of step_h."""
    if step_h >= radius:
        return 0.0                  # contact moves onto the cylinder: vertical face
    return (radius - step_h) / radius


def walk_max(radius, angle_deg=FLOOR_MAX_ANGLE_DEG):
    """Tallest step the body WALKS up unassisted."""
    return radius * (1.0 - math.cos(math.radians(angle_deg)))


def step_up_min(radius, threshold):
    """Shortest step whose contact normal passes `n.y < threshold`."""
    return radius * (1.0 - threshold)


def contract():
    with open(CONTRACT, encoding="utf-8") as f:
        return json.load(f)


# --- the identity the fix rests on ------------------------------------------

@pytest.mark.parametrize("radius", [0.25, 0.3, 0.35, 0.4, 0.5, 0.6])
@pytest.mark.parametrize("angle", [30.0, 45.0, 50.0, 55.0])
def test_floor_threshold_makes_the_ranges_meet(radius, angle):
    """Gating step-up on cos(floor_max_angle) puts its floor exactly at the walk
    ceiling -- for ANY body and ANY floor angle. No gap, no overlap."""
    ceiling = walk_max(radius, angle)
    floor = step_up_min(radius, math.cos(math.radians(angle)))
    assert floor == pytest.approx(ceiling, abs=1e-12)


@pytest.mark.parametrize("radius", [0.3, 0.35, 0.4, 0.5])
def test_the_old_constant_left_a_dead_band(radius):
    """The picked 0.2 engaged only above 0.8*R, well past the walk ceiling, so
    steps in between were handled by neither mechanism."""
    ceiling = walk_max(radius)
    floor = step_up_min(radius, OLD_PICKED_THRESHOLD)
    assert floor == pytest.approx(0.8 * radius)
    assert floor > ceiling, "no dead band to explain -- check the arithmetic"
    band = floor - ceiling
    assert band > 0.05, f"band of {band:.4f} m is too small to match play reports"


def test_the_kerb_sat_inside_that_band_for_the_contract_body():
    """SIDEWALK_H is 0.16 and this is why walking off the ground onto a sidewalk
    stopped the body despite a controller that nominally climbs 0.45 m."""
    r = float(contract()["characters"]["player"]["radius_m"])
    ceiling, floor = walk_max(r), step_up_min(r, OLD_PICKED_THRESHOLD)
    for name, h in (("sidewalk", 0.16), ("courtyard-as-was", 0.12)):
        assert ceiling < h < floor, (
            f"{name} at {h} is not in the dead band "
            f"({ceiling:.4f}..{floor:.4f}) for a {r} m body")


def test_the_fix_covers_that_band():
    c = contract()
    r = float(c["characters"]["player"]["radius_m"])
    ceiling = float(c["characters"]["player"]["max_step_up_m"])
    floor = step_up_min(r, math.cos(math.radians(FLOOR_MAX_ANGLE_DEG)))
    for name, h in (("sidewalk", 0.16), ("courtyard-as-was", 0.12)):
        assert floor <= h <= ceiling, f"{name} at {h} still unhandled"


# --- the contract agrees with the formula -----------------------------------

def test_contract_records_the_walk_ceiling_it_derives():
    c = contract()
    r = float(c["characters"]["player"]["radius_m"])
    assert float(c["clearances"]["unassisted_step_max_m"]) == pytest.approx(
        walk_max(r), abs=5e-5)


def test_emitted_surfaces_are_walkable_or_steppable():
    """Lot's outdoor slabs must be walkable; the kerb must be within step-up."""
    import sys
    sys.path.insert(0, LOT)
    import lot as lot_mod
    c = contract()
    r = float(c["characters"]["player"]["radius_m"])
    ceiling = float(c["characters"]["player"]["max_step_up_m"])
    walk = walk_max(r)
    for name, h in (("ROAD_THICK", lot_mod.ROAD_THICK),
                    ("PATH_THICK", lot_mod.PATH_THICK),
                    ("COURT_THICK", lot_mod.COURT_THICK)):
        assert h <= walk, f"{name} {h} is above the walk ceiling {walk:.4f}"
        assert lot_mod.SIDEWALK_H - h <= walk, (
            f"{name} {h} -> sidewalk {lot_mod.SIDEWALK_H} is "
            f"{lot_mod.SIDEWALK_H - h:.4f}, above the walk ceiling")
    assert lot_mod.SIDEWALK_H <= ceiling, (
        f"a {lot_mod.SIDEWALK_H} m kerb is beyond step-up ({ceiling}); nothing "
        f"gets onto it from the ground without a jump")


# --- the shipped controller matches all of the above ------------------------

def test_player_gd_gates_on_the_floor_angle_not_a_constant():
    """Reads the shipped controller, because the arithmetic above is only worth
    anything if the code actually uses it."""
    if not os.path.exists(PLAYER_GD):
        pytest.skip("lot_player.gd not present")
    src = open(PLAYER_GD, encoding="utf-8").read()
    assert "cos(floor_max_angle)" in src, (
        "the step-up gate is not derived from floor_max_angle")
    assert "absf(col.get_normal().y) < 0.2" not in src, (
        "the picked 0.2 threshold is still in the step-up gate")


def test_player_gd_head_probe_is_not_a_pinned_height():
    if not os.path.exists(PLAYER_GD):
        pytest.skip("lot_player.gd not present")
    src = open(PLAYER_GD, encoding="utf-8").read()
    assert "step_top + body_height" in src, (
        "the head-clearance probe does not use the body height")
    assert "step_top + 1.7" not in src, (
        "the head-clearance probe still uses a pinned 1.7 m")
