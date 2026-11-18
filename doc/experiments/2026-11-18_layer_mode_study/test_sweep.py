"""Step 1c of the per-layer mode plan (README_FI section 2): one layer at a controlled zero share of its input
activations (test hook OPENEYE_IACT_ZERO_FRACTION of DRAMContents), on sparse or dense hardware (SPARSITY_EN from the
environment), profiler on. Same weights and input values for every zero share (seed 1); the zeroed positions grow
with the share. Run through run_sweep.py."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402

# shape id: (LAYER, input width, input height, input channels, filters) - the layers of the Table 2 network
SHAPES = {
    "conv1": ("Convolution_Single", 28, 28, 1, 16),      # first layer, image input
    "conv2": ("Convolution_Single", 14, 14, 16, 32),
    "conv3": ("Convolution_Single", 7, 7, 32, 32),
    "fc":    ("DENSE_CHAIN_1568_32", 1568, 1, 1, 32),     # Dense 1568 -> 32
}
ZEROS = ["0", "0.25", "0.5", "0.75", "0.9"]
# (CLUSTER_ROWS, NUM_GLB_PSUM, NUM_GLB_WGHT)
CONFIGS = {"cr1x2": (1, 2, 3), "cr2x4": (2, 4, 3), "cr8x4": (8, 4, 3)}
CASES = {f"{s}_z{z}_{c}": (s, z, c) for s in SHAPES for c in CONFIGS for z in ZEROS}


@pytest.mark.parametrize("case", list(CASES))
def test_sweep(case, request, monkeypatch):
    shape, zero, config = CASES[case]
    layer, width, height, channels, filters = SHAPES[shape]
    rows, pes_x, pes_y = CONFIGS[config]
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_IACT_ZERO_FRACTION", zero)
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", pes_x)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", pes_y)
    conv._run_conv_const(layer, 8, rows, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=1)
