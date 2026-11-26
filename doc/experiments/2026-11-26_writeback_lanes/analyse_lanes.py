"""analyse_lanes.py <prefix> <lanes> <seeds...> [--dir D]: identify the output (filter, x, y) of every write-back lane
value of layer 0. test/.temp/lanes_<prefix>_s<seed>/lanes.json per seed, or D/<prefix>_s<seed>.json with --dir (the saved
copies: doc/perf/writeback_lanes_2026-11-26); the write-back schedule does not depend on the data, so a
(capture, lane) slot holds the same output position in every seed: its candidates are the positions whose reference
value equals the lane value, intersected over the seeds. Prints the slot table and checks that every output is
written exactly once."""
import json
import sys
from collections import Counter

args = sys.argv[1:]
folder = None
if "--dir" in args:
    i = args.index("--dir")
    folder = args[i + 1]
    del args[i:i + 2]
prefix, lanes = args[0], int(args[1])
seeds = args[2:]
runs = [json.load(open(f"{folder}/{prefix}_s{s}.json" if folder else f"test/.temp/lanes_{prefix}_s{s}/lanes.json"))
        for s in seeds]
caps = [[c for c in r["captures"] if c["layer"] == 0] for r in runs]
refs = [r["refs"]["0"] for r in runs]
F, X, Y = len(refs[0]), len(refs[0][0]), len(refs[0][0][0])
sched = [[(c["psum_cycle"], c["x_cl"], c["y_cl"], c["main_cycle"], c["x_pos"]) for c in cs] for cs in caps]
print(f"{prefix}: {len(caps[0])} captures in layer 0, outputs {F} filters x {X} x {Y}; schedule identical over "
      f"{len(seeds)} seeds: {all(s == sched[0] for s in sched)}")
slots = []
for k in range(len(caps[0])):
    row = []
    for l in range(lanes):
        cand = None
        for r, cs in zip(refs, caps):
            v = cs[k]["lanes"][l]
            here = {(f, x, y) for f in range(F) for x in range(X) for y in range(Y) if r[f][x][y] == v}
            cand = here if cand is None else cand & here
        row.append(cand)
    slots.append(row)
written = Counter(next(iter(c)) for row in slots for c in row if len(c) == 1)
unique = sum(1 for row in slots for c in row if len(c) == 1)
empty = sum(1 for row in slots for c in row if not c)
amb = sum(1 for row in slots for c in row if len(c) > 1)
print(f"slots: {unique} unique, {amb} ambiguous, {empty} no match (padding); outputs written once: "
      f"{sum(1 for v in written.values() if v == 1)}/{F * X * Y}, twice or more: {sum(1 for v in written.values() if v > 1)}")
print("k  | cluster (x_cl, y_cl) | psum_cycle | x_pos | " + " | ".join(f"lane {l} (f, x, y)" for l in range(lanes)))
for k, (c, row) in enumerate(zip(caps[0], slots)):
    cells = []
    for cand in row:
        cells.append(str(next(iter(cand))) if len(cand) == 1 else ("-" if not cand else f"{len(cand)}?"))
    print(f"{k:2d} | ({c['x_cl']}, {c['y_cl']}) | {c['psum_cycle']:3d} | {c['x_pos']} | " + " | ".join(cells))
