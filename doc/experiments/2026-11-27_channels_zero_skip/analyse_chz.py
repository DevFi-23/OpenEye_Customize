"""analyse_chz.py: compute cycles of 14 x 14 x C -> 32 against the input zero share, from the profiles of test_chz.py
(test/.temp/*test_chz_<case>_/profile.json). Prints, per C: dense compute, sparse compute at 0 / 40 / 80 % zero inputs,
the reduction at 40 / 80 %, the total sparse / dense ratio at 80 %, and the channel passes of the layer."""
import glob
import json

CHANNELS = [1, 2, 4, 8, 16, 32, 64]


def prof(case):
    f = glob.glob(f"test/.temp/*test_chz_{case}_/profile.json")
    return json.load(open(f[0])) if f else None


def ph(r, n):
    return r["phases"].get(n, {}).get("cycles", 0)


print("C | dense compute | sparse 0 % | 40 % | 80 % | reduction 40 % | reduction 80 % | compute per channel (sparse 0 %) "
      "| total sparse / dense at 80 %")
for c in CHANNELS:
    d = prof(f"c{c}_a0_dense")
    s = {a: prof(f"c{c}_a{a}_sparse") for a in ("0", "0.4", "0.8")}
    if not d or not all(s.values()):
        print(c, "missing")
        continue
    s0, s4, s8 = (ph(s[a], "compute") for a in ("0", "0.4", "0.8"))
    print(f"{c:2d} | {ph(d, 'compute'):6d} | {s0:6d} | {s4:6d} | {s8:6d} | {100 * (s4 - s0) / s0:6.1f} % | "
          f"{100 * (s8 - s0) / s0:6.1f} % | {s0 / c:7.1f} | {100 * s['0.8']['total_cycles'] / d['total_cycles']:5.1f} %")
