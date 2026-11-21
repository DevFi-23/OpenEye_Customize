"""pytest cases of doc/experiments/2026-11-20_act_wzero, part C: one layer of the Table 2 network on its own at a
controlled zero share of its weights (OPENEYE_WGHT_ZERO_FRACTION, with OPENEYE_WGHT_ZERO_DENSE=1 for the Dense layer)
and of its input activations (OPENEYE_IACT_ZERO_FRACTION), 0 / 20 / 40 / 60 / 80 % each, on sparse and dense hardware
(the mode is in the case name). CR 2 X 4 Y 3 (48 PE), DMA 64 bit, OPENEYE_SEED=1 (the same weights and input values in
every case; a larger share zeroes a superset of the positions), profiler on. In a whole network only the first layer's
input can be set this way: the inputs of the later layers are written back on chip. Run through run.py --grid."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402

# shape id: (LAYER, input width, input height, input channels, filters), as in the step 1 sweep (2026-11-18)
SHAPES = {
    "conv1": ("Convolution_Single", 28, 28, 1, 16),
    "conv2": ("Convolution_Single", 14, 14, 16, 32),
    "conv3": ("Convolution_Single", 7, 7, 32, 32),
    "fc":    ("DENSE_CHAIN_1568_32", 1568, 1, 1, 32),
}
ZEROS = ["0", "0.2", "0.4", "0.6", "0.8"]
MODES = {"sparse": "1", "dense": "0"}
CASES = {f"grid_{s}_w{w}_a{a}_{m}": (s, w, a, m) for s in SHAPES for m in MODES for w in ZEROS for a in ZEROS}
HOOKS = ["OPENEYE_ACTIVATION", "OPENEYE_WGHT_ZERO_PARITY", "OPENEYE_WGHT_LAYOUT", "OPENEYE_FORCE_RAW_WGHT",
         "OPENEYE_KEEP_GOING"]


@pytest.mark.parametrize("case", list(CASES))
def test_grid(case, request, monkeypatch):
    shape, wzero, azero, mode = CASES[case]
    layer, width, height, channels, filters = SHAPES[shape]
    for name in HOOKS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPARSITY_EN", MODES[mode])
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setenv("OPENEYE_WGHT_ZERO_FRACTION", wzero)
    monkeypatch.setenv("OPENEYE_WGHT_ZERO_DENSE", "1")
    monkeypatch.setenv("OPENEYE_IACT_ZERO_FRACTION", azero)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", 4)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", 3)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=1)
