"""A parking field is its own dressing zone, at a road's density (Lot 0.95.0)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lot  # noqa: E402
import site_surfaces as SS  # noqa: E402
import test_site_fields as TF  # noqa: E402


def _spec():
    site = TF._site()
    return TF._with_fields(site, TF._plan(site))


def test_a_field_declares_a_low_density_zone_at_its_own_height():
    spec = _spec()
    zs, _f = SS.zones(spec)
    (z,) = [z for z in zs if z["surface_zone_id"] == "field_0"]
    assert z["density"] == "low" and "zone_family:parking" in z["tags"]
    assert abs(z["aabb"][2] - lot.ROAD_THICK) < 1e-9                # the field's top
    x0, y0, x1, y1 = spec["fields"][0]["rect"]
    assert z["aabb"][0] == x0 and z["aabb"][1] == y0 and z["aabb"][3] == x1 and z["aabb"][4] == y1


def test_the_field_owns_its_ground_ahead_of_open_ground():
    """The precedence travels in the data: the field's zone comes before
    `open_ground`, so a point on the aisle is the field's."""
    spec = _spec()
    zs, _f = SS.zones(spec)
    ids = [z["surface_zone_id"] for z in zs]
    assert ids.index("field_0") < ids.index("open_ground")
    x0, y0, x1, y1 = spec["fields"][0]["rect"]
    aisle = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    assert SS.zone_for(aisle, zs)["surface_zone_id"] == "field_0"


def test_a_site_with_no_fields_declares_none():
    zs, _f = SS.zones(TF._site())
    assert not [z for z in zs if "zone_family:parking" in z["tags"]]


# --- the dressing reads the site as drawn (0.95.0) ----------------------------

def test_assemble_writes_the_site_it_drew(tmp_path):
    import json
    spec_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "specs", "coldrun_kerb_probe.json")
    lot.assemble(spec_path, str(tmp_path))
    authored = json.load(open(spec_path, encoding="utf-8"))
    drawn = json.load(open(tmp_path / f"{authored['name']}.site.drawn.json", encoding="utf-8"))
    # what assemble adds: the fields and their driveways, the cover, every
    # building's footprint; none of it in the authored spec
    assert drawn["fields"] and drawn["driveways"] == [f["driveway"] for f in drawn["fields"]]
    assert not authored.get("fields")
    assert drawn["cover"] and all(b.get("_footprint") for b in drawn["buildings"])


def test_the_surfaces_cli_reads_the_drawn_site_and_says_so(tmp_path):
    import json
    spec_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "specs", "coldrun_kerb_probe.json")
    lot.assemble(spec_path, str(tmp_path))
    out = tmp_path / "surfaces.json"
    assert SS.main([spec_path, "--out", str(out), "--base-dir", str(tmp_path)]) in (0, 1)
    doc = json.load(open(out, encoding="utf-8"))
    assert any(z["surface_zone_id"].startswith("field_") for z in doc["zones"])
    assert any(s["family"] == "parking" for s in doc["tops"])
    assert any(f["code"] == SS.CODE_SPEC_AS_DRAWN for f in doc["findings"])
    # the control: the same spec with no drawn site beside it is read as before
    bare = tmp_path / "bare"
    bare.mkdir()
    out2 = tmp_path / "surfaces_bare.json"
    SS.main([spec_path, "--out", str(out2), "--base-dir", ""])
    doc2 = json.load(open(out2, encoding="utf-8"))
    assert not any(z["surface_zone_id"].startswith("field_") for z in doc2["zones"])
    assert not any(f["code"] == SS.CODE_SPEC_AS_DRAWN for f in doc2["findings"])
