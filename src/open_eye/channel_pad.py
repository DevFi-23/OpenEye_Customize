# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Pad a one-channel convolution input to two channels (former Python workaround for RTL bug #17).

Bug #17 is fixed in the RTL since 2026-11-04 (as upstream 36395dd: a one-channel
pixel is a word of its own, no row-pair packing), so the padding is OFF by
default; OPENEYE_PAD_CHANNELS=1 turns it on again, for comparisons with the
measurements made before the fix. The description below is the bug as it was.

The one-channel writer of hdl/iact_stream_constructor.v computes its RAM
address from row and column only and ignores the x passes of an image wider
than one pass (iact_x_line_repetitions > 1, e.g. MNIST Conv1 28x28x1 on 2x2
clusters): the output rows come out equal in pairs. Two or more channels take
the multi-channel writer, which handles the x passes.

The workaround keeps the RTL as it is and changes the data the host sends:
the first layer gets a second input channel whose activations are all zero.
Every product of that channel is 0, so each output equals the one-channel
result exactly (no rounding, the accumulation is integer). The weights of
that channel are 1, not 0: a channel whose kernels are all zero makes every
output wrong (found 2026-10-22, open bug #22), while any non-zero value is
harmless next to zero activations. The cost is the second channel on the DMA
input stream, in the converter and in the weight stream; the zero activations
are skipped by the sparse PE datapath.

Used by the testbench (OpenEye_FPGA_tb.py) when OPENEYE_PAD_CHANNELS=1 (was on
by default until the bug #17 fix). Only layer 0 is padded, the only layer
whose activations come from the DMA stream through the converter.
"""

import os

import numpy as np

from open_eye.layer_adapter import TensorShapeAdapter

PAD_CHANNELS_ENV = "OPENEYE_PAD_CHANNELS"
PAD_WEIGHT = 1      # weight of the padding channel: any non-zero value (bug #22: all-zero kernels fail)


def padding_enabled():
    """True when OPENEYE_PAD_CHANNELS is set to 1 (off by default since the RTL fix of bug #17)."""
    return os.environ.get(PAD_CHANNELS_ENV, "0") == "1"


def needs_padding(layer_params):
    """True for the layers bug #17 breaks: a convolution with one input channel and more than one x pass."""
    return (layer_params.layer_name == "Convolution2D" and layer_params.channels == 1
            and layer_params.iact_x_line_repetitions > 1)


class ChannelPaddedConv2D:
    """A Conv2D layer seen with extra input channels whose kernel is zero.

    Stands in for the layer where LayerParameters and DRAMContents read it:
    input.shape and kernel.shape get the new channel count, weights[0] the
    kernel [kx][ky][c][f] with zeros for the new channels (the float model:
    the extra channel adds nothing; fill_padding_channels sets the integer
    weights the accelerator gets); everything else
    (name, filters, output, strides, ...) comes from the original layer.
    """

    def __init__(self, layer, channels=2):
        self._layer = layer
        shape = tuple(layer.input.shape)
        self.original_channels = shape[3]
        self.pad_channels = channels - self.original_channels
        if self.pad_channels <= 0:
            raise ValueError("layer already has %d input channels" % self.original_channels)
        self.input = TensorShapeAdapter(shape[:3] + (channels,))
        kernel = np.asarray(layer.weights[0])
        zeros = np.zeros(kernel.shape[:2] + (self.pad_channels,) + kernel.shape[3:], dtype=kernel.dtype)
        self.kernel = np.concatenate([kernel, zeros], axis=2)
        self.weights = [self.kernel] + list(layer.weights[1:])

    def get_weights(self):
        return [np.asarray(w) for w in self.weights]

    def __getattr__(self, name):
        # Only called for attributes not set above
        if name == "_layer":
            raise AttributeError(name)
        return getattr(self._layer, name)


def pad_first_layer(model, layer_parameters):
    """Return (model, padded): layer 0 wrapped in ChannelPaddedConv2D when needs_padding says so.

    model is the list of layers the testbench runs; the caller rebuilds the
    layer parameters from the returned model when padded is True.
    """
    if not padding_enabled() or not needs_padding(layer_parameters[0]):
        return model, False
    return [ChannelPaddedConv2D(model[0])] + list(model[1:]), True


def fill_padding_channels(model, dram):
    """Set the padding channels of layer 0 in dram: activations 0, weights PAD_WEIGHT.

    DRAMContents fills every channel (random activations, and zero weights
    replaced by +-1), and the debug hooks of the testbench may overwrite them,
    so this runs last, before the streams and the reference are built.
    Returns the number of padding channels (0 when layer 0 is not padded).
    """
    layer = model[0]
    if not isinstance(layer, ChannelPaddedConv2D):
        return 0
    for c in range(layer.original_channels, layer.original_channels + layer.pad_channels):
        dram.fmap[0][c] = [[0 for _ in row] for row in dram.fmap[0][c]]
        dram.weights[0][c] = [[[PAD_WEIGHT for _ in row] for row in kernel] for kernel in dram.weights[0][c]]
    return layer.pad_channels
