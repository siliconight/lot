"""A real, minimal ``.glb`` for tests that only need the file to be there.

Until 0.75.0 these were written as `b"glTF"` -- four bytes that are not a
glTF container. That was harmless while nothing in Lot read a module's
contents, and stopped being harmless the moment `cover_module_refs` started
asking each module what it names beside itself (`glb_deps`). Six tests turned
into `GlbUnreadable`.

A fixture that is not the format under test proves nothing about the format,
so they are real files now.
"""
from __future__ import annotations

import json
import os
import struct

_MAGIC = 0x46546C67
_JSON = 0x4E4F534A


def glb_bytes(tag: str = "stub", images=()) -> bytes:
    """A one-node glTF 2.0 binary. ``images`` names external textures."""
    doc = {
        "asset": {"version": "2.0", "generator": tag},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": tag}],
    }
    if images:
        doc["images"] = [{"name": os.path.basename(u).rsplit(".", 1)[0],
                          "uri": u} for u in images]
    payload = json.dumps(doc).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    chunk = struct.pack("<II", len(payload), _JSON) + payload
    return struct.pack("<III", _MAGIC, 2, 12 + len(chunk)) + chunk


def write_glb(path, tag: str = "stub", images=()):
    """Write `glb_bytes` at ``path``; return ``path``.

    Any texture named in ``images`` is written beside it, so the file is
    self-consistent -- a fixture that names a texture it does not have would
    be testing the copy's refusal path by accident.
    """
    path = str(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(glb_bytes(tag, images))
    for uri in images:
        tex = os.path.join(os.path.dirname(os.path.abspath(path)),
                           *uri.split("/"))
        os.makedirs(os.path.dirname(tex), exist_ok=True)
        with open(tex, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + b"\0" * 64)
    return path
