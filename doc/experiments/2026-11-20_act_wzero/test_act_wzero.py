"""pytest cases of doc/experiments/2026-11-20_act_wzero (README_FI, Nhật ký 2026-11-20). Every case at CR 2 X 4 Y 3
(CLUSTER_ROWS 2, CLUSTER_COLUMNS 2, NUM_GLB_PSUM 4, NUM_GLB_WGHT 3, 48 PE), DMA 64 bit, profiler on, OPENEYE_SEED=1;
the hardware mode (SPARSITY_EN) is part of the case name. Run through run.py, not directly.

  act_<f>_<mode>       the Table 2 network (LAYER=PAPER_MNIST, random weights and input) with the activation f after
                       every Conv2D / Dense but the last: none, relu (PAPER_MNIST_RELU, fused ReLU), leaky
                       (Leaky ReLU, negative sums x 1 / 2^10), silu / hardswish (256-entry table, int8 scale 1/16 in
                       and out); leaky, silu and hardswish round to nearest as the trained models do
  wz_mnist_z<f>_<mode> the trained MNIST model (ReLU, test image 0) with exactly the share f of the weights of every
                       Conv2D and Dense layer set to 0 (OPENEYE_WGHT_ZERO_FRACTION, OPENEYE_WGHT_ZERO_DENSE=1)
  wz_t2_z<f>_<mode>    the same on the Table 2 network without activation"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402
import test_real_model as trm  # noqa: E402

ACTS = {
    "none": ("PAPER_MNIST", None),
    "relu": ("PAPER_MNIST_RELU", None),
    "leaky": ("PAPER_MNIST", "leaky:1:10:round"),
    "silu": ("PAPER_MNIST", "table:silu:0.0625:0.0625:round"),
    "hardswish": ("PAPER_MNIST", "table:hardswish:0.0625:0.0625:round"),
}
ZEROS = ["0", "0.2", "0.4", "0.6", "0.8"]
MODES = {"sparse": "1", "dense": "0"}
CASES = {}
for _mode in MODES:                      # the long trained-model runs first
    CASES.update({f"wz_mnist_z{z}_{_mode}": ("wz_mnist", z, _mode) for z in ZEROS})
for _mode in MODES:
    CASES.update({f"wz_t2_z{z}_{_mode}": ("wz_t2", z, _mode) for z in ZEROS})
    CASES.update({f"act_{a}_{_mode}": ("act", a, _mode) for a in ACTS})
HOOKS = ["OPENEYE_ACTIVATION", "OPENEYE_WGHT_ZERO_FRACTION", "OPENEYE_WGHT_ZERO_DENSE", "OPENEYE_WGHT_ZERO_PARITY",
         "OPENEYE_IACT_ZERO_FRACTION", "OPENEYE_WGHT_LAYOUT", "OPENEYE_FORCE_RAW_WGHT", "OPENEYE_KEEP_GOING"]


def _paper(layer, request):
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=1, request=request, input_height=28,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=7)


@pytest.mark.parametrize("case", list(CASES))
def test_act_wzero(case, request, monkeypatch):
    kind, arg, mode = CASES[case]
    for name in HOOKS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPARSITY_EN", MODES[mode])
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", 4)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", 3)
    if kind == "act":
        layer, spec = ACTS[arg]
        if spec:
            monkeypatch.setenv("OPENEYE_ACTIVATION", spec)
        _paper(layer, request)
        return
    monkeypatch.setenv("OPENEYE_WGHT_ZERO_FRACTION", arg)
    monkeypatch.setenv("OPENEYE_WGHT_ZERO_DENSE", "1")
    if kind == "wz_mnist":
        trm.run_trained(trm.CHECKPOINT, 0, request, monkeypatch)
    else:
        _paper("PAPER_MNIST", request)
