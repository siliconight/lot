"""No parking where the bus pulls in (0.131.0): a stop's zone, `BUS_ZONE_M` of kerb centred on its shelter, holds no
bay -- so no car, no meter, no paint -- on its side only. The walker, walking cold run 9386: "bus stop sign is for
cars/buses so there is no parking ther". FAILS ON 0.130.0."""
import site_furniture
import site_streets


def _street():
    return {"roads": [{"a": [-60.0, 0.0], "b": [60.0, 0.0], "width": 10.0, "sidewalk": 3.0}], "buildings": [],
            "paths": []}


def test_a_zone_empties_the_bays_it_overlaps_on_its_side_only():
    spec = _street()
    road = site_streets.roads(spec)[0]
    before = site_streets.bays(road)
    assert before, "the probe street has no bays: not a test"
    spec["bus_zones"] = [{"road": 0, "side": "L", "t0": 40.0, "t1": 40.0 + site_furniture.BUS_ZONE_M}]
    road = site_streets.roads(spec)[0]
    after = site_streets.bays(road)
    gone = [b for b in before if b not in after]
    assert gone and all(b["side"] == "L" and b["t1"] > 40.0 and b["t0"] < 40.0 + site_furniture.BUS_ZONE_M
                        for b in gone), gone
    assert [b for b in before if b["side"] == "R"] == [b for b in after if b["side"] == "R"]


def test_the_zone_is_nactos_midblock_length():
    assert abs(site_furniture.BUS_ZONE_M - 36.576) < 1e-9


def test_furniture_records_a_stops_zone_and_stands_no_meter_in_it():
    spec = _street()
    spec["buildings"] = [{"id": "b0", "at": [0.0, 20.0], "rot": 0, "footprint": [30.0, 20.0]}]
    roads = site_streets.roads(spec)
    pieces = site_furniture.plan_furniture(roads, spec["buildings"])
    shelters = [p for p in pieces if p["species"] == "bus_shelter"]
    zones = site_furniture.bus_zones(roads)
    assert len(shelters) == len(zones) >= 1, (shelters, zones)
    z = zones[0]
    assert abs((z["t0"] + z["t1"]) / 2.0 - shelters[0]["t"]) < 1e-3
    meters = [p for p in pieces if p["species"] == "parking_meter" and p["kerb"] == z["side"]]
    assert not [m for m in meters if z["t0"] <= m["t"] <= z["t1"]], meters
