"""Step 2 of the per-layer weight format P1 (README_FI section 2): the sparse FSM with conv weights in the dense
layout (every weight an entry with overhead 0, zero weights included) on today's RTL, without an RTL change.
One layer of the Table 2 network (as in step 1c), on sparse hardware, profiler on, at a controlled zero share of the
input activations (OPENEYE_IACT_ZERO_FRACTION) and of the weights (OPENEYE_WGHT_ZERO_FRACTION). Layouts:
  csc          today's zero-compressed columns (zero weights skipped)
  dense        OPENEYE_WGHT_LAYOUT=dense + OPENEYE_FORCE_RAW_WGHT=1 (raw_wght_i held at 1 in simulation, as P1 would set
               it), so two zero weights in one word (an all-zero word) are kept
controls (conv2, CR 2 X 4, 50 % input zeros, 25 % weight zeros):
  cscraw       csc with raw_wght_i forced: must equal csc (raw mode only changes all-zero words)
  cscpar       csc, zeros only where c + f + y + x is even (OPENEYE_WGHT_ZERO_PARITY=1: no two neighbouring filters zero)
  densepar     dense layout of the cscpar weights without the force: no all-zero word, so today's RTL as it is
  denseparraw  the same with the force: must equal densepar
  densebad     dense layout with all-zero words and without the force (OPENEYE_WGHT_LAYOUT=dense_nocheck): expected to
               fail (data_pipeline_wght drops the words, #47)
Run through run_step2.py."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402

SHAPES = {
    "conv1": ("Convolution_Single", 28, 28, 1, 16),
    "conv2": ("Convolution_Single", 14, 14, 16, 32),
    "conv3": ("Convolution_Single", 7, 7, 32, 32),
}
CONFIGS = {"cr1x2": (1, 2, 3), "cr2x4": (2, 4, 3), "cr8x4": (8, 4, 3)}
IACT_ZEROS = ["0", "0.5"]
WGHT_ZEROS = ["0", "0.05", "0.25", "0.5"]
LAYOUTS = {
    "csc": {},
    "dense": {"OPENEYE_WGHT_LAYOUT": "dense", "OPENEYE_FORCE_RAW_WGHT": "1"},
    "cscraw": {"OPENEYE_FORCE_RAW_WGHT": "1"},
    "cscpar": {"OPENEYE_WGHT_ZERO_PARITY": "1"},
    "densepar": {"OPENEYE_WGHT_ZERO_PARITY": "1", "OPENEYE_WGHT_LAYOUT": "dense"},
    "denseparraw": {"OPENEYE_WGHT_ZERO_PARITY": "1", "OPENEYE_WGHT_LAYOUT": "dense", "OPENEYE_FORCE_RAW_WGHT": "1"},
    "densebad": {"OPENEYE_WGHT_LAYOUT": "dense_nocheck"},
}
CASES = {}
for s in SHAPES:
    for c in CONFIGS:
        for i in IACT_ZEROS:
            for w in WGHT_ZEROS:
                CASES[f"{s}_i{i}_w{w}_csc_{c}"] = (s, i, w, "csc", c)
                if w != "0" or i == "0":            # weight zeros 0: both layouts are the same stream (one check)
                    CASES[f"{s}_i{i}_w{w}_dense_{c}"] = (s, i, w, "dense", c)
for layout in ("cscraw", "cscpar", "densepar", "denseparraw", "densebad"):
    CASES[f"conv2_i0.5_w0.25_{layout}_cr2x4"] = ("conv2", "0.5", "0.25", layout, "cr2x4")


@pytest.mark.parametrize("case", list(CASES))
def test_step2(case, request, monkeypatch):
    shape, iact_zero, wght_zero, layout, config = CASES[case]
    layer, width, height, channels, filters = SHAPES[shape]
    rows, pes_x, pes_y = CONFIGS[config]
    for key in ("OPENEYE_WGHT_LAYOUT", "OPENEYE_FORCE_RAW_WGHT", "OPENEYE_WGHT_ZERO_PARITY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENEYE_PROFILE", "1")
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_IACT_ZERO_FRACTION", iact_zero)
    monkeypatch.setenv("OPENEYE_WGHT_ZERO_FRACTION", wght_zero)
    monkeypatch.setenv("OPENEYE_FAIL_ON_STALL", "400000")
    for key, value in LAYOUTS[layout].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", pes_x)
    monkeypatch.setattr(conv, "NUM_GLB_WGHT", pes_y)
    conv._run_conv_const(layer, 8, rows, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=32, dma_bitwidth=64, random_data=True, expect_layers=1)
