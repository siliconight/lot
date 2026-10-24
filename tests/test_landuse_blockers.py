"""The census counts an Empty as built land (0.130.0): a `blockers` entry's footprint is `building`, not remainder.
The walker, walking cold run 9386: "this empty space goes against the doc i sent you about the value of urban land"
-- and restaurant_row_001's 26 rowhomes had read as remainder. FAILS ON 0.129.0."""
import site_landuse


def _spec(blockers):
    return {"ground": {"size_x": 40, "size_y": 20}, "buildings": [], "roads": [], "paths": [],
            "blockers": blockers}


def _as_building(bl):
    """The same footprint as a mission's building: what the census has always measured a building's land as, its
    0.5 m cells included at the edges."""
    s = _spec([])
    s["buildings"] = [{"id": "b0", "at": bl["at"], "rot": bl["rot"], "footprint": [bl["size_x"], bl["size_y"]]}]
    return site_landuse.census(s)


def test_an_empty_is_building_land_not_remainder():
    bl = {"id": "e0", "at": [5.0, 0.0], "rot": 180, "size_x": 6.0, "size_y": 12.0}
    bare = site_landuse.census(_spec([]))
    one = site_landuse.census(_spec([bl]))
    assert bare["ok"] and one["ok"], (bare, one)
    assert bare["areas"]["building"] == 0.0
    assert one["areas"]["building"] == _as_building(bl)["areas"]["building"] > 0.0, one["areas"]
    assert one["areas"]["remainder"] == bare["areas"]["remainder"] - one["areas"]["building"]


def test_an_empty_turned_a_quarter_is_measured_turned():
    bl = {"id": "e0", "at": [0.0, 0.0], "rot": 90, "size_x": 6.0, "size_y": 12.0}
    assert site_landuse.census(_spec([bl]))["areas"]["building"] == _as_building(bl)["areas"]["building"]


def test_an_empty_is_not_a_building_the_mission_enters():
    c = site_landuse.census(_spec([{"id": "e0", "at": [5.0, 0.0], "rot": 0, "size_x": 6.0, "size_y": 12.0}]))
    assert c["nearest_building_gap"] == {}, c["nearest_building_gap"]
