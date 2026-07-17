"""Site-level known-bad fixtures (Production Package acceptance 44-45): each
must fail its pvp_heist site gate for the documented reason."""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import site_tactical as st

HERE = os.path.dirname(os.path.abspath(__file__))
FIXDIR = os.path.join(os.path.dirname(HERE), "specs_failing")


def test_site_fixtures_fail_for_documented_reason():
    manifest = json.load(open(os.path.join(FIXDIR, "FIXTURES.json")))
    fixtures = sorted(glob.glob(os.path.join(FIXDIR, "fx_*.json")))
    assert fixtures, "no site failing fixtures"
    assert {os.path.basename(p) for p in fixtures} == set(manifest)
    for p in fixtures:
        spec = json.load(open(p))
        meta = manifest[os.path.basename(p)]
        try:
            st.gate(spec)
            raise AssertionError(
                f"{os.path.basename(p)} passed but must fail "
                f"({meta['reason']})")
        except st.SiteTacticalError as ex:
            assert meta["expected_code"].lower() in str(ex).lower(), \
                (f"{os.path.basename(p)} failed for the wrong reason: {ex} "
                 f"(expected '{meta['expected_code']}')")
    print(f"  {len(fixtures)} site failing fixture(s): OK")


if __name__ == "__main__":
    test_site_fixtures_fail_for_documented_reason()
