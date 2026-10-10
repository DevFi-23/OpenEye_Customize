#!/usr/bin/env python3
# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Check that the DUT received exactly the DMA stream the testbench generated.

Reads dma_in_trace.csv (written by rtl_test_utils.trace_dma_input when
OPENEYE_TRACE_DMA=1) and demo/layer_0_0/dma_stream_input.txt from one or
more simulation directories and reports, per directory:
  - how many words the DUT took and whether they equal the generated stream
    in content and order (first differing index otherwise),
  - how many words each load state took,
  - every main-FSM transition out of a load state with the values of
    enable_dma_i_reg, ready_dma_o and fsm_psum_cycle at the deciding edge
    (enable_reg=0 means the state was left in a cycle without a valid word).

Usage:
  python3 tools/check_dma_trace.py test/.temp/<sim dir> [more dirs ...]
"""

import os
import sys

STATES = {1: "GET_PARAMETERS", 2: "GET_ROUTER_CONFIG", 3: "GET_IACT", 4: "GET_WGHT",
          5: "GET_BIAS", 6: "GET_QUANTIZE", 7: "START_CONVERTER"}


def check(sim_dir, layer="layer_0_0"):
    ref_path = os.path.join(sim_dir, "demo", layer, "dma_stream_input.txt")
    with open(ref_path) as f:
        ref = [int(line) for line in f if line.strip()]
    words, transitions = [], []
    with open(os.path.join(sim_dir, "dma_in_trace.csv")) as f:
        for line in f:
            row = line.strip().split(",")
            if row[0] == "word":
                words.append((int(row[1]), int(row[2]), int(row[4])))
            elif row[0] == "state":
                transitions.append(row[1:])
    data = [w[2] for w in words]
    mismatch = next((i for i, (a, b) in enumerate(zip(data, ref)) if a != b), None)
    print(f"\n== {os.path.basename(os.path.normpath(sim_dir))}")
    print(f"generated {len(ref)} words, DUT took {len(data)}; "
          + ("same content and order" if mismatch is None else f"first difference at word {mismatch}")
          + ("" if len(data) == len(ref) else f" ({len(ref) - len(data):+d} not taken)"))
    counts = {}
    for _, state, _ in words:
        counts[state] = counts.get(state, 0) + 1
    print("words per state: " + ", ".join(f"{STATES.get(s, s)}={n}" for s, n in sorted(counts.items())))
    first_word_of = {}
    for index, (_, state, _) in enumerate(words):
        first_word_of.setdefault(state, index)
    for cycle, change, enable, ready, psum_cycle in transitions:
        old, new = (int(x) for x in change.split("->"))
        if old in STATES and old != 7:
            note = "" if enable == "1" else "   <-- left without a valid word"
            print(f"  {STATES[old]:17s} -> {STATES.get(new, new):17s} cycle {cycle}: enable_reg={enable} "
                  f"ready={ready} fsm_psum_cycle={psum_cycle}{note}")
    return mismatch is None and len(data) == len(ref)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    ok = all([check(d) for d in argv])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
