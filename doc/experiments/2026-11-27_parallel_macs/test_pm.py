"""pytest cases of doc/experiments/2026-11-27_parallel_macs: one layer of the Table 2 network on its own with
PARALLEL_MACS = 1 or 2 (MACs per PE per clock, weights per SPad word), at a controlled share of zero weights
(OPENEYE_WGHT_ZERO_FRACTION) and zero inputs (OPENEYE_IACT_ZERO_FRACTION), sparse and dense, CR 2 X 4 Y 3, OPENEYE_SEED=1,
profiler on. The values do not change with PARALLEL_MACS, only how many weights a PE takes per clock. Run through
run_pm.py (the runner of 2026-11-23_channel_sweep with this file)."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, *[os.pardir] * 3))
sys.path.insert(0, os.path.join(REPO, "test", "cocotb_fpga"))
import test_conv_const as conv  # noqa: E402

SHAPES = {
    "conv2": ("Convolution_Single", 14, 14, 16, 32),
    "conv3": ("Convolution_Single", 7, 7, 32, 32),
    "fc":    ("DENSE_CHAIN_1568_32", 1568, 1, 1, 32),
}
ZEROS = ["0", "0.2", "0.4", "0.6", "0.8"]
MODES = {"sparse": "1", "dense": "0"}
CASES = {}
for _s in SHAPES:
    for _pm in (1, 2):
        for _m in MODES:
            for _w in ZEROS:
                for _a in ("0", "0.5"):
                    CASES[f"pm{_pm}_{_s}_w{_w}_a{_a}_{_m}"] = (_s, _pm, _w, _a, _m)


@pytest.mark.parametrize("case", list(CASES))
def test_pm(case, request, monkeypatch):
    shape, pm, wzero, azero, mode = CASES[case]
    layer, width, height, channels, filters = SHAPES[shape]
    for name in ("OPENEYE_ACTIVATION", "OPENEYE_WGHT_ZERO_PARITY", "OPENEYE_WGHT_LAYOUT", "OPENEYE_FORCE_RAW_WGHT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPARSITY_EN", MODES[mode])
    monkeypatch.setenv("PARALLEL_MACS", str(pm))
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
