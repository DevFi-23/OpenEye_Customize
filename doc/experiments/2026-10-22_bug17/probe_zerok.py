"""All-zero kernels in layer 0 (ZEROK_MODE): chan1 = channel 1 zero for every filter, chan1_f0 = only the kernel
(channel 1, filter 0), filter0 = filter 0 zero in every channel, none = control. Wraps the unmodified
OpenEye_FPGA_tb; the zeroing runs where channel_pad.fill_padding_channels runs (after all data hooks), so
the reference and the streams are built from the zeroed weights."""
import os

import cocotb

import OpenEye_FPGA_tb as tb
import open_eye.channel_pad as cp

_orig = cp.fill_padding_channels


def zero_kernels(model, dram):
    n = _orig(model, dram)
    w = dram.weights[0]                       # [c][f][ky][kx]
    mode = os.environ["ZEROK_MODE"]
    for c in range(len(w)):
        for f in range(len(w[c])):
            if (mode == "chan1" and c == 1) or (mode == "chan1_f0" and (c, f) == (1, 0)) or \
               (mode == "filter0" and f == 0):
                w[c][f] = [[0 for _ in row] for row in w[c][f]]
    tb.logger.info("probe_zerok: mode %s", mode)
    return n


@cocotb.test()
async def probe_test(dut):
    cp.fill_padding_channels = zero_kernels
    await tb.start_test_fpga.func(dut)
