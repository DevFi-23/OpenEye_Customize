# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Convolutions on the dense hardware (SPARSITY_EN=0): bugs #46, #47 and the Python side of the dense weight stream.

The fork runs sparse; the dense mode (upstream's development configuration) had never run on it and every case failed
(doc/experiments/2026-11-09_dense_vs_sparse.md). Fixed 2026-11-10 (doc/experiments/2026-11-10_bug46_47.md):
  Python  the conv weight stream of dense hardware keeps every weight in its slot (no bug #22 column encoding) and keeps
          all-zero words (wght_stream_mapper.py);
  #47     data_pipeline_wght.v dropped an all-zero weight word outside raw mode and restarted the SPad write address, so
          the rest of the block overwrote its start and the PE read activations it never got (X). The 16-channel case
          below has such a word with seed 1; the trained MNIST net has many;
  #46     the dense FSM of PE.v did not forward the adder output when a psum address recurs within the two-cycle write
          pipeline (4 or fewer filters per PE) and never reset the psum address with 2 or fewer filters per PE.
An odd number of filters per PE is refused on dense hardware (bug #48, check_dense_wght_slots).

The data are those of the investigation (random, seed 1, QUANT_AMOUNT 1024, CR 2 x CC 2), so the zero weight word of
the 16-channel case is the one that was traced.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_dense_mode.py
"""
import pytest

import test_conv_const as conv
import test_real_model

# id: (LAYER, layers, input width, input height, input channels, filters, NUM_GLB_PSUM)
CASES = {
    "single_c4_f2":        ("Convolution_Single", 1, 8, 4, 4, 2, 4),     # 2 filters per PE: psum address reset (#46)
    "single_c4_f4":        ("Convolution_Single", 1, 8, 4, 4, 4, 4),     # 4 filters per PE: psum forwarding (#46)
    "single_c8_f8":        ("Convolution_Single", 1, 8, 4, 8, 8, 4),     # 4 filters per PE (#46)
    "single_c4_f16":       ("Convolution_Single", 1, 8, 4, 4, 16, 4),    # 8 filters per PE, was right
    "single_c16_f16":      ("Convolution_Single", 1, 8, 4, 16, 16, 4),   # an all-zero weight word (#47)
    "stack_c4_f4":         ("Convolution_Stack", 2, 8, 4, 4, 4, 4),      # write-back for the next layer
    "stack_c4_f4_glbp2":   ("Convolution_Stack", 2, 8, 4, 4, 4, 2),
    "conv_pool_conv_c2_f8": ("Conv_Pool_Conv", 3, 8, 4, 2, 8, 4),
    "stack_c4_f16":        ("Convolution_Stack", 2, 8, 4, 4, 16, 4),
}


@pytest.mark.parametrize("case", list(CASES))
def test_dense(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, glb_psum = CASES[case]
    monkeypatch.setenv("SPARSITY_EN", "0")             # parameters_*.vh and OpenEyeParameters of the testbench
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.delenv("OPENEYE_ALLOW_UNSUPPORTED", raising=False)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request, input_height=height,
                         random_data=True, expect_layers=layers)


def test_dense_trained_mnist(request, monkeypatch):
    """The trained MNIST net, image 0, on dense hardware: every buffer check and the Dense psums bit-exact (Conv2, Conv3
    and Dense were wrong before #47 was fixed), 225,221 cycles against 218,564 sparse."""
    monkeypatch.setenv("SPARSITY_EN", "0")
    test_real_model.run_trained(test_real_model.CHECKPOINT, 0, request, monkeypatch)
