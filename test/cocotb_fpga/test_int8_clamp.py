# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""int8 saturation and fused ReLU of the quantized layer outputs, through the whole FPGA design.

The quantizers (quantization_unit.v) clamp a layer's outputs to [act_min, 127] before they are written back as the
next layer's input: act_min = -128 is plain int8 saturation, act_min = 0 a ReLU fused into the preceding Conv/Dense
(LayerParameters.act_min, status register quant_clamp_low). Before, the quantizers kept the low 8 bits, so a value
just outside the range came back with the opposite sign.

OPENEYE_QUANT_SHIFT sets a small shift so that many outputs leave the int8 range (data_create); a "_RELU" model gets
activation='relu' on every Conv/Dense but the last. The testbench reference saturates the same way and checks the
iact buffer after every layer and the final outputs.

Usage (from the repository root):
  venv/bin/python -m pytest -q test/cocotb_fpga/test_int8_clamp.py
"""
import pytest

import test_conv_const as conv

# case: (LAYER, layers, input width, height, channels, filters, quant shift or None, NUM_GLB_PSUM, max pooling)
CASES = {
    "sat_conv_stack":           ("Convolution_Stack", 2, 8, 4, 4, 4, 2, 4, False),
    "relu_conv_stack":          ("Convolution_Stack_RELU", 2, 8, 4, 4, 4, None, 4, False),
    "relu_sat_conv_stack":      ("Convolution_Stack_RELU", 2, 8, 4, 4, 4, 2, 4, False),
    "relu_sat_conv_stack_c16":  ("Convolution_Stack_RELU", 2, 8, 8, 16, 16, 3, 4, False),
    "relu_sat_conv_pool_conv":  ("Conv_Pool_Conv_RELU", 3, 8, 4, 2, 8, 3, 4, True),
    "relu_sat_dense_chain":     ("DENSE_CHAIN_64_32_10_RELU", 2, 8, 1, 1, 4, 4, 4, False),
    "relu_mlp":                 ("MLP_RELU", 3, 8, 1, 1, 4, None, 4, False),
    "sat_conv_stack_psum2":     ("Convolution_Stack", 2, 8, 4, 4, 4, 2, 2, False),
    "relu_paper_network":       ("PAPER_MNIST_RELU", 7, 28, 28, 1, 16, None, 4, True),
}


@pytest.mark.parametrize("case", list(CASES))
def test_int8_clamp(case, request, monkeypatch):
    layer, layers, width, height, channels, filters, shift, glb_psum, max_pooling = CASES[case]
    monkeypatch.setenv("OPENEYE_SEED", "1")
    if shift is not None:
        monkeypatch.setenv("OPENEYE_QUANT_SHIFT", str(shift))
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
                         input_height=height, quant_amount=32, dma_bitwidth=64, random_data=True,
                         expect_layers=layers)
