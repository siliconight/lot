"""An isolated building is a major finding, not a log line (0.124.0, factory roadmap 178).

`site_tactical.analyze` warned of a building no path or street reaches in `report["warnings"]`, a string
`lot.py` printed and nothing read. The same fact now stands in `report["findings"]` as `LOT_ISOLATED_BUILDING`,
severity `major`, the shape Level Factory's Lot adapter ingests and its pick counts. These cannot pass on
0.123.0's tree: the report had no `findings` key.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import site_tactical as st  # noqa: E402
from test_street_graph import _site  # noqa: E402


def test_a_site_with_no_road_and_no_paths_reports_every_building_but_the_root():
    rep = st.analyze(_site(road=None, spurs=False))
    assert rep["intel"]["isolated_buildings"] == ["b1", "b2"]
    assert [w for w in rep["warnings"] if "no declared path-route" in w], "the warning string stays"
    codes = [f["code"] for f in rep["findings"]]
    assert codes == ["LOT_ISOLATED_BUILDING"]
    f = rep["findings"][0]
    assert f["severity"] == "major"
    assert f["category"] == "combat_structure"
    assert "b1, b2" in f["message"] and "'b0'" in f["message"]
    # the four fields the adapter reads (`adapters/lot`: code, severity, category, message)
    assert {"code", "severity", "category", "message"} <= set(f)


def test_a_whole_site_reports_no_finding_and_the_list_is_there():
    rep = st.analyze(_site())
    assert rep["intel"]["isolated_buildings"] == []
    assert rep["findings"] == []


def test_the_finding_is_one_per_site_not_one_per_building():
    rep = st.analyze(_site(n=4, road=None, spurs=False))
    assert rep["intel"]["isolated_buildings"] == ["b1", "b2", "b3"]
    assert len(rep["findings"]) == 1
    assert rep["findings"][0]["message"].startswith("3 building(s)")
