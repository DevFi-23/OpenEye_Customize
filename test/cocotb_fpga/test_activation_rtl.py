# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Activation functions in the RTL through the whole FPGA design (step B of doc/experiments/2026-11-02_activation_plan.md,
design doc/experiments/2026-11-02_activation_rtl_design.md).

The quantizers of the write-back compute the activation of the layer: Leaky ReLU as a second [mant, shift] for
negative sums (status registers act_mode 1, act_neg_mant, act_neg_shift), a 256-entry int8 table after the clamp
(act_mode 2, loaded in the main FSM state GET_ACTIVATION from the words after the quantization words, or kept from
the previous layer with act_keep_table), rounding half up instead of the floor (act_round). The test hook
OPENEYE_ACTIVATION (data_create.set_test_activation) sets them on every Conv/Dense but the last of a random model; the
testbench reference (simple_layer_operations.batchnorm_output) computes the same and the iact buffer is checked after
every layer, so a wrong slope, rounding, table entry or table address fails the run.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_activation_rtl.py
"""
import pytest

import test_conv_const as conv

# case: (LAYER, layers, input width, height, channels, filters, OPENEYE_ACTIVATION, NUM_GLB_PSUM, max pooling,
#        DMA width)
CASES = {
    "leaky_conv_stack":         ("Convolution_Stack", 2, 8, 4, 4, 4, "leaky:1:10", 4, False, 64),
    "leaky_round_conv_stack":   ("Convolution_Stack", 2, 8, 4, 4, 4, "leaky:3:11:round", 4, False, 64),
    "leaky_dense_chain":        ("DENSE_CHAIN_64_32_10", 2, 8, 1, 1, 4, "leaky:1:10:round", 4, False, 64),
    "round_relu_conv_stack":    ("Convolution_Stack_RELU", 2, 8, 4, 4, 4, "round", 4, False, 64),
    "table_conv_stack":         ("Convolution_Stack", 2, 8, 4, 4, 4, "table:random", 4, False, 64),
    "table_round_conv_stack":   ("Convolution_Stack", 2, 8, 4, 4, 4, "table:random:round", 4, False, 64),
    "table_conv_pool_conv":     ("Conv_Pool_Conv", 3, 8, 4, 2, 8, "table:silu:0.0625:0.0625:round", 4, True, 64),
    "table_conv_stack_psum2":   ("Convolution_Stack", 2, 8, 4, 4, 4, "table:random", 2, False, 64),
    "table_conv_stack_dma32":   ("Convolution_Stack", 2, 8, 4, 4, 4, "table:random:round", 4, False, 32),
    "table_keep_mlp":           ("MLP", 3, 8, 1, 1, 4, "table:random:keep", 4, False, 64),
    "table_dense_chain":        ("DENSE_CHAIN_64_32_10", 2, 8, 1, 1, 4, "table:hardswish:0.05:0.04", 4, False, 64),
    "table_paper_network":      ("PAPER_MNIST", 7, 28, 28, 1, 16, "table:silu:0.0625:0.0625:round", 4, True, 64),
}


@pytest.mark.parametrize("case", list(CASES))
def test_activation_rtl(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, activation, glb_psum, max_pooling, dma = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    monkeypatch.setenv("OPENEYE_ACTIVATION", activation)
    monkeypatch.setattr(conv, "NUM_GLB_PSUM", glb_psum)
    monkeypatch.setattr(conv, "INPUT_SIZE_X", width)
    monkeypatch.setattr(conv, "NUM_FILTERS", filters)
    if max_pooling:
        real_run = conv.cocotb_test.simulator.run

        def run(**kw):
            # as test_pooling.py: max pooling, decoded outputs checked instead of the raw DMA file
            kw["extra_env"] = dict(kw["extra_env"], LOGGER_LEVEL="20")
            kw["parameters"] = {"MAX_POOLING": 1, "AVERAGE_POOLING": 0}
            return real_run(**kw)
        monkeypatch.setattr(conv.cocotb_test.simulator, "run", run)
    conv._run_conv_const(layer, 8, 2, num_glb_iact=1, input_channels=channels, request=request,
                         input_height=height, quant_amount=32, dma_bitwidth=dma, random_data=True,
                         expect_layers=layers)
