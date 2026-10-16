"""Bug #14 analysis: run one layer with psum_pipeline replaced by its Vivado netlist.

Usage: run_gate.py <case> [rtl]   (rtl = same run with the RTL psum_pipeline, for comparison)
The netlist was synthesized out of context with the generics of the fix67 hardware
(QUANT_AMOUNT=32, DMA_BITWIDTH=64), so only cases with that configuration are valid.
"""
import os
import sys
import types

REPO = "/home/truongphi/OpenEye_orig"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
os.chdir(os.path.join(REPO, "test", "cocotb_fpga"))

import cocotb_test.simulator  # noqa: E402
import test_conv_const as conv  # noqa: E402

# id: (width, height, channels, filters, random_data)
CASES = {
    "8x1_f4": (8, 1, 4, 4, False),
    "16x3_f4": (16, 3, 4, 4, False),
    "32x3_f4": (32, 3, 4, 4, False),
    "32x3_f16": (32, 3, 4, 16, False),
    "mnist1": (28, 28, 4, 32, False),
    "mnist2": (14, 14, 32, 32, False),
    "mnist3": (8, 8, 32, 32, False),
    "rand_8x4_c32_f32": (8, 4, 32, 32, True),
    "rand_14x14_c32_f32": (14, 14, 32, 32, True),
}

case = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else "gate"   # gate (Vivado netlist), yosys, rtl
use_rtl = mode in ("rtl", "probe")
width, height, channels, filters, random_data = CASES[case]

orig_run = cocotb_test.simulator.run


def gate_run(**kw):
    if mode == "probe":
        kw["module"] = "probe14"
        kw["testcase"] = "probe_test"
        kw["python_search"] = kw["python_search"] + [HERE]
        kw.setdefault("extra_env", {})["BUG14_PROBE_OUT"] = os.path.join(HERE, f"probe_{case}.json")
    elif not use_rtl:
        src = [s for s in kw["verilog_sources"]
               if os.path.basename(s) not in ("psum_pipeline.v", "quantization_unit.v")]
        assert len(src) == len(kw["verilog_sources"]) - 2
        if mode == "yosys":
            kw["verilog_sources"] = src + [os.path.join(HERE, "psum_pipeline_yosys.v"),
                                           "/home/truongphi/tools/yosys/share/yosys/simcells.v"]
        else:
            kw["verilog_sources"] = [os.path.join(HERE, "glbl.v")] + src + [os.path.join(HERE, "psum_pipeline_gate.v")]
            kw["compile_args"] = kw.get("compile_args", []) + ["-s", "glbl", "-y", os.path.join(HERE, "unisims")]
    return orig_run(**kw)


cocotb_test.simulator.run = gate_run
os.environ["OPENEYE_PROFILE"] = "1"
os.environ["OPENEYE_DUMP_VERIFY"] = "1"
conv.INPUT_SIZE_X = width
conv.NUM_FILTERS = filters
request = types.SimpleNamespace(node=types.SimpleNamespace(
    nodeid=f"bug14_{mode}_{case}"))
conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels,
                     request=request, input_height=height, ramp_iacts=not random_data,
                     asymmetric_kernel=not random_data, quant_amount=32, dma_bitwidth=64,
                     random_data=random_data)
print("DONE", case)
