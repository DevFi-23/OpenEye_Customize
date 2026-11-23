"""compare_profiles.py <dir A> <dir B>: compare the saved profiles (*.json except status.json) of two runs: total
cycles and every phase of every layer; prints the differences and a summary, and the status.json verdicts of both."""
import json, os, sys
a, b = sys.argv[1:3]
names = sorted(f for f in os.listdir(a) if f.endswith(".json") and f != "status.json")
same = diff = missing = 0
for n in names:
    pb = os.path.join(b, n)
    if not os.path.exists(pb):
        missing += 1; print("MISSING", n); continue
    x, y = json.load(open(os.path.join(a, n))), json.load(open(pb))
    d = []
    if x.get("total_cycles") != y.get("total_cycles"):
        d.append(f"total {x.get('total_cycles')} -> {y.get('total_cycles')}")
    for lx, ly in zip(x.get("layers", []), y.get("layers", [])):
        for ph in sorted(set(lx["phases"]) | set(ly["phases"])):
            cx = lx["phases"].get(ph, {}).get("cycles"); cy = ly["phases"].get(ph, {}).get("cycles")
            if cx != cy:
                d.append(f"layer {lx['index']} {ph} {cx} -> {cy}")
    if len(x.get("layers", [])) != len(y.get("layers", [])):
        d.append("layer count differs")
    if d:
        diff += 1; print("DIFF", n, "; ".join(d[:6]))
    else:
        same += 1
print(f"identical {same}, different {diff}, missing {missing} (of {len(names)})")
for side in (a, b):
    s = os.path.join(side, "status.json")
    if os.path.exists(s):
        st = json.load(open(s))
        vals = list(st.values()) if isinstance(st, dict) else st
        print(side, "status:", {v: vals.count(v) for v in set(map(str, vals))})
