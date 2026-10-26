# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Dense -> Dense on chip (bug #26).

The first Dense layer writes its quantized outputs back into the iact buffer (psum FSM SEND_PSUM_TO_IACT, main FSM
RECEIVE_PSUMS_TO_IACT) and the next Dense layer reads them from there. The testbench checks the buffer after every
layer except the last (the first N activations; the rest of the row is don't-care padding) and the final outputs.
Before the fix the write-back wrote nothing and the second layer read the first layer's input
(doc/experiments/2026-10-24_bug26_dense_writeback.md).

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_dense_chain.py
  venv/bin/python -m pytest -q "test/cocotb_fpga/test_dense_chain.py::test_dense_chain[mlp]"
"""
import pytest

import test_conv_const as conv

# case: (LAYER, layers, CLUSTER_ROWS, NUM_GLB_IACT, NUM_GLB_PSUM, QUANT_AMOUNT)
CHAINS = {
    "k16_n8_n10":        ("DENSE_CHAIN_16_8_10", 2, 2, 1, 4, 32),
    "k64_n10_n10":       ("DENSE_CHAIN_64_10_10", 2, 2, 1, 4, 32),     # 10 outputs: a partly filled buffer word
    "k256_n32_n10":      ("DENSE_CHAIN_256_32_10", 2, 2, 1, 4, 32),
    "k1568_n32_n10":     ("DENSE_CHAIN_1568_32_10", 2, 2, 1, 4, 32),   # the Dense pair of the paper's network
    "k16_n64_n10":       ("DENSE_CHAIN_16_64_10", 2, 2, 1, 4, 64),     # two psum transmissions, two buffer rows
    "mlp":               ("MLP", 3, 2, 1, 4, 32),                      # 6 -> 32 -> 16 -> 4, two junctions
    "k64_n8_n10_psum2":  ("DENSE_CHAIN_64_8_10", 2, 2, 1, 2, 32),      # WRITEBACK_WORDS = 2
    "k64_n8_n10_iact3":  ("DENSE_CHAIN_64_8_10", 2, 2, 3, 4, 32),
    "k64_n8_n10_cr1":    ("DENSE_CHAIN_64_8_10", 2, 1, 1, 4, 32),
    "k64_n32_n10_cr4":   ("DENSE_CHAIN_64_32_10", 2, 4, 1, 4, 32),
    "mlp_cr4":           ("MLP", 3, 4, 1, 4, 32),
}


@pytest.mark.parametrize("case", list(CHAINS))
def test_dense_chain(case, request, monkeypatch):
    layer, layers, cluster_rows, num_glb_iact, num_glb_psum, quant_amount = CHAINS[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", num_glb_psum)
    conv._run_conv_const(layer, 8, cluster_rows, num_glb_iact=num_glb_iact, input_channels=1, request=request,
                         input_height=1, quant_amount=quant_amount, dma_bitwidth=64, random_data=True,
                         expect_layers=layers)
