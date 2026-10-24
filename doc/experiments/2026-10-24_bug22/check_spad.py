"""check_spad.py <dump.json> <channels> <filters>: decode every PE's weight SPads as the PE reads them and compare
with the weights of the layer (single weight transmission, 3x3 kernel, one cluster row of kernel rows).

PE reading (from the passing control): column k = data words [addr[k-1], addr[k]) (addr[-1] = 0); inside a column,
pos starts at 0, each entry (value, overhead): pos += overhead, weight[pos] = value, pos += 1. Column k of PE row r is
kernel_x = k // C, channel = k % C, i.e. weights w[c][f][kernel_x][r] for f = 0..F-1."""
import json, sys
from show_spad import load, entries

dump, C, F = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
w = json.load(open(dump + ".weights.json"))["weights"]
spads = load(dump)
bad_pes = 0
for pe in sorted(spads):
    addr, data, _ = spads[pe]
    row = int(pe[3])
    ptr = [addr[a] for a in sorted(addr)]
    problems = []
    ncols = 3 * C
    if len(ptr) != ncols:
        problems.append(f"{len(ptr)} column pointers instead of {ncols}: {ptr}")
    for k in range(ncols):
        kx, c = k // C, k % C
        want = [w[c][f][kx][row] for f in range(F)]
        if k >= len(ptr):
            problems.append(f"col {k} (kx{kx} c{c}) missing, want {want}")
            continue
        start = ptr[k - 1] if k else 0
        got, pos, ent = [0] * F, 0, []
        for a in range(start, ptr[k]):
            for v, oh in entries(data.get(a, 0)):
                ent.append((v, oh))
                pos += oh
                if pos < F:
                    got[pos] = v
                elif v != 0:
                    got.append(("out of range", pos, v))
                pos += 1
        if got != want:
            problems.append(f"col {k} (kx{kx} c{c}) words {start}..{ptr[k]-1} entries {ent} -> {got}, want {want}")
    if problems:
        bad_pes += 1
        if bad_pes <= 3:
            print(f"== PE {pe}:")
            for p in problems[:6]:
                print("   ", p)
print(f"{bad_pes} of {len(spads)} PEs decode wrong")
