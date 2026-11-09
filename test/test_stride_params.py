# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The host side of a strided convolution (bugs #41b, #41d; doc/experiments/2026-11-07_bug41_stride.md section 8).

With STRIDE_ENABLED=1 the RTL computes stride 2 right; the host programmed and decoded it with input sizes where output
sizes belong:
  A  the output order (test_utils_main.calculate_conv_serial) switched to the next kernel after psum_size_x + add_up
     slots, add_up counting input pixels (psum_add_up * strideX): from the second kernel on every output was read 4
     slots late (12 x 8: the DUT sends 6 outputs + 2 padding slots per kernel);
  B  iact_x_add_up = iact_size_x + add_up left an odd width one column short (7 -> 7 instead of 8);
  Y  the rows of a pass, (iact_size_y + kernel - strideY), left an odd height without its bottom padding row, so a
     strided layer reading an on-chip input took that row from whatever followed the image (#41d);
  W  the write-back length (fsm_psum_limit) counted input pixels, 4 x the outputs at stride 2.
Every value is unchanged at stride 1 and for widths / heights that divide by the stride (the regression's layers).
"""
import io
import os

import pytest

tf = pytest.importorskip("tensorflow")

from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402
from open_eye import test_utils_main as tum  # noqa: E402

PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32", "STRIDE_ENABLED": "1"}


@pytest.fixture
def params(monkeypatch):
    for key, value in PLATFORM.items():
        monkeypatch.setenv(key, value)
    return oep.get_oep(1)


def conv_layers(width, height, stride, layers=1, channels=4, filters=16):
    tf.keras.utils.set_random_seed(1)
    model = tf.keras.models.Sequential([tf.keras.Input((width, height, channels))] +
                                       [tf.keras.layers.Conv2D(filters, (3, 3), strides=stride, padding="same")
                                        for _ in range(layers)])
    return model.layers


def build(layers, params):
    out = [0] * len(layers)
    for n, layer in reversed(list(enumerate(layers))):
        out[len(layers) - n - 1] = lp.LayerParameters(out, layer, params, n, len(layers))
    return list(reversed(out))


@pytest.mark.parametrize("width,height,expected", [
    (12, 8, [[0, x, 0] for x in range(6)] + [None, None] + [[1, 0, 0]]),     # 6 outputs + 2 padding slots per kernel
    (4, 8, [[0, 0, 0], [0, 1, 0], None, None, [1, 0, 0]]),
    (8, 8, [[0, x, 0] for x in range(4)] + [[1, 0, 0]]),                       # no padding: unchanged
])
def test_output_order_counts_output_positions(width, height, expected, params):
    p = build(conv_layers(width, height, 2), params)[0]
    results = [[[0] * p.psum_size_y for _ in range(p.psum_size_x)] for _ in range(p.filters)]
    order = tum.calculate_conv_serial(params, p, results, io.StringIO())
    assert order[:len(expected)] == expected


@pytest.mark.parametrize("width,height,stride,x_add_up,y_add_up", [
    (7, 8, 2, 8, 8), (9, 9, 2, 16, 10), (12, 8, 2, 16, 8), (8, 7, 2, 8, 8), (16, 14, 2, 16, 14),
    (7, 7, 1, 8, 7), (8, 8, 1, 8, 8), (28, 28, 1, 32, 28), (14, 14, 1, 16, 14),          # stride 1: as before
])
def test_padded_input_sizes(width, height, stride, x_add_up, y_add_up, params):
    p = build(conv_layers(width, height, stride), params)[0]
    assert (p.iact_x_add_up, p.iact_y_add_up) == (x_add_up, y_add_up)
    if stride == 1:
        assert p.iact_x_add_up == p.iact_size_x + p.add_up and p.iact_y_add_up == p.iact_size_y
    assert p.iact_x_add_up == (p.psum_size_x + p.psum_add_up) * stride


def test_odd_height_reads_the_bottom_padding_row(params):
    # 8 x 7 at stride 2: outputs at rows 0, 2, 4, 6, the last window reads rows 5..7 (7 = bottom padding):
    # rows -1 .. 7 = 9 per pass, as 8 x 8 would need; the old formula gave 8
    odd, even = (build(conv_layers(8, h, 2), params)[0] for h in (7, 8))
    assert odd.iact_buffer_words_per_write == even.iact_buffer_words_per_write
    assert odd.iact_glb_writing_cycles == even.iact_glb_writing_cycles


@pytest.mark.parametrize("stride", [1, 2])
def test_write_back_length_counts_outputs(stride, params):
    first = build(conv_layers(16, 14, stride, layers=2, filters=4), params)[0]
    lanes = min(params.TRANS_WORDS, params.NUM_GLB_PSUM)
    out_w, out_h = first.iact_x_add_up // stride, -(-first.iact_size_y // stride)
    assert first.send_values_out == 0
    assert first.fsm_psum_limit == -(-(out_w * first.filters * out_h) // lanes) + 11
