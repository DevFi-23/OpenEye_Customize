"""rtl_vs_ref.py <test/.temp dir> <N> <Clusters_X>: compare the Dense output beats the RTL sent (log lines of
DUMP_PSUM_BUFFERS=1) with the reference stream of make_ref (demo/layer_0_0/dma_stream_ref.txt), then decode the beats
with the make_ref / psum buffer layout (beat = r*CX*P + a*CX + c -> f = r*CX*P + c*P + a) and count right outputs."""
import math, re, sys
D, N, CX = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
log = open(f"{D}/cocotb_sim.log", errors="replace").read()
beats = [int(m.group(1)) for m in re.finditer(r"Dense DMA beat=\d+ f=\d+ value=(-?\d+)", log)]
def s20(v): v &= (1 << 20) - 1; return v - (1 << 20) if v >> 19 else v
ref = [s20(int(l, 2)) for l in open(f"{D}/demo/layer_0_0/dma_stream_ref.txt").read().split()]
P = len(ref) // (CX * math.ceil(N / (16 * CX)))
def decode(words):
    out = {}
    for b, v in enumerate(words):
        r, rem = divmod(b, CX * P); a, c = divmod(rem, CX)
        out[r * CX * P + c * P + a] = v
    return out
got, want = decode(beats), decode(ref)
print(f"beats {len(beats)}, ref words {len(ref)}, P {P}; RTL == make_ref at {sum(a == b for a, b in zip(beats, ref))} beats; "
      f"decoded: {sum(got.get(f) == want[f] for f in range(N))}/{N} outputs right; "
      f"padding slots {sorted(f for f in want if f >= N)} RTL values {[got.get(f) for f in sorted(want) if f >= N]}")
print([l.split('cocotb')[-1].strip() for l in log.splitlines() if 'outputs differ' in l])
