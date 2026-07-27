#!/usr/bin/env python3
r"""remediate_s3.py -- fix naked crossings (site_layout_lint S3) in place.

For every declared path leg longer than 40 m with no cover near its line,
place cover along the leg every ~22 m: offset alternately left/right of the
path line, with deterministically varied dims (never the identical-box
anti-pattern, LAYOUT_RULES D2).

    python remediate_s3.py            # dry run
    python remediate_s3.py --write    # apply
"""
import glob
import hashlib
import json
import math
import os
import sys

import site_layout_lint as SL

HERE = os.path.dirname(os.path.abspath(__file__))
WRITE = "--write" in sys.argv
STEP = 22.0
OFFSET = 4.0


def jitter(seed_key, lo, hi):
    h = int(hashlib.sha256(seed_key.encode()).hexdigest()[:8], 16)
    return lo + (h % 1000) / 999.0 * (hi - lo)


def main():
    changed = []
    for p in sorted(glob.glob(os.path.join(HERE, "specs", "*", "*_site.json"))):
        s = json.load(open(p))
        if s.get("mode") != "pvp_heist":
            continue
        name = s["name"]
        pos = {b["id"]: tuple(b["at"]) for b in s.get("buildings", [])}
        cover = [tuple(c["at"]) for c in s.get("cover", [])]
        added = 0
        for e in s.get("paths", []):
            a, b = e["from"], e["to"]
            if a not in pos or b not in pos:
                continue
            ax, ay = pos[a]; bx, by = pos[b]
            L = math.hypot(bx - ax, by - ay)
            if L <= SL.KILL_LANE:
                continue
            if any(SL._seg_point_dist(pos[a], pos[b], c) <= SL.COVER_NEAR
                   for c in cover):
                continue
            ux, uy = (bx - ax) / L, (by - ay) / L      # along
            nx, ny = -uy, ux                            # normal
            n = int(L // STEP)
            for i in range(1, n + 1):
                t = i * STEP
                if t >= L - 8:
                    break
                side = 1 if i % 2 else -1
                key = f"{name}:{a}->{b}:{i}"
                cx = ax + ux * t + nx * OFFSET * side
                cy = ay + uy * t + ny * OFFSET * side
                s.setdefault("cover", []).append({
                    "at": [round(cx, 1), round(cy, 1)],
                    "size": [round(jitter(key + "x", 1.8, 3.2), 2),
                             round(jitter(key + "y", 0.9, 1.6), 2),
                             round(jitter(key + "z", 1.0, 1.4), 2)]})
                cover.append((cx, cy))
                added += 1
        if added:
            changed.append((name, added))
            if WRITE:
                json.dump(s, open(p, "w"), indent=1)
    for name, n in changed:
        print(f"{'FIXED' if WRITE else 'would fix'} {name}: +{n} cover")
    print(f"[remediate-s3] {len(changed)} sites, "
          f"{sum(n for _, n in changed)} cover volumes "
          f"{'written' if WRITE else '(dry run)'}")


if __name__ == "__main__":
    main()
