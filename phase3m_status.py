import json, os
print("=== P3 MISSION GATES (6 sites) ===")
for spec in ["septa_station","mainline_mansion","museum_row","port_row","storage_row","brewery_block"]:
    wf = f"../_runs/{spec}_proj/{spec}_navqa.walktest.json"
    mf = f"../_runs/{spec}_proj/{spec}.mp_smoke.json"
    w = json.load(open(wf)) if os.path.exists(wf) else {}
    m = json.load(open(mf)) if os.path.exists(mf) else {}
    bad = [p['leg'] for p in w.get("path_proofs",[]) if not p['ok']]
    stuck = [x['name'] for x in w.get("walkers",[]) if not str(x['status']).startswith('ok')]
    print(f"  {spec:18s} walktest={'PASS' if w.get('ok') else 'FAIL'} sim={w.get('sim_seconds')}s bad_proofs={bad[:3]} stuck={stuck[:4]}  mp_smoke={'PASS' if m.get('ok') else 'FAIL'}")
