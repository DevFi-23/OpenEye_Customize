"""padcheck.py <sim dir>: how many 20-bit slots of the DUT output stream differ from dma_stream_ref.txt in result slots
and how many only in padding slots / the bits above them (bug #9 writes non-zero padding). Needs OPENEYE_DUMP_VERIFY=1."""
import os, pickle, sys
sim = sys.argv[1]
d = pickle.load(open(os.path.join(sim, "verify_layer0.pkl"), "rb"))
bits, spw = d["psum_bits"], d["dma_bits"] // 32
order = d["output_order"]
if order and isinstance(order[0], list) and (not order[0] or isinstance(order[0][0], (list, type(None)))):
    order = [q for r in order for q in r]
demo = os.path.join(sim, "demo", "layer_0_0")
out = [l.strip() for l in open(os.path.join(demo, "output.txt")) if l.strip()]
ref = [l.strip() for l in open(os.path.join(demo, "dma_stream_ref.txt")) if l.strip()]
res = pad = 0
for i, (a, b) in enumerate(zip(out, ref)):
    if a == b:
        continue
    wa, wb = int(a, 2), int(b, 2)
    for s in range(spw):
        if (wa >> (bits * s)) & ((1 << bits) - 1) != (wb >> (bits * s)) & ((1 << bits) - 1):
            if spw * i + s < len(order) and order[spw * i + s] is not None:
                res += 1
            else:
                pad += 1
    if (wa >> (bits * spw)) != (wb >> (bits * spw)):
        pad += 1
print(f"{os.path.basename(sim)}: differing slots: {res} result, {pad} padding / upper bits")
