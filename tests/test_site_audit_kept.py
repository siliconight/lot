"""The site audit is kept in the site's gameplay manifest, not only printed
(0.102.0, roadmap 215).

`assemble` runs `site_audit` at the end of every assembly. Until 0.102.0 it
printed the report to the job log and stored nothing, so Level Factory's
validation report -- and every cold run's findings diff, which counts that
report's codes -- never carried an `S_` code. Measured on cold run 9209's
seed_9181: the job log printed one MED (`S_RESPONDER_ARC`) and three INFO
(`S_GETAWAY_AT_SPAWN`, `S_STREET_CROSS` twice); the report carried none.

All three tests fail on 0.101.0: the manifest has no `site_audit` block, and
`site_audit` has no `record`.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lot          # noqa: E402
import site_audit   # noqa: E402

SPECS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "specs")

#: One finding as `format_report` prints it: "  [MED] S_BARE_LEG: ...".
PRINTED = re.compile(r"^  \[(HIGH|MED|INFO)\] (S_[A-Z_]+): ", re.M)


def _assemble(tmp_path, capsys, spec="example_compound.json"):
    r = lot.assemble(os.path.join(SPECS, spec), str(tmp_path / "out"))
    printed = capsys.readouterr().out
    with open(r["gameplay"], encoding="utf-8") as f:
        return json.load(f), printed


def test_the_manifest_keeps_what_the_job_log_prints(tmp_path, capsys):
    """Read against the printed report, not a list written here: the spec's
    findings can change, and what the log says must still be what is kept.
    On 0.101.0, `example_compound.json` printed 2 MED (S_NAKED_ANCHOR,
    S_ONE_APPROACH) and 1 INFO (S_NO_RESPONDERS) and kept none."""
    gameplay, printed = _assemble(tmp_path, capsys)
    assert "site_audit" in gameplay, sorted(gameplay)
    said = sorted(PRINTED.findall(printed))
    assert said, "the job log printed no site_audit finding: the spec no longer exercises the record"
    kept = sorted((f["severity"], f["code"]) for f in gameplay["site_audit"]["findings"])
    assert kept == said, (kept, said)


def test_the_counts_are_the_findings(tmp_path, capsys):
    block = _assemble(tmp_path, capsys)[0]["site_audit"]
    tally = {"HIGH": 0, "MED": 0, "INFO": 0}
    for f in block["findings"]:
        tally[f["severity"]] += 1
    assert block["counts"] == tally, (block["counts"], tally)
    assert block["mode"] == "heist"


def test_a_finding_is_named_fields_not_positions():
    """The audit's tuple would reach JSON as a three-item list, and a reader
    would have to know which position is the code. Named, a reader that
    cannot find a field can say so."""
    res = {"name": "t", "mode": "heist", "counts": {"HIGH": 0, "MED": 1, "INFO": 0},
           "findings": [("MED", "S_BARE_LEG", "the leg is bare")]}
    assert site_audit.record(res) == {
        "mode": "heist",
        "counts": {"HIGH": 0, "MED": 1, "INFO": 0},
        "findings": [{"severity": "MED", "code": "S_BARE_LEG",
                      "message": "the leg is bare"}],
    }
