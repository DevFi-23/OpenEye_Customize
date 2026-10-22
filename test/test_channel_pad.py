# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""One-channel input padded to two channels (open_eye.channel_pad, workaround for RTL bug #17)."""
import types

import numpy as np
import pytest

tf = pytest.importorskip("tensorflow")

from open_eye import channel_pad  # noqa: E402
from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402

# Platform of the cocotb_fpga tests (test_conv_const._run_conv_const)
PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "32", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}


def conv_layer(width, channels=1, filters=4):
    tf.keras.utils.set_random_seed(3)
    model = tf.keras.models.Sequential([
        tf.keras.Input((width, width, channels)),
        tf.keras.layers.Conv2D(filters, (3, 3), padding="same")])
    return model.layers[0]


def parameters(layer, monkeypatch):
    for key, value in PLATFORM.items():
        monkeypatch.setenv(key, value)
    return lp.LayerParameters([0], layer, oep.get_oep(1), 0, 1)


def test_padded_layer_shapes():
    layer = conv_layer(28)
    padded = channel_pad.ChannelPaddedConv2D(layer)
    assert (padded.original_channels, padded.pad_channels) == (1, 1)
    assert tuple(padded.input.shape) == (None, 28, 28, 2)
    assert padded.kernel.shape == (3, 3, 2, 4)
    kernel = np.asarray(layer.weights[0])
    assert np.array_equal(padded.weights[0][:, :, :1, :], kernel)
    assert not padded.weights[0][:, :, 1:, :].any()
    assert np.array_equal(np.asarray(padded.weights[1]), np.asarray(layer.weights[1]))
    # Everything else is the original layer's
    assert padded.name == layer.name and padded.filters == 4 and padded.strides == layer.strides
    assert tuple(padded.output.shape) == (None, 28, 28, 4)
    assert not hasattr(padded, "store_in_psum")
    with pytest.raises(ValueError):
        channel_pad.ChannelPaddedConv2D(conv_layer(8, channels=2))


def test_same_result_as_one_channel():
    """A zero channel adds nothing: Keras on [x, 0] with the padded kernel equals Keras on x.

    Integer operands as on the accelerator, so float32 sums are exact and the
    comparison can be exact as well.
    """
    rng = np.random.default_rng(0)
    layer = conv_layer(28)
    layer.set_weights([rng.integers(-64, 64, (3, 3, 1, 4)).astype("float32"),
                       rng.integers(-8, 8, 4).astype("float32")])
    padded = channel_pad.ChannelPaddedConv2D(layer)
    x = rng.integers(-32, 32, (1, 28, 28, 1)).astype("float32")
    two = tf.keras.layers.Conv2D(4, (3, 3), padding="same")
    two.build((None, 28, 28, 2))
    two.set_weights(padded.get_weights())
    x2 = np.concatenate([x, np.zeros_like(x)], axis=3)
    assert np.array_equal(two(x2).numpy(), layer(x).numpy())


@pytest.mark.parametrize("width,channels,needed", [
    (8, 1, False),      # one x pass: the one-channel writer is correct
    (16, 1, False),
    (28, 1, True),      # MNIST Conv1: two x passes, bug #17
    (40, 1, True),      # three x passes
    (28, 2, False),     # already takes the multi-channel writer
])
def test_needs_padding(width, channels, needed, monkeypatch):
    params = parameters(conv_layer(width, channels), monkeypatch)
    assert (params.iact_x_line_repetitions > 1) == (width > 16)
    assert channel_pad.needs_padding(params) == needed


def test_padded_layer_parameters(monkeypatch):
    """LayerParameters sees two channels, everything else as for the original layer."""
    layer = conv_layer(28)
    one = parameters(layer, monkeypatch)
    two = parameters(channel_pad.ChannelPaddedConv2D(layer), monkeypatch)
    assert (one.channels, two.channels) == (1, 2)
    assert (two.iact_size_x, two.iact_size_y, two.filters, two.psum_size_x, two.iact_x_line_repetitions) == \
           (one.iact_size_x, one.iact_size_y, one.filters, one.psum_size_x, one.iact_x_line_repetitions)
    assert not channel_pad.needs_padding(two)


def test_pad_first_layer(monkeypatch):
    model = [conv_layer(28), "next layer"]
    wide = types.SimpleNamespace(layer_name="Convolution2D", channels=1, iact_x_line_repetitions=2)
    narrow = types.SimpleNamespace(layer_name="Convolution2D", channels=1, iact_x_line_repetitions=1)
    dense = types.SimpleNamespace(layer_name="Dense", channels=1, iact_x_line_repetitions=2)
    padded, done = channel_pad.pad_first_layer(model, [wide])
    assert done and isinstance(padded[0], channel_pad.ChannelPaddedConv2D) and padded[1] == "next layer"
    assert channel_pad.pad_first_layer(model, [narrow]) == (model, False)
    assert channel_pad.pad_first_layer(model, [dense]) == (model, False)
    monkeypatch.setenv(channel_pad.PAD_CHANNELS_ENV, "0")      # reproduce bug #17
    assert channel_pad.pad_first_layer(model, [wide]) == (model, False)


def test_fill_padding_channels():
    layer = channel_pad.ChannelPaddedConv2D(conv_layer(4, filters=2))
    fmap = [[[c * 100 + x * 4 + y + 1 for y in range(4)] for x in range(4)] for c in range(2)]
    weights = [[[[1, 2, 3], [4, 5, 6], [7, 8, 9]] for _ in range(2)] for _ in range(2)]   # [c][f][ky][kx]
    dram = types.SimpleNamespace(fmap=[fmap, "layer 1"], weights=[weights, "layer 1"])
    assert channel_pad.fill_padding_channels([layer], dram) == 1
    assert dram.fmap[0][0] == [[x * 4 + y + 1 for y in range(4)] for x in range(4)]      # data channel kept
    assert dram.fmap[0][1] == [[0] * 4] * 4
    assert dram.weights[0][0][1] == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    assert dram.weights[0][1] == [[[1] * 3] * 3] * 2           # non-zero: all-zero kernels fail (bug #22)
    assert dram.fmap[1] == "layer 1"
    assert channel_pad.fill_padding_channels([conv_layer(4)], dram) == 0          # not padded: unchanged
