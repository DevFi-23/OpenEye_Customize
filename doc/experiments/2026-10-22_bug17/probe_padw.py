"""Pad-weight variant: the padding channel keeps the +-1 weights DRAMContents put there (its activations stay 0).
Wraps the unmodified OpenEye_FPGA_tb; only open_eye.channel_pad.zero_padded_channels is replaced."""
import copy

import cocotb

import OpenEye_FPGA_tb as tb
import open_eye.channel_pad as cp

_orig = cp.zero_padded_channels


def zero_iacts_only(model, dram):
    saved = copy.deepcopy(dram.weights[0])
    n = _orig(model, dram)
    dram.weights[0] = saved
    tb.logger.info("probe_padw: padding channel keeps its nonzero weights")
    return n


@cocotb.test()
async def probe_test(dut):
    cp.zero_padded_channels = zero_iacts_only
    await tb.start_test_fpga.func(dut)
