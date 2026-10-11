"""The walk test's clock and its navigation (0.117.0, factory roadmap 239).

Offline, like test_walktest_runner.py: no Godot is launched. The director simulates at Godot's
default clock, which waits on real seconds -- cold run 9247's walk tests took 2.1 to 2.6 minutes
-- and `--fixed-fps 60` computes the same steps as fast as the processor allows. That is only
safe because `lot_navqa_setup.gd` makes the navigation map and the site's region update
synchronously BEFORE it bakes: with Godot's default worker-thread iterations, the fixed clock
read the map EMPTY on every candidate, the director's ten-second wait gone in milliseconds.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import walktest as W

SETUP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "godot", "addons", "lot", "lot_navqa_setup.gd")


class _Proc:
    stdout = ""
    returncode = 0


def _command(monkeypatch, tmp_path):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = list(cmd)
        return _Proc()

    monkeypatch.setattr(W.subprocess, "run", fake_run)
    scene = tmp_path / "site_navqa.tscn"
    scene.write_text("", encoding="utf-8")
    W.run_one("godot", str(tmp_path), str(scene), timeout=5)
    return seen["cmd"]


def test_the_scene_runs_on_the_fixed_clock(monkeypatch, tmp_path):
    cmd = _command(monkeypatch, tmp_path)
    assert "--fixed-fps" in cmd, cmd
    i = cmd.index("--fixed-fps")
    assert cmd[i + 1] == "60", cmd
    assert i < cmd.index("--path"), "an engine argument, with the others before the scene"


def test_zero_restores_the_waiting_clock(monkeypatch, tmp_path):
    monkeypatch.setattr(W, "FIXED_FPS", 0)
    assert "--fixed-fps" not in _command(monkeypatch, tmp_path)


def _bake_nav_body():
    text = open(SETUP, encoding="utf-8").read()
    start = text.index("func _bake_nav(")
    end = text.find("\nfunc ", start + 1)
    return text[start:end if end != -1 else len(text)]


def test_the_map_and_the_region_iterate_synchronously_before_the_bake():
    body = _bake_nav_body()
    bake = body.find("bake_navigation_mesh(")
    assert bake != -1, "the setup no longer bakes where this test looks"
    m = re.search(r"map_set_use_async_iterations\(\s*map\s*,\s*false\s*\)", body)
    r = re.search(r"region_set_use_async_iterations\(\s*nav\.get_rid\(\)\s*,\s*false\s*\)", body)
    assert m and m.start() < bake, "the map is set synchronous before the bake"
    assert r and r.start() < bake, "and the site's region"


def test_the_commit_is_still_forced_after_the_bake():
    """The setters are server commands that land at the next sync; the force_update after the
    bake is that sync, so it has to stay."""
    body = _bake_nav_body()
    assert body.find("map_force_update(map)") > body.find("bake_navigation_mesh(")
