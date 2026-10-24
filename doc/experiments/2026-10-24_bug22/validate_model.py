"""validate_model.py <dump.json> <filters_w>: replay each PE's recorded input words (enable cycles) through the model and
compare the address/data SPad write sequences with the RTL dump (first load: writes before the first compute pulse
that follows the load)."""
import json, sys
from wght_pipeline_model import run

log = json.load(open(sys.argv[1]))
F = int(sys.argv[2])
ok = bad = 0
for pe, ev in sorted(log.items()):
    ins = [e for e in ev if e[0] == "I"]
    if not ins:
        continue
    first, last = ins[0][1], ins[-1][1]
    by_cycle = {e[1]: (e[2] or 0) for e in ins}   # X data (one trailing enable cycle) acts like 0 in the if conditions
    seq = [((1, by_cycle[c]) if c in by_cycle else (0, 0)) for c in range(first, last + 1)] + [(0, 0)] * 3
    a_m, d_m = run(None, F, seq=seq)
    end = last + 4
    a_r = [(e[2], e[3]) for e in ev if e[0] == "A" and first <= e[1] <= end]
    d_r = [(e[2], e[3]) for e in ev if e[0] == "D" and first <= e[1] <= end]
    if a_m == a_r and d_m == d_r:
        ok += 1
    else:
        bad += 1
        if bad <= 2:
            print("PE", pe, "inputs", len(ins), "cycles", first, last)
            print("  A model", a_m[:40]); print("  A rtl  ", a_r[:40])
            print("  D model", d_m[:12]); print("  D rtl  ", d_r[:12])
print(f"{sys.argv[1]}: model = RTL for {ok} PEs, differs for {bad}")
