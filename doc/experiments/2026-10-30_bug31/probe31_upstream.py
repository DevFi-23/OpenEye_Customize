"""Bug #31 check on upstream's code (cocotb module, run through run31_upstream.py inside a worktree of upstream/main).

Upstream's testbench keeps the DRAM as dicts keyed by layer name and always applies OPENEYE_CONST_IACTS /
OPENEYE_CONST_WGHTS. B31_IACT=<file.npy> ([C][X][Y]) replaces the first layer's input right before the testbench
computes that layer's reference (test_utils_main.collect_results), so the reference and the DMA stream both use it.
Upstream's files are not modified."""
import os

import cocotb
import numpy as np

import OpenEye_FPGA_tb as tb

_orig_collect = tb.tum.collect_results
_done = []


def collect_results(layer_params, dram, serial, *args, **kw):
    path = os.environ.get("B31_IACT")
    if path and not _done:
        _done.append(1)
        a = np.load(path)
        name = next(iter(dram.fmap))              # the first layer's input (DRAMContents fills the dict in order)
        assert np.array(dram.fmap[name]).shape == a.shape, "B31_IACT shape %s vs %s" % (
            np.array(dram.fmap[name]).shape, a.shape)
        dram.fmap[name] = a.tolist()
        tb.logger.info("B31_IACT: input of %s from %s (%d of %d values zero)", name, os.path.basename(path),
                       int((a == 0).sum()), a.size)
    return _orig_collect(layer_params, dram, serial, *args, **kw)


@cocotb.test()
async def probe_test(dut):
    tb.tum.collect_results = collect_results
    await tb.start_test_fpga.func(dut)
