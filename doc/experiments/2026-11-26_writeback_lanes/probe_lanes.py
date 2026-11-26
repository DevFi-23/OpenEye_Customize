"""Write-back lane probe (cocotb module, run through run_lanes.py): the unmodified OpenEye_FPGA_tb plus a monitor. At
every rising clock edge where the write-back takes the activated quantizer outputs (trace wire act_capture of
OpenEye_FPGA.v, the profiler's activation_cycles), it records the value of every write-back lane (the bytes of
psum_pipeline_inst.quantized_value_flat), the psum FSM state / cycle, the cluster indices of the result sweep and the
main FSM's x position counter. After the run it stores the testbench reference of every layer output
(dram.fmap[layer + 1] after slo.batchnorm_output: the int8 values the write-back must produce, [filter][x][y]).
Output: lanes.json in the simulation directory. Observation only: no RTL and no testbench logic changed."""
import copy
import json

import cocotb
from cocotb.triggers import RisingEdge

import OpenEye_FPGA_tb as tb

REFS = {}
_batchnorm = tb.slo.batchnorm_output


def batchnorm_output(layer_params, a, layer_number, dram):
    result = _batchnorm(layer_params, a, layer_number, dram)
    REFS[layer_number] = copy.deepcopy([[[int(v) for v in col] for col in ch] for ch in dram.fmap[layer_number + 1]])
    return result


tb.slo.batchnorm_output = batchnorm_output


def _int(sig):
    try:
        return int(sig.value)
    except (ValueError, AttributeError):
        return None


async def monitor(dut, rows):
    pp = dut.psum_pipeline_inst
    layer = -1
    last_main = None
    cycle = 0
    while True:
        await RisingEdge(dut.clk_i)
        cycle += 1
        main = _int(dut.fsm_current_state)
        if main == 1 and last_main != 1:
            layer += 1
        last_main = main
        if _int(dut.UNPACKED_TRACES.act_capture) != 1:
            continue
        flat = _int(pp.quantized_value_flat)
        lanes = [None if flat is None else ((flat >> (8 * i)) & 0xFF) for i in range(8)]
        lanes = [None if v is None else (v - 256 if v > 127 else v) for v in lanes]
        rows.append({"cycle": cycle, "layer": layer, "lanes": lanes,
                     "psum_state": _int(pp.fsm_psum_current_state), "psum_cycle": _int(pp.fsm_psum_cycle),
                     "x_cl": _int(pp.fsm_x_cl_psum), "y_cl": _int(pp.fsm_y_cl_psum),
                     "main_cycle": _int(dut.fsm_cycle), "x_pos": _int(dut.iact_to_psum_x_pos_counter)})


@cocotb.test()
async def probe_test(dut):
    rows = []
    cocotb.start_soon(monitor(dut, rows))
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        with open("lanes.json", "w") as f:
            json.dump({"captures": rows, "refs": {str(k): v for k, v in REFS.items()}}, f)
