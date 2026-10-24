"""sweep.py: offline comparison of the repository encoding (as shipped: SKIP_ZERO_WORDS on) and the candidate encoder
over layer shapes and zero patterns. A layer counts as broken when any PE decodes any column wrong."""
import random, sys, time
from offline_check import check
from encoder import encode

SHAPES = [(20, 8, 2, 8), (8, 4, 8, 16), (8, 4, 4, 32), (28, 28, 2, 32), (14, 14, 32, 64), (7, 7, 64, 64)]
PATTERNS = ["rand0.05", "rand0.1", "rand0.3", "rand0.5", "rand0.9", "rand1.0", "chan0", "filter0", "kx0"]
TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def weights(C, F, pattern, seed):
    rng = random.Random(seed)
    w = [[[[rng.choice([v for v in range(-127, 128) if v]) for x in range(3)] for y in range(3)] for f in range(F)] for c in range(C)]
    for c in range(C):
        for f in range(F):
            for y in range(3):
                for x in range(3):
                    if (pattern.startswith("rand") and rng.random() < float(pattern[4:])) or \
                       (pattern == "chan0" and c == 0) or (pattern == "filter0" and f == 0) or (pattern == "kx0" and y == 0):
                        w[c][f][y][x] = 0
    return w


for W, H, C, F in SHAPES:
    t0 = time.time()
    row = []
    for pattern in PATTERNS:
        old_bad = new_bad = 0
        trials = 1 if pattern in ("rand1.0", "chan0", "filter0", "kx0") else TRIALS
        for t in range(trials):
            w = weights(C, F, pattern, 100 + t)
            r_old = check(w, W, H, skip=True)
            r_new = check(w, W, H, skip=False, encoder=encode)
            old_bad += r_old["bad_pes"] > 0
            new_bad += r_new["bad_pes"] > 0
        row.append(f"{pattern}: {old_bad}/{trials} -> {new_bad}/{trials}")
    print(f"{W}x{H}x{C}->{F} (fpc {r_old['fpc']}, dkpc {r_old['dkpc']}, reps {r_old['reps']}, M0 {r_old['M0']}, filters_w {r_old['filters_w']}, "
          f"{r_old['pes']} PE loads): " + "; ".join(row) + f"  [{time.time() - t0:.0f} s]", flush=True)
