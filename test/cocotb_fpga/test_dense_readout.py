# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""A last Dense layer with more than one psum pass (bug #21, fixed in the testbench 2026-11-21).

One psum pass holds 16 x Clusters_X outputs (32 at 2 cluster columns). A layer with more sends its passes one after
another (pass r, buffer address a, cluster column c). The RTL always did this right; the testbench decoder
compare_stream_Dense placed every pass after the first wrong (Dense 64 -> 40: 30 of 40 outputs "wrong"), and from
2026-11-07 to 2026-11-21 the toolchain refused such layers (check_dense_readout). Each case checks the final outputs
against the integer reference; the chains also check the on-chip write-back (bug #26) of the first layer.
doc/experiments/2026-11-21_test_dense_output.md.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_dense_readout.py
  venv/bin/python -m pytest -q "test/cocotb_fpga/test_dense_readout.py::test_dense_readout[k64_n40]"
"""
import pytest

import test_conv_const as conv
import test_gemm_layer as gemm

# case: (LAYER, layers, CLUSTER_ROWS, NUM_GLB_IACT, NUM_GLB_PSUM, QUANT_AMOUNT, SPARSITY_EN); 2 cluster columns
CASES = {
    "k64_n40":          ("DENSE_CHAIN_64_40", 1, 2, 1, 4, 64, 1),        # the recorded #21 case: 2 passes, P 10
    "k64_n34":          ("DENSE_CHAIN_64_34", 1, 2, 1, 4, 64, 1),        # 6 padding slots at the end of pass 1
    "k16_n64":          ("DENSE_CHAIN_16_64", 1, 2, 1, 4, 64, 1),        # 2 full passes, P 16
    "k64_n100":         ("DENSE_CHAIN_64_100", 1, 2, 1, 4, 128, 1),      # 4 passes, P 14
    "k1568_n40":        ("DENSE_CHAIN_1568_40", 1, 2, 1, 4, 64, 1),      # K of the paper's Dense layer
    "k64_n40_cr1":      ("DENSE_CHAIN_64_40", 1, 1, 1, 4, 64, 1),
    "k64_n40_cr4":      ("DENSE_CHAIN_64_40", 1, 4, 1, 4, 64, 1),
    "k64_n40_iact3":    ("DENSE_CHAIN_64_40", 1, 2, 3, 4, 64, 1),
    "k64_n40_psum2":    ("DENSE_CHAIN_64_40", 1, 2, 1, 2, 64, 1),
    "k64_n40_dense":    ("DENSE_CHAIN_64_40", 1, 2, 1, 4, 64, 0),        # dense hardware
    "k64_n32_n40":      ("DENSE_CHAIN_64_32_40", 2, 2, 1, 4, 64, 1),     # write-back, then a 2-pass read-out
    "k64_n64_n40":      ("DENSE_CHAIN_64_64_40", 2, 2, 1, 4, 64, 1),     # 2-pass write-back and 2-pass read-out
}


@pytest.mark.parametrize("case", list(CASES))
def test_dense_readout(case, request, monkeypatch):
    layer, layers, cluster_rows, num_glb_iact, num_glb_psum, quant_amount, sparsity = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("SPARSITY_EN", str(sparsity))
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", num_glb_psum)
    conv._run_conv_const(layer, 8, cluster_rows, num_glb_iact=num_glb_iact, input_channels=1, request=request,
                         input_height=1, quant_amount=quant_amount, dma_bitwidth=64, random_data=True,
                         expect_layers=layers)


# test_gemm_layer: other cluster column counts, one MAC lane, the output-stationary dataflow (QUANT_AMOUNT 1024)
GEMM = {
    "cx1_k64_n40":      dict(CLUSTER_COLUMNS=1, PARALLEL_MACS=2, DATAFLOW="row_stationary"),     # 3 passes, P 14
    "pm1_k64_n40":      dict(CLUSTER_COLUMNS=2, PARALLEL_MACS=1, DATAFLOW="row_stationary"),
    "os_k64_n40":       dict(CLUSTER_COLUMNS=2, PARALLEL_MACS=2, DATAFLOW="output_stationary"),
}


@pytest.mark.parametrize("case", list(GEMM))
def test_dense_readout_gemm(case, request, monkeypatch):
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_LAYER_SEED", "1")
    monkeypatch.setenv("OPENEYE_SKIP_FC_WRITE_CHECK", "1")    # bug #5: false alarm of the live FC write checker
    gemm.test_gemm_layer(INPUT_SIZE=64, OUTPUT_SIZE=40, CLUSTER_ROWS=2, NUM_GLB_IACT=1, NUM_GLB_PSUM=4,
                         NUM_GLB_WGHT=3, request=request, **GEMM[case])
