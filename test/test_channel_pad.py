# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Padding of the first layer's input channels (open_eye.channel_pad): an odd count above 1 to the next even count
(bug #7, on by default since 2026-11-22) and one channel to two (former workaround for RTL bug #17)."""
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
    monkeypatch.delenv(channel_pad.PAD_CHANNELS_ENV, raising=False)
    assert channel_pad.pad_first_layer(model, [wide]) == (model, False)   # off by default since the RTL fix of #17
    monkeypatch.setenv(channel_pad.PAD_CHANNELS_ENV, "1")
    padded, done = channel_pad.pad_first_layer(model, [wide])
    assert done and isinstance(padded[0], channel_pad.ChannelPaddedConv2D) and padded[1] == "next layer"
    assert channel_pad.pad_first_layer(model, [narrow]) == (model, False)
    assert channel_pad.pad_first_layer(model, [dense]) == (model, False)
    monkeypatch.setenv(channel_pad.PAD_CHANNELS_ENV, "0")
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


@pytest.mark.parametrize("width,channels,filters", [
    (28, 1, 32), (28, 1, 64), (8, 1, 64), (14, 1, 64),     # one channel: the cases of bug #39
    (28, 2, 32), (14, 4, 64), (14, 32, 64), (8, 8, 64),    # several channels: unchanged by the fix
])
def test_weight_sets_cover_every_pass(width, channels, filters, monkeypatch):
    # Bug #39: the weight stream carries one set per filter group and channel batch, the sets the RTL reads in
    # needed_wght_cycles passes. One channel with more than 16 filters per calculation got a single set, so the RTL
    # computed the second filter group with the first group's weights (MNIST Conv1 once it was no longer padded).
    for key, value in dict(PLATFORM, QUANT_AMOUNT="64").items():   # one quantization entry per filter
        monkeypatch.setenv(key, value)
    p = lp.LayerParameters([0], conv_layer(width, channels=channels, filters=filters), oep.get_oep(1), 0, 1)
    assert p.needed_wght_transmissions == p.needed_wght_cycles * p.iact_transmissions_pe


def test_check_wght_sets_refuses_a_short_stream():
    # the guard of bug #39: weight sets in the stream must equal weight passes x channel batches the RTL reads
    layer = types.SimpleNamespace(layer_name="Conv", filters=64, used_psum_per_PE=21, needed_wght_transmissions=3,
                                  needed_wght_cycles=4, iact_transmissions_pe=1)
    with pytest.raises(NotImplementedError, match="3 weight set"):
        lp.check_wght_sets(layer)
    layer.needed_wght_transmissions = 4
    assert lp.check_wght_sets(layer) == 4


@pytest.mark.parametrize("width", [8, 28])
@pytest.mark.parametrize("channels", [1, 2, 4, 8, 32])
@pytest.mark.parametrize("filters", [16, 32, 64])
def test_check_wght_sets_accepts_working_layers(width, channels, filters, monkeypatch):
    for key, value in dict(PLATFORM, QUANT_AMOUNT="64").items():
        monkeypatch.setenv(key, value)
    p = lp.LayerParameters([0], conv_layer(width, channels=channels, filters=filters), oep.get_oep(1), 0, 1)
    assert lp.check_wght_sets(p) == p.needed_wght_cycles * p.iact_transmissions_pe


def test_check_wght_sets_refuses_bug39b(monkeypatch):
    # tiled weights, 64 filters not a multiple of the tiling factor 3: 21 psums per PE (4 passes), sets of 22 (3 sets)
    for key, value in dict(PLATFORM, QUANT_AMOUNT="64").items():
        monkeypatch.setenv(key, value)
    p = lp.LayerParameters([0], conv_layer(14, channels=3, filters=64), oep.get_oep(1), 0, 1)
    assert (p.needed_wght_transmissions, p.needed_wght_cycles) == (3, 4)
    with pytest.raises(NotImplementedError, match="bug #39b"):
        lp.check_wght_sets(p)


def test_check_full_passes_refuses_an_uneven_last_pass():
    # the guard of bug #40: passes x psums per PE x kernels per calculation (the filter slots the RTL computes and
    # sends) must equal the filters, which the output and bias word counts use
    layer = types.SimpleNamespace(layer_name="Conv", filters=24, needed_wght_cycles=2, used_psum_per_PE=16,
                                  different_kernels_per_calculation=1)
    with pytest.raises(NotImplementedError, match="32 filter slots"):
        lp.check_full_passes(layer)
    layer.filters = 32
    assert lp.check_full_passes(layer) == 32


@pytest.mark.parametrize("width", [8, 28])
@pytest.mark.parametrize("channels", [1, 2, 4, 8, 32])
@pytest.mark.parametrize("filters", [16, 32, 64])
def test_check_full_passes_accepts_working_layers(width, channels, filters, monkeypatch):
    for key, value in dict(PLATFORM, QUANT_AMOUNT="64").items():
        monkeypatch.setenv(key, value)
    p = lp.LayerParameters([0], conv_layer(width, channels=channels, filters=filters), oep.get_oep(1), 0, 1)
    if p.needed_wght_transmissions != p.needed_wght_cycles * p.iact_transmissions_pe:
        pytest.skip("refused earlier by check_wght_sets (bug #39b)")
    assert lp.check_full_passes(p) == filters


@pytest.mark.parametrize("channels", [1, 2])
def test_check_full_passes_refuses_bug40(channels, monkeypatch):
    # 28 x 28 -> 24: 16 + 8 filters in two passes of 16 psums; the RTL sent 10,752 of the 14,336 result words
    for key, value in dict(PLATFORM, QUANT_AMOUNT="64").items():
        monkeypatch.setenv(key, value)
    p = lp.LayerParameters([0], conv_layer(28, channels=channels, filters=24), oep.get_oep(1), 0, 1)
    assert (p.needed_wght_cycles, p.used_psum_per_PE, p.different_kernels_per_calculation) == (2, 16, 1)
    assert lp.check_wght_sets(p) == 2
    with pytest.raises(NotImplementedError, match="bug #40"):
        lp.check_full_passes(p)


def test_check_full_passes_bug40_controls(monkeypatch):
    # 48 filters: 28 x 28 (one kernel per calculation) fills three passes of 16 and passed on the RTL; 8 x 8 (two
    # kernels) is 32 + 16, like 8 x 4 x 1 -> 48 that failed 48 / 48 maps
    for key, value in dict(PLATFORM, QUANT_AMOUNT="64").items():
        monkeypatch.setenv(key, value)
    p = lp.LayerParameters([0], conv_layer(28, channels=1, filters=48), oep.get_oep(1), 0, 1)
    assert lp.check_full_passes(p) == 48
    p = lp.LayerParameters([0], conv_layer(8, channels=1, filters=48), oep.get_oep(1), 0, 1)
    with pytest.raises(NotImplementedError, match="64 filter slots"):
        lp.check_full_passes(p)


# --- odd channel counts (bug #7) ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("channels,padded_to", [(1, None), (2, None), (3, 4), (4, None), (5, 8), (7, 8), (8, None),
                                                (9, 12), (11, 12), (13, 16)])
