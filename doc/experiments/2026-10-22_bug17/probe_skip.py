"""Bug #22 probe. SKIP_WORDS=0 turns off WghtStreamMapper.SKIP_ZERO_WORDS (dropping all-zero packed weight words);
PAD_WEIGHT_ZERO=1 gives the padding channel zero weights; ZERO_FRAC=p zeroes that fraction of all layer-0 weights
(seeded), like a real int8 model with small or pruned weights. Wraps the unmodified OpenEye_FPGA_tb."""
import os
import random

import cocotb

import OpenEye_FPGA_tb as tb
import open_eye.channel_pad as cp
import open_eye.wght_stream_mapper as wsm

_orig = cp.fill_padding_channels


def fill(model, dram):
    n = _orig(model, dram)
    w = dram.weights[0]                       # [c][f][ky][kx]
    if n and os.environ.get("PAD_WEIGHT_ZERO") == "1":
        for c in range(len(w) - n, len(w)):
            w[c] = [[[0 for _ in row] for row in k] for k in w[c]]
    frac = float(os.environ.get("ZERO_FRAC", "0"))
    rng = random.Random(7)
    zeros = 0
    for c in range(len(w)):
        for f in range(len(w[c])):
            for row in w[c][f]:
                for x in range(len(row)):
                    if rng.random() < frac:
                        row[x] = 0
                        zeros += 1
    tb.logger.info("probe_skip: SKIP_ZERO_WORDS=%s, pad weight zero %s, %d weights zeroed",
                   wsm.WghtStreamMapper.SKIP_ZERO_WORDS, os.environ.get("PAD_WEIGHT_ZERO"), zeros)
    return n


@cocotb.test()
async def probe_test(dut):
    if os.environ.get("SKIP_WORDS") == "0":
        wsm.WghtStreamMapper.SKIP_ZERO_WORDS = False
    cp.fill_padding_channels = fill
    await tb.start_test_fpga.func(dut)
