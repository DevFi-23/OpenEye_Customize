# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""int8 saturation of the quantized outputs and the fused ReLU bound, on the Python side.

quantization_unit.v clamps to [act_min, 127]; LayerParameters.act_min comes from the layer (-128, or 0 after a ReLU),
the mappers send it as the status register quant_clamp_low (act_min + 128) and the reference
(simple_layer_operations.batchnorm_output) saturates the same way.
"""
import os
import types

import pytest

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
import tensorflow as tf  # noqa: E402

from open_eye import generator  # noqa: E402
from open_eye import simple_layer_operations as slo  # noqa: E402
from open_eye.layer_parameters import activation_min  # noqa: E402

REGMAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cocotb_fpga")


@pytest.mark.parametrize("layer,expected", [
    (tf.keras.layers.Conv2D(4, (3, 3), activation="relu"), 0),
    (tf.keras.layers.Conv2D(4, (3, 3)), -128),
    (tf.keras.layers.Dense(8, activation="relu"), 0),
    (tf.keras.layers.Dense(8), -128),
    (tf.keras.layers.Dense(8, activation="sigmoid"), -128),       # not a clamp: no fused activation
    (types.SimpleNamespace(relu=True), 0),                         # imported layer (tflite2model, ...)
    (types.SimpleNamespace(relu=False), -128),
])
def test_activation_min(layer, expected):
    assert activation_min(layer) == expected


def conv_params(act_min, shift=2):
    return types.SimpleNamespace(quantize=[[1, shift], [1, shift]], act_min=act_min)


def test_reference_saturates_conv():
    psums = [[[1000, -1000, 508, -516]], [[511, 512, -512, -513]]]     # 2 filters, 1 x 4, shift 2
    dram = types.SimpleNamespace(fmap=[None, [[list(row) for row in f] for f in psums]])
    slo.batchnorm_output(conv_params(-128), 1, 0, dram)
    assert dram.fmap[1] == [[[127, -128, 127, -128]], [[127, 127, -128, -128]]]
    dram = types.SimpleNamespace(fmap=[None, [[list(row) for row in f] for f in psums]])
    slo.batchnorm_output(conv_params(0), 1, 0, dram)
    assert dram.fmap[1] == [[[127, 0, 127, 0]], [[127, 127, 0, 0]]]


def test_reference_inside_int8_unchanged():
    dram = types.SimpleNamespace(fmap=[None, [[[400, -400, 3, -3]]]])
    slo.batchnorm_output(types.SimpleNamespace(quantize=[[1, 2]], act_min=-128), 1, 0, dram)
    assert dram.fmap[1] == [[[100, -100, 0, -1]]]                         # floor, as the arithmetic shift


def test_reference_saturates_dense():
    # Dense: filter 0's multiplier and shift for every output, as the hardware (bug #12)
    params = types.SimpleNamespace(quantize=[[3, 4], [1, 0]], act_min=0)
    dram = types.SimpleNamespace(fmap=[None, [1000, -1000, 100, -1]])
    slo.batchnorm_output(params, 1, 0, dram)
    assert dram.fmap[1] == [127, 0, 18, 0]


def test_regmap_field():
    os.environ.setdefault("DMA_BITWIDTH", "64")
    transmissions, width = generator.layout_registers(REGMAP_DIR)
    last = transmissions[-1]
    field = [r for r in last if r["name"] == "quant_clamp_low"]
    assert field and field[0]["width"] == 8
    words = generator.pack_registers({"quant_clamp_low": 128}, REGMAP_DIR)
    pos = field[0]["pos"]
    assert any((w >> pos) & 0xFF == 0x80 for w in words)