def test_odd_channels_are_padded(channels, padded_to, monkeypatch):
    """An odd count above 1 gets zero channels up to 4 or the next multiple of 4 (6 and 10 channels are wrong, #45),
    whatever OPENEYE_PAD_CHANNELS says; the padded layer passes check_conv_geometry, the original one is refused."""
    model = [conv_layer(8, channels), "next layer"]
    params = parameters(model[0], monkeypatch)
    for env in ("0", "1"):     # 8 pixels wide: one x pass, so the bug #17 padding never applies here
        monkeypatch.setenv(channel_pad.PAD_CHANNELS_ENV, env)
        assert channel_pad.needs_even_channels(params) == (padded_to is not None)
        assert channel_pad.padded_channels(params) == padded_to
        padded, done = channel_pad.pad_first_layer(model, [params])
        if padded_to is None:
            assert (padded, done) == (model, False)
            continue
        assert done and isinstance(padded[0], channel_pad.ChannelPaddedConv2D) and padded[1] == "next layer"
        assert (padded[0].original_channels, padded[0].pad_channels) == (channels, padded_to - channels)
        assert tuple(padded[0].input.shape)[3] == padded_to
        assert np.all(padded[0].kernel[:, :, channels:, :] == 0)      # the float model: the zero channel adds nothing
        assert np.array_equal(padded[0].kernel[:, :, :channels, :], np.asarray(model[0].weights[0]))
        new = parameters(padded[0], monkeypatch)
        assert new.channels == padded_to and not channel_pad.needs_even_channels(new)
        assert (new.iact_size_x, new.iact_size_y, new.filters, new.psum_size_x) == \
               (params.iact_size_x, params.iact_size_y, params.filters, params.psum_size_x)
        assert lp.check_conv_geometry(new, oep.get_oep(1)) is new
        with pytest.raises(NotImplementedError, match="bug #7"):
            lp.check_conv_geometry(params, oep.get_oep(1))


def test_odd_channel_padding_is_for_convolutions_only():
    dense = types.SimpleNamespace(layer_name="Dense", channels=3, iact_x_line_repetitions=1)
    pool = types.SimpleNamespace(layer_name="Pooling", channels=3, iact_x_line_repetitions=1)
    assert channel_pad.pad_first_layer(["dense"], [dense]) == (["dense"], False)
    assert channel_pad.pad_first_layer(["pool"], [pool]) == (["pool"], False)


def test_fill_three_channels_padded_to_four():
    layer = channel_pad.ChannelPaddedConv2D(conv_layer(4, channels=3, filters=2), 4)
    fmap = [[[c * 100 + x * 4 + y + 1 for y in range(4)] for x in range(4)] for c in range(4)]
    weights = [[[[c + 2] * 3] * 3 for _ in range(2)] for c in range(4)]       # [c][f][ky][kx]
    dram = types.SimpleNamespace(fmap=[fmap, "layer 1"], weights=[weights, "layer 1"])
    assert channel_pad.fill_padding_channels([layer], dram) == 1
    for c in range(3):                                                         # data channels kept
        assert dram.fmap[0][c] == [[c * 100 + x * 4 + y + 1 for y in range(4)] for x in range(4)]
        assert dram.weights[0][c] == [[[c + 2] * 3] * 3] * 2
    assert dram.fmap[0][3] == [[0] * 4] * 4
    assert dram.weights[0][3] == [[[channel_pad.PAD_WEIGHT] * 3] * 3] * 2
