import shutil, os
DST = r"C:\Projects\gabagool_studios\gabagool_factory\_runs\p3_diag"
shutil.rmtree(DST, ignore_errors=True); os.makedirs(DST)
picks = [
 (r"..\_runs\storage_row_proj\storage_row.mp_smoke.json", "sr.smoke.json"),
 (r"..\_runs\brewery_block_proj\brewery_block_navqa.walktest.json", "bb.walktest.json"),
]
for lg in ("host", "client0", "client1", "client2"):
    picks.append((rf"..\_runs\storage_row_proj\_mp_logs\{lg}.log", f"sr_{lg}.log"))
for src, dst in picks:
    try:
        shutil.copy(src, os.path.join(DST, dst)); print("copied", dst)
    except Exception as e:
        print("MISS", dst, e)
print("done ->", DST)
