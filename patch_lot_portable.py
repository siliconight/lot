"""Add --portable to lot.py: emit shipped scenes with scene-relative refs.

Asserts every block it replaces and refuses to write on a miss. Run from the
lot repo root:

    python patch_lot_portable.py            # apply
    python patch_lot_portable.py --check    # report only, write nothing

WHAT THIS IS FOR. `write_godot_scene` and `write_walk_scene` have carried a
`portable` parameter since they were written, and no caller has ever passed it
-- `assemble` calls them with the default and there is no CLI flag, so the
setting has been unreachable from `python lot.py`. An unreachable parameter is
indistinguishable from one that does not work; this makes it reachable.

WHAT IT DOES NOT TOUCH. `write_navqa_scene` keeps `res://addons/lot/...`. The
nav-QA scene is not a deliverable -- it is an input to Lot's own walktest
harness, which stages `addons/lot/` itself and resolves those refs today.
Flipping it would change a working gate's contract for no gain, and the rule
here is that a fix which cannot be isolated should say which items it is
assumed to cover. This one covers the two scenes that ship.

MEASURED, NOT ASSUMED. Godot 4.7.stable resolves a non-`res://` ext_resource
path against the referencing scene's own directory: a probe whose root scene
instanced `lot/a/inner.tscn`, which referenced a bare `leaf.tscn` existing only
beside it, imported and loaded clean. Root-relative resolution would have
looked for `<project>/leaf.tscn` and missed.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("lot.py")

EDITS = [
    (
        "assemble signature",
        "def assemble(site_spec_path, out_dir=None, walkable=False, navqa=False, preview=False):\n"
        '    """Read a site spec, write <name>.site.gameplay.json and <name>.tscn."""\n',
        "def assemble(site_spec_path, out_dir=None, walkable=False, navqa=False,\n"
        "             preview=False, portable=False):\n"
        '    """Read a site spec, write <name>.site.gameplay.json and <name>.tscn.\n'
        "\n"
        "    With portable=True the SHIPPED scenes (the site scene and, with\n"
        "    --walkable, the walk scene) reference their contents relative to\n"
        "    themselves rather than through res://, so the out dir is a folder a\n"
        "    consumer can drop anywhere in their own project. res:// is rooted at\n"
        "    the project directory, so a res:// ref only resolves for a consumer\n"
        "    who reproduces this layout at their own root -- and an ABSOLUTE path\n"
        "    behind res:// (res://C:/...) asks for a folder named 'C:' inside the\n"
        "    project and resolves nowhere at all.\n"
        "\n"
        "    The nav-QA scene is deliberately excluded: it is consumed by Lot's\n"
        "    own walktest harness, which supplies addons/lot/ and resolves the\n"
        '    res:// form today.\n'
        '    """\n',
    ),
    (
        "site scene write",
        "    write_godot_scene(site_spec, merged, tscn_out, preview=preview,\n"
        "                      self_flooring=self_flooring)\n",
        "    write_godot_scene(site_spec, merged, tscn_out, preview=preview,\n"
        "                      portable=portable, self_flooring=self_flooring)\n",
    ),
    (
        "walk scene write",
        "        result[\"walk_positions\"] = write_walk_scene(\n"
        "            site_spec, merged, walk_out, site_spec[\"name\"], solids=solids)\n",
        "        result[\"walk_positions\"] = write_walk_scene(\n"
        "            site_spec, merged, walk_out, site_spec[\"name\"], solids=solids,\n"
        "            portable=portable)\n",
    ),
    (
        "cli flag",
        '    walkable = "--walkable" in sys.argv\n'
        '    navqa = "--navqa" in sys.argv\n'
        '    preview = "--preview" in sys.argv\n'
        "    if not args:\n"
        '        print("usage: python lot.py <site_spec.json> [out_dir] "\n'
        '              "[--walkable] [--navqa] [--preview]")\n',
        '    walkable = "--walkable" in sys.argv\n'
        '    navqa = "--navqa" in sys.argv\n'
        '    preview = "--preview" in sys.argv\n'
        '    portable = "--portable" in sys.argv\n'
        "    if not args:\n"
        '        print("usage: python lot.py <site_spec.json> [out_dir] "\n'
        '              "[--walkable] [--navqa] [--preview] [--portable]")\n',
    ),
    (
        "cli call",
        "        r = assemble(args[0], out, walkable=walkable, navqa=navqa, preview=preview)\n",
        "        r = assemble(args[0], out, walkable=walkable, navqa=navqa,\n"
        "                     preview=preview, portable=portable)\n",
    ),
]


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    if not TARGET.is_file():
        print(f"[patch] {TARGET} not found -- run from the lot repo root")
        return 1

    raw = TARGET.read_bytes()
    # Read BYTES and normalise deliberately. These files are CRLF; reading them
    # as text with universal newlines silently converts to LF, and writing that
    # back rewrites every line ending in the file -- a whole-file diff carrying
    # a five-line change. Normalise for matching, restore before writing.
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    print(f"[patch] {TARGET}: {len(raw)} bytes on disk, "
          f"{text.count(chr(10))} lines, endings={'CRLF' if crlf else 'LF'}")

    missing = [name for name, before, _ in EDITS if before not in text]
    already = [name for name, _, after in EDITS if after in text]
    for name in already:
        print(f"[patch]   ALREADY APPLIED: {name}")
    for name in missing:
        if name not in already:
            print(f"[patch]   ANCHOR NOT FOUND: {name}")

    todo = [(n, b, a) for n, b, a in EDITS if b in text and a not in text]
    if not todo:
        print("[patch] nothing to do")
        return 0 if not [m for m in missing if m not in already] else 1
    if [m for m in missing if m not in already]:
        print("[patch] REFUSING: at least one anchor did not match. The file "
              "has drifted from what this patch was written against; re-read "
              "it and re-author rather than forcing a partial edit.")
        return 1

    for name, before, after in todo:
        assert text.count(before) == 1, f"{name}: anchor is not unique"
        text = text.replace(before, after)
        print(f"[patch]   applied: {name}")

    if check_only:
        print("[patch] --check: no write")
        return 0

    payload = (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
    TARGET.write_bytes(payload)
    out = TARGET.read_bytes()
    print(f"[patch] wrote {TARGET}: {len(raw)} -> {len(out)} bytes "
          f"(+{len(out) - len(raw)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
