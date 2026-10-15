#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Independent, word-by-word check of the DMA output of a convolution layer.

The testbench compares the DUT with a reference produced by the same Python
package that builds the input stream, so a mistake shared by both (stream
order, operand packing) can pass. This tool recomputes the layer with numpy
from the raw integers the DUT received and checks every output word.

Run a simulation with OPENEYE_DUMP_VERIFY=1 (writes verify_layer0.pkl into
the simulation directory, next to demo/layer_0_0/output.txt and
dma_stream_ref.txt), then:

    venv/bin/python tools/verify_conv_output.py test/.temp/<sim dir> [more dirs]

Per directory it reports:
  - output words of the DUT vs the reference file: identical lines, lines with
    X, non-zero bits above the psum slots, non-zero padding slots, and whether
    every line that differs from the reference is padding only;
  - coverage: every (filter, x, y) decoded exactly once (missing, duplicated);
  - the DUT values vs the numpy result (Keras orientation: dram.weights
    [c][f][ky][kx] = kernel[kx][ky][c][f]); the transposed orientation is
    printed as a sanity check (it must differ when the data is not symmetric);
  - the testbench reference vs numpy, and values outside the psum width.
Exit code 0 when every result slot equals numpy and coverage is complete.
"""
import os
import pickle
import sys

import numpy as np


def check(sim_dir, layer=0):
    dump = pickle.load(open(os.path.join(sim_dir, f"verify_layer{layer}.pkl"), "rb"))
    bits = dump["psum_bits"]
    slots_per_word = dump["dma_bits"] // 32          # psums per DMA word (two 20-bit slots in 64 bit)
    fm = np.array(dump["fmap"], dtype=np.int64)      # [c][x][y]
    W = np.array(dump["weights"], dtype=np.int64)    # [c][f][ky][kx]
    F = dump["filters"]
    b = np.array(dump["bias"], dtype=np.int64)[:F]
    C, X, Y = fm.shape
    K = W.shape[-1]
    p = K // 2
    if dump["stride"] != [1, 1]:
        raise SystemExit("only stride 1 is supported")
    pad = np.zeros((C, X + 2 * p, Y + 2 * p), dtype=np.int64)
    pad[:, p:p + X, p:p + Y] = fm

    def conv(kernel_for):
        out = np.zeros((F, X, Y), dtype=np.int64)
        for f in range(F):
            acc = np.full((X, Y), b[f], dtype=np.int64)
            for c in range(C):
                k = kernel_for(c, f)
                for i in range(K):
                    for j in range(K):
                        acc += k[i][j] * pad[c, i:i + X, j:j + Y]
            out[f] = acc
        return out

    def wrap(a):
        a = a & ((1 << bits) - 1)
        return np.where(a >= 1 << (bits - 1), a - (1 << bits), a)

    expected = conv(lambda c, f: W[c, f].T)
    transposed = conv(lambda c, f: W[c, f])
    ref = dump["reference"]
    if isinstance(ref, dict):
        ref = [ref[k] for k in sorted(ref)]
    ref = np.array(ref, dtype=np.int64)[:F, :X, :Y]

    demo = os.path.join(sim_dir, "demo", f"layer_0_{layer}")
    out_lines = [l.strip() for l in open(os.path.join(demo, "output.txt")) if l.strip()]
    ref_lines = [l.strip() for l in open(os.path.join(demo, "dma_stream_ref.txt")) if l.strip()]
    order = [pos for rep in dump["output_order"] for pos in rep] \
        if dump["output_order"] and isinstance(dump["output_order"][0], list) and \
        (not dump["output_order"][0] or isinstance(dump["output_order"][0][0], (list, type(None)))) \
        else dump["output_order"]

    def has_result(i):
        return any(slots_per_word * i + k < len(order) and order[slots_per_word * i + k] is not None
                   for k in range(slots_per_word))

    dut, x_words, upper, pad_nonzero = {}, 0, 0, 0
    for wi, line in enumerate(out_lines):
        if set(line.lower()) - {"0", "1"}:
            x_words += 1
            continue
        word = int(line, 2)
        if word >> (slots_per_word * bits):
            upper += 1
        for i in range(slots_per_word):
            idx = slots_per_word * wi + i
            pos = order[idx] if idx < len(order) else None
            val = (word >> (bits * i)) & ((1 << bits) - 1)
            val = val - (1 << bits) if val >= 1 << (bits - 1) else val
            if pos is None:
                pad_nonzero += val != 0
                continue
            dut.setdefault(tuple(pos), []).append(val)

    positions = [(f, x, y) for f in range(F) for x in range(X) for y in range(Y)]
    missing = [k for k in positions if k not in dut]
    dupes = [k for k, v in dut.items() if len(v) > 1]
    differ = [k for k in positions if k in dut and dut[k][0] != wrap(expected[k])]
    differ_t = sum(1 for k in positions if k in dut and dut[k][0] != wrap(transposed[k]))
    diff_lines = [i for i, (a, c) in enumerate(zip(out_lines, ref_lines)) if a != c]
    diff_result_lines = [i for i in diff_lines if has_result(i)]
    print(f"== {os.path.basename(os.path.normpath(sim_dir))}")
    print(f"  words: DUT {len(out_lines)}, reference {len(ref_lines)}, identical {len(out_lines) - len(diff_lines)}; "
          f"with X {x_words}; non-zero bits above the psum slots {upper}; non-zero padding slots {pad_nonzero}")
    print(f"  differing lines: {len(diff_lines)} ({len(diff_lines) - len(diff_result_lines)} padding only, "
          f"{len(diff_result_lines)} also carry results: the result slots are checked below)")
    print(f"  coverage: {len(positions)} outputs, decoded {len(dut)}, missing {len(missing)}, duplicated {len(dupes)}")
    print(f"  DUT vs numpy: {len(positions) - len(missing) - len(differ)} equal, {len(differ)} differ "
          f"(transposed kernel: {differ_t} differ)")
    print(f"  testbench reference vs numpy: {int(np.sum(wrap(expected) != ref))} differ; "
          f"outside {bits} bit: {int(np.sum(np.abs(expected) >= 1 << (bits - 1)))}; "
          f"{len(np.unique(expected))} distinct values")
    for k in differ[:5]:
        print(f"    e.g. {k}: DUT {dut[k][0]}, numpy {int(expected[k])}")
    return not differ and not missing and not dupes and not x_words


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    ok = [check(d) for d in argv]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
