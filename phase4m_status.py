#!/usr/bin/env python3
r"""Phase 4 mission status -- local ground truth for the 8 P4 sites.

Run from lot\ after the engine batch:
    python phase4m_status.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.normpath(os.path.join(HERE, "..", "_runs"))

SITES = ["ballpark_block", "rivers_casino", "phl_airport", "bank_tower_block",
         "xfinity_center", "reading_terminal", "independence_mall", "septa_yard"]


def load(p):
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return {"ok": False, "why": "unreadable report"}


wt_p = mp_p = 0
print(f"{'site':<18} {'walktest':<9} {'mp_smoke':<9}")
print("-" * 40)
for s in SITES:
    proj = os.path.join(RUNS, f"{s}_proj")
    wt = load(os.path.join(proj, f"{s}_navqa.walktest.json"))
    mp = load(os.path.join(proj, f"{s}.mp_smoke.json"))
    wv = "missing" if wt is None else ("PASS" if wt.get("ok") else "FAIL")
    mv = "missing" if mp is None else ("PASS" if mp.get("ok") else "FAIL")
    wt_p += wv == "PASS"
    mp_p += mv == "PASS"
    print(f"{s:<18} {wv:<9} {mv:<9}")
    for tag, r in (("wt", wt), ("mp", mp)):
        if r is not None and not r.get("ok"):
            why = r.get("why") or r.get("error") or ""
            legs = r.get("legs") or r.get("failures") or []
            if isinstance(legs, list):
                bad = [str(l)[:90] for l in legs
                       if isinstance(l, dict) and not l.get("ok")][:3]
                why = why or "; ".join(bad)
            if not why and "clients" in r:
                why = f"clients: {r['clients']} early_disc: {r.get('early_disconnects')}"
            if why:
                print(f"    [{tag}] {str(why)[:180]}")
print("-" * 40)
print(f"walktest {wt_p}/8   mp_smoke {mp_p}/8")
print("ALL GREEN" if wt_p == mp_p == 8 else "stragglers above")
