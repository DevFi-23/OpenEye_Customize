"""pytest cases of doc/experiments/2026-11-27_channels_zero_skip: does zero skipping work better with more input
channels? One convolution on its own, 14 x 14 x C -> 32, 3 x 3, only C changes (1, 2, 4, 8, 16, 32, 64; 3 and the counts
of bug #45 left out), CR 2 X 4 Y 3, OPENEYE_SEED=1, profiler on; input zero share 0 / 40 / 80 % (OPENEYE_IACT_ZERO_FRACTION,
weights without zeros) on sparse hardware, and 0 % on dense hardware (dense compute does not depend on zeros)."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402

CHANNELS = [1, 2, 4, 8, 16, 32, 64]
CASES = {}
for _c in CHANNELS:
    for _a in ("0", "0.4", "0.8"):
        CASES[f"c{_c}_a{_a}_sparse"] = (_c, _a, "1")
    CASES[f"c{_c}_a0_dense"] = (_c, "0", "0")


@pytest.mark.parametrize("case", list(CASES))
def test_chz(case, request, monkeypatch):
    channels, azero, sparse = CASES[case]
    for name in ("OPENEYE_ACTIVATION", "OPENEYE_WGHT_ZERO_FRACTION", "OPENEYE_WGHT_LAYOUT", "OPENEYE_FORCE_RAW_WGHT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPARSITY_EN", sparse)
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    monkeypatch.setenv("OPENEYE_IACT_ZERO_FRACTION", azero)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", 14)
    monkeypatch.setattr(conv, "NUM_FILTERS", 32)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", 4)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", 3)
    conv._run_conv_const("Convolution_Single", 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=14, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=1)
