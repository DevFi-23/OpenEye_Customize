"""Rounding probe (cocotb module, run through run_round.py): the unmodified OpenEye_FPGA_tb with the rounding of every
activation forced by the environment, for the trained models of test_real_model.

P_ROUND=0 / 1: after onnx2model.finish_activations, every layer with an activation (relu, leaky_relu, silu, hardswish)
gets activation_round = P_ROUND. LayerParameters.activation_config reads it, so the testbench reference and the RTL
(status field act_round) use the same rounding; the toolchain and the RTL are not modified."""
import os

import cocotb
import OpenEye_FPGA_tb as tb
from open_eye import onnx2model as o2m

_finish = o2m.finish_activations


def finish_activations(pipeline):
    pipeline = _finish(pipeline)
    rounding = os.environ.get("P_ROUND")
    if rounding in ("0", "1"):
        changed = []
        for layer in pipeline:
            if getattr(layer, "activation", None) in ("relu", "leaky_relu", "silu", "hardswish"):
                layer.activation_round = rounding == "1"
                changed.append(getattr(layer, "activation", None))
        tb.logger.info("P_ROUND=%s: activation_round forced on %d layers %s", rounding, len(changed), changed)
    return pipeline


o2m.finish_activations = finish_activations


@cocotb.test()
async def probe_test(dut):
    await tb.start_test_fpga.func(dut)
