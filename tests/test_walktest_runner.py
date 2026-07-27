"""Tests for walktest.py's runner behaviour: --require and --report-dir.

Offline and self-asserting, same style as test_lot.py -- no Godot is launched,
because the two things under test are what happens when Godot is ABSENT and
where a written report ends up.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import walktest as W


class _no_godot:
    """Run a block with every route to a Godot binary removed: the two env
    hints and PATH itself, so shutil.which finds nothing either."""

    def __enter__(self):
        self._saved = dict(os.environ)
        for var in ("LOT_GODOT", "DC_GODOT", "PATH"):
            os.environ.pop(var, None)
        return self

    def __exit__(self, *exc):
        os.environ.clear()
        os.environ.update(self._saved)
        return False


# --- --require: a check that did not run must not look like one that passed ---

def test_missing_godot_without_require_returns_zero():
    """The historical behaviour, pinned so a change to it is deliberate.

    A hand-run on a machine with no Godot should not fail a developer's build,
    which is why the skip exists. It is also exactly why an automated caller
    must not take the default: exit 0 with no report is a nav check that never
    happened, reported as success.
    """
    with tempfile.TemporaryDirectory() as d, _no_godot():
        assert W.main([d, "--all"]) == 0


def test_missing_godot_with_require_fails():
    with tempfile.TemporaryDirectory() as d, _no_godot():
        assert W.main([d, "--all", "--require"]) == 1


def test_find_godot_rejects_a_binary_that_is_not_godot_4():
    """A version string that does not start with '4.' is not a usable binary,
    and the reason comes back with the failure rather than as a bare None."""
    path, reason = W.find_godot(env={"LOT_GODOT": "/definitely/not/here/godot"})
    assert path is None
    assert "not found" in reason


# --- --report-dir: the report has to land where the caller asked ------------

def test_copy_report_places_the_file_and_returns_the_destination():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "site_navqa.walktest.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump({"ok": True}, f)
        out = os.path.join(d, "out")
        dst = W.copy_report(src, out)
        assert dst == os.path.join(out, "site_navqa.walktest.json")
        assert os.path.exists(dst)
        with open(dst, encoding="utf-8") as f:
            assert json.load(f)["ok"] is True


def test_copy_report_is_a_no_op_without_a_destination():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "r.walktest.json")
        open(src, "w").close()
        assert W.copy_report(src, None) is None


def test_copy_report_does_not_invent_a_report_that_was_never_written():
    """A missing source is the interesting case: the director writes nothing
    when the scene never ran, and copying must not paper over that."""
    with tempfile.TemporaryDirectory() as d:
        assert W.copy_report(os.path.join(d, "absent.json"),
                             os.path.join(d, "out")) is None
        assert not os.path.exists(os.path.join(d, "out", "absent.json"))


def test_copy_report_tolerates_the_destination_being_the_source():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "r.walktest.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump({"ok": False}, f)
        assert W.copy_report(src, d) == src
        with open(src, encoding="utf-8") as f:
            assert json.load(f)["ok"] is False


ALL = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    for fn in ALL:
        fn()
        print(f"[ok] {fn.__name__}")
    print(f"\n{len(ALL)} walktest runner tests passed.")
