"""pytest cases of doc/experiments/2026-11-17_paper_dense_sparse: the Table 2 network of the OpenEye paper with a fused
ReLU after every Conv2D / Dense but the last (LAYER=PAPER_MNIST_RELU of data_create.py) on the 16 configurations of
test_profile.py::test_profile_paper, everything else as there (random weights with real zeros, random non-sparse input
image, CLUSTER_COLUMNS 2, DMA 64, QUANT_AMOUNT 32, OPENEYE_SEED=1, profiler on, OPENEYE_KEEP_GOING).

The Table 3 runs have no activation function, so no layer input has zeros and the sparse datapath can skip nothing. With
the ReLU, the inputs of Conv2, Conv3 and the two Dense layers are about half zeros, as after a ReLU in a real network.
The layer is chosen by P_LAYER (default PAPER_MNIST_RELU); the hardware mode by SPARSITY_EN in the environment.
Run through run_relu.py, not directly."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402
from test_profile import PAPER_CONFIGS  # noqa: E402


@pytest.mark.parametrize("case", list(PAPER_CONFIGS))
def test_paper_relu(case, request, monkeypatch):
    cluster_rows, pes_x, pes_y = PAPER_CONFIGS[case]
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setenv("OPENEYE_KEEP_GOING", "1")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", pes_x)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", pes_y)
    conv._run_conv_const(os.environ.get("P_LAYER", "PAPER_MNIST_RELU"), 8, cluster_rows, num_glb_iact=1,
                         input_channels=1, request=request, input_height=28, quant_amount=32, dma_bitwidth=64,
                         random_data=True, expect_layers=7)
