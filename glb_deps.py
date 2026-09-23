"""A GLB is not one file. Copy it by name and you copy half of it.

WHY THIS EXISTS. `cover_module_refs` stages a cover piece's module by copying
the one `.glb` it resolved out of the Zoo kit into `<out>/cover/`, exactly the
way the ground's skins are staged -- and its own docstring gives the reason:
"Every stage that loads a Lot scene copies its siblings." A GLB's siblings
grew. Zoo 1.2.0 stopped embedding a module's images and started writing them
beside it, named by a relative glTF `images[].uri`, and this copy went on
moving one file where there were now several.

Measured 2026-09-22 on cold run 9068's shipped `LF_club_block_007`: 1,264
external references across 265 GLBs, 1,264 of them resolving to nothing, of
which 128 are this repo's `cover/`. The walker's report was "around 90%
graybox".

THE SAME FILE EXISTS IN `deli_counter`, and deliberately. Neither repo imports
the other and neither imports Zoo; two spellings of one contract is the price
of that, and it is the price `level_factory.packages.exporting.export`'s
`SHARED_TEX_DIR` note already records paying. The gate that catches a drift
between them is `level_factory.packages.exporting.glb_refs`, which reads the
shipped package rather than either copy of this file.

NO LIBRARY. This reads the JSON chunk and nothing else -- it never rewrites
the file, so parsing the container is the whole job, and a dependency that
loads and re-saves a GLB to answer "what does it name" would be free to change
bytes this module has no business changing.

KEYED ON THE DOCUMENT, NOT ON A FOLDER NAME. `_tex` does not appear here. The
next asset class Zoo externalises will be carried by this function on the day
it appears, without an edit.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import urllib.parse

_MAGIC = 0x46546C67
_JSON_CHUNK = 0x4E4F534A

#: The document members glTF 2.0 permits a `uri` on.
_URI_HOLDERS = ("images", "buffers")


class GlbUnreadable(ValueError):
    """A `.glb` this module could not parse."""


def gltf_json(path):
    """The JSON chunk of the GLB at `path`, as a dict, or raise."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 12 or struct.unpack_from("<I", data, 0)[0] != _MAGIC:
        raise GlbUnreadable("%s: not a GLB (bad magic)" % path)
    off = 12
    while off + 8 <= len(data):
        clen, ctype = struct.unpack_from("<II", data, off)
        body = data[off + 8:off + 8 + clen]
        if len(body) != clen:
            raise GlbUnreadable("%s: truncated chunk at byte %d" % (path, off))
        if ctype == _JSON_CHUNK:
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise GlbUnreadable("%s: JSON chunk will not parse: %s"
                                    % (path, exc))
        off += 8 + clen + (-clen) % 4
    raise GlbUnreadable("%s: no JSON chunk" % path)


def dependencies(path):
    """Every file the GLB names beside itself, as relative POSIX paths.

    `data:` URIs are content rather than references and are skipped.
    Percent-decoded, because glTF 2.0 says a `uri` is URI-encoded.

    Raises rather than returning `[]` on a file it cannot read: "names
    nothing" and "could not be read" are different answers, and a caller
    copying files must not be handed the first when the truth is the second.
    """
    js = gltf_json(path)
    out = []
    for holder in _URI_HOLDERS:
        for ent in js.get(holder) or []:
            if not isinstance(ent, dict) or not ent.get("uri"):
                continue
            uri = str(ent["uri"])
            if uri.startswith("data:"):
                continue
            rel = urllib.parse.unquote(uri)
            if rel not in out:
                out.append(rel)
    return out


def _escapes(rel):
    depth = 0
    for part in rel.replace("\\", "/").split("/"):
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        elif part not in ("", "."):
            depth += 1
    return False


def copy_with_deps(src, dst):
    """Copy a GLB and everything it names, keeping the relative layout.

    Returns the list of dependency paths copied, relative to the GLB.

    The layout is preserved rather than flattened because the URI inside the
    binary is what has to keep resolving, and rewriting it is Zoo's job, not a
    copy's. A dependency already at the destination with the same size is left
    alone: Zoo's filenames carry a hash of the pixels, so the same name is the
    same file, and that is what makes sixty modules share one texture.

    Raises `OSError` when a named dependency is not there. A copy that
    silently drops half of what it was asked to move is the defect this
    module exists for, and it went out four times.
    """
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    deps = dependencies(src)
    shutil.copy2(src, dst)
    src_dir, dst_dir = os.path.dirname(src), os.path.dirname(os.path.abspath(dst))
    copied = []
    for rel in deps:
        if _escapes(rel) or os.path.isabs(rel) or "://" in rel:
            raise OSError("%s names %r, which cannot be bundled into a package"
                          % (src, rel))
        s = os.path.join(src_dir, *rel.split("/"))
        d = os.path.join(dst_dir, *rel.split("/"))
        if not os.path.isfile(s):
            raise OSError("%s names %r and %s is not there" % (src, rel, s))
        if not (os.path.isfile(d)
                and os.path.getsize(d) == os.path.getsize(s)):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
        copied.append(rel)
    return copied


def unresolved(pkg_dir):
    """Every GLB reference under `pkg_dir` that the directory does not satisfy.

    A report, not a verdict: `(glb_rel, uri)` pairs plus the GLBs that would
    not parse. The caller decides what a non-empty answer means -- except that
    an unreadable GLB is in the list, because reporting nothing about a file
    that could not be read is reporting that it is clean.
    """
    bad = []
    for root, _dirs, files in os.walk(pkg_dir):
        for f in sorted(files):
            if not f.endswith(".glb"):
                continue
            full = os.path.join(root, f)
            rel_glb = os.path.relpath(full, pkg_dir).replace("\\", "/")
            try:
                deps = dependencies(full)
            except GlbUnreadable as exc:
                bad.append((rel_glb, "UNREADABLE: %s" % exc))
                continue
            for rel in deps:
                if _escapes(rel) or os.path.isabs(rel) or "://" in rel:
                    bad.append((rel_glb, rel))
                elif not os.path.isfile(
                        os.path.join(root, *rel.split("/"))):
                    bad.append((rel_glb, rel))
    return bad
