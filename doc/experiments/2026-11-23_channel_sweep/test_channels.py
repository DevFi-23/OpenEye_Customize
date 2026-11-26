"""pytest cases of doc/experiments/2026-11-23_channel_sweep: which channel counts the toolchain + RTL compute right.
Random weights and input (OPENEYE_SEED=1), CR 2 (2 x 2 clusters), NUM_GLB_PSUM 4, NUM_GLB_WGHT 3, 3 x 3 kernels, DMA 64
bit; the hardware mode is in the case name. Every case checks the RTL output (and the iact buffer between layers)
against the testbench reference. Run through run_channels.py.

  first_c<C>_<mode>  Conv 16 x 4 x C -> 8, one layer: C input channels from DRAM (layer 0; odd C > 1 is padded by
                     channel_pad since 2026-11-22)
  mid_f<F>_<mode>    Conv 16 x 4 x 4 -> F, Conv F -> F: the second layer reads F channels written back on chip
  dense_f<F>_<mode>  Conv 8 x 4 x 4 -> F, flatten, Dense 32 F -> 10: the Dense input holds F channels per pixel
  last_f<F>_<mode>   Conv 16 x 4 x 4 -> F, one layer (added after the first run): F filters without a write-back, to
                     tell a filter-count problem from a channel-count one"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402

MODES = {"sparse": "1", "dense": "0"}
CASES = {}
for _m in MODES:
    CASES.update({f"first_c{c}_{_m}": ("first", c, _m) for c in range(1, 35)})
    CASES.update({f"mid_f{f}_{_m}": ("mid", f, _m) for f in range(1, 21)})
    CASES.update({f"dense_f{f}_{_m}": ("dense", f, _m) for f in range(1, 19)})
    CASES.update({f"last_f{f}_{_m}": ("last", f, _m) for f in range(1, 13)})
HOOKS = ["OPENEYE_ACTIVATION", "OPENEYE_WGHT_ZERO_FRACTION", "OPENEYE_WGHT_ZERO_DENSE", "OPENEYE_IACT_ZERO_FRACTION",
         "OPENEYE_WGHT_LAYOUT", "OPENEYE_FORCE_RAW_WGHT", "OPENEYE_KEEP_GOING", "OPENEYE_ALLOW_UNSUPPORTED",
         "OPENEYE_PAD_CHANNELS"]


@pytest.mark.parametrize("case", list(CASES))
def test_channels(case, request, monkeypatch):
    kind, n, mode = CASES[case]
    for name in HOOKS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPARSITY_EN", MODES[mode])
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "200000")
    monkeypatch.setenv("OUTPUT_SIZE", "10")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", 4)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", 3)
    if kind == "first":
        layer, width, height, channels, filters, layers = "Convolution_Single", 16, 4, n, 8, 1
    elif kind == "last":
        layer, width, height, channels, filters, layers = "Convolution_Single", 16, 4, 4, n, 1
    elif kind == "mid":
        layer, width, height, channels, filters, layers = "Convolution_Stack", 16, 4, 4, n, 2
    else:
        layer, width, height, channels, filters, layers = "Conv_Dense", 8, 4, 4, n, 2
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request, input_height=height,
                         quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=layers)
