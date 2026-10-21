"""Bug #19 probe: wraps the unmodified OpenEye_FPGA_tb and dumps the Dense layer data the DUT receives
(fmap, weights, bias), the reference and the DUT outputs to B19_DUMP (pickle)."""
import os
import pickle

import cocotb

import OpenEye_FPGA_tb as tb

DUMP = {}


def _plain(v):
    try:
        return [_plain(e) for e in v]
    except TypeError:
        return int(v)


@cocotb.test()
async def probe_test(dut):
    orig_collect = tb.tum.collect_results
    orig_compare = tb.tum.compare_dram_with_ref

    def collect(layer_number, layer_params, dram, serial):
        res = orig_collect(layer_number, layer_params, dram, serial)
        if "Dense" in str(layer_params.layer_name):
            DUMP.update(fmap=_plain(dram.fmap[layer_number]), weights=_plain(dram.weights[layer_number]),
                        bias=_plain(dram.bias[layer_number]), ref=[int(res[f]) for f in sorted(res)])
        return res

    def compare(layer_params, ref_output, dram):
        if "Dense" in str(layer_params.layer_name):
            DUMP["dut"] = [int(v) for v in dram[:len(ref_output)]]
        return orig_compare(layer_params, ref_output, dram)

    tb.tum.collect_results = collect
    tb.tum.compare_dram_with_ref = compare
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        with open(os.environ["B19_DUMP"], "wb") as f:
            pickle.dump(DUMP, f)
