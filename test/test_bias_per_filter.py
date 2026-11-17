# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Bias once per filter (BIAS_PER_FILTER_EN, doc/experiments/2026-11-17_bias_per_filter.md), Python side.

A model of psum_pipeline.v builds the psum buffer twice: from the old per-output bias stream (GET_BIAS shifts
CONV_BIAS_CYCLES words into an address) and from the per-filter stream (bias table, then the rewrite: the word of group g
shifted together from the table, written to addresses g, g + groups, ...). Both must give the same buffer for every
configuration LayerParameters.set_bias_per_filter accepts; the decision itself is tested against its rules.

Usage: venv/bin/python -m pytest -q test/test_bias_per_filter.py
"""
import math
import random
from types import SimpleNamespace

import pytest

from open_eye.layer_parameters import LayerParameters
from open_eye.psum_stream_mapper import PsumStreamMapper


def params_for(dma=64, psum_bits=20, clusters=4, glb_psum=4, quant=1024, enable=1):
    return SimpleNamespace(SERIAL=True, DMA_BITWIDTH=dma, DATA_PSUM_BITWIDTH=psum_bits, Clusters=clusters,
                           NUM_GLB_PSUM=glb_psum, QUANT_AMOUNT=quant, BIAS_PER_FILTER_EN=enable,
                           Clusters_X=2, Clusters_Y=max(1, clusters // 2), Psum_Routers=glb_psum)


def layer_for(filters, groups, rows, xreps):
    return SimpleNamespace(layer_name="Conv", fully_connected=0, filters=filters,
                           different_kernels_per_calculation=groups, iact_size_y=rows, iact_x_line_repetitions=xreps,
                           trans_cycles_psum=0, bias_per_filter=0, bias_groups=0)


def rtl_words_per_dma(params):
    return 2 if params.DMA_BITWIDTH == 64 else 1          # PSUM_OUTPUT_WORDS of OpenEye_FPGA.v


def buffer_old(params, stream):
    """GET_BIAS of the old stream: shift CONV_BIAS_CYCLES payloads into an address, write, next address."""
    per = rtl_words_per_dma(params)
    payload_bits = per * params.DATA_PSUM_BITWIDTH
    cycles = math.ceil(params.Clusters * params.NUM_GLB_PSUM / per)
    width = params.DATA_PSUM_BITWIDTH * params.Clusters * params.NUM_GLB_PSUM
    buf, data, count = {}, 0, 0
    for word in stream:
        data = ((data << payload_bits) | (word & ((1 << payload_bits) - 1))) & ((1 << width) - 1)
        count += 1
        if count == cycles:
            buf[len(buf)] = data
            count = 0
    return buf


def buffer_new(params, layer, stream):
    """The rewrite of psum_pipeline.v from the per-filter stream."""
    per = rtl_words_per_dma(params)
    bits = params.DATA_PSUM_BITWIDTH
    payload_bits = per * bits
    cycles = math.ceil(params.Clusters * params.NUM_GLB_PSUM / per)
    width = bits * params.Clusters * params.NUM_GLB_PSUM
    k = layer.different_kernels_per_calculation
    block = cycles // k
    table = []
    for word in stream:
        table += [(word >> (s * bits)) & ((1 << bits) - 1) for s in range(per)]
    buf = {}
    for g in range(layer.bias_groups):
        data = 0
        for q in reversed(range(k)):                      # the group's last filter first, as the old stream
            b = table[g * k + q]
            payload = sum(b << (s * bits) for s in range(per))
            for _ in range(block):
                data = ((data << payload_bits) | payload) & ((1 << width) - 1)
        for t in range(layer.iact_size_y * layer.iact_x_line_repetitions):
            buf[g + t * layer.bias_groups] = data
    return buf


def streams(params, layer, biases):
    old_layer = SimpleNamespace(**vars(layer))
    old_layer.bias_per_filter = 0
    old = PsumStreamMapper(params, old_layer, 0, biases).get_psum_stream()
    new = PsumStreamMapper(params, layer, 0, biases).get_psum_stream()
    return old, new


CONFIGS = [
    # dma, psum bits, clusters, NUM_GLB_PSUM, filters, groups, rows, x passes
    (64, 20, 4, 4, 16, 1, 4, 1),        # the baseline platform, one group
    (64, 20, 4, 4, 32, 2, 14, 2),       # two kernel groups (short lines, bug #32 order)
    (64, 20, 4, 2, 32, 1, 14, 4),       # NUM_GLB_PSUM 2
    (64, 20, 2, 2, 16, 1, 28, 7),       # CR 1 (2 clusters), Table 3 Conv1
    (64, 20, 16, 4, 32, 2, 7, 1),       # CR 8 X 4
    (64, 20, 16, 4, 16, 4, 28, 1),      # four groups
    (64, 32, 4, 4, 16, 1, 3, 2),        # 32-bit psums
    (32, 20, 4, 4, 8, 1, 3, 2),         # DMA 32: one bias per word
    (64, 20, 4, 4, 5, 1, 2, 1),         # odd filter count: half-empty last word
]


@pytest.mark.parametrize("cfg", CONFIGS, ids=[str(c) for c in CONFIGS])
def test_same_buffer(cfg):
    dma, bits, clusters, glb, filters, groups, rows, xreps = cfg
    params = params_for(dma, bits, clusters, glb)
    layer = layer_for(filters, groups, rows, xreps)
    LayerParameters.set_bias_per_filter(layer, params)
    assert layer.bias_per_filter == 1
    assert layer.bias_groups == filters // groups
    rng = random.Random(sum(cfg))
    biases = [rng.randint(-(1 << (bits - 1)), (1 << (bits - 1)) - 1) for _ in range(filters)]
    old, new = streams(params, layer, biases)
    assert len(new) == math.ceil(filters / rtl_words_per_dma(params)) == layer.trans_cycles_psum
    assert len(new) < len(old)
    assert buffer_new(params, layer, new) == buffer_old(params, old)


@pytest.mark.parametrize("change, on", [
    ({}, 1),
    ({"enable": 0}, 0),                 # hardware without the table
    ({"dma": 128}, 0),                  # PSUM_OUTPUT_WORDS of the RTL differs from the Python stream at 128 bit
    ({"quant": 8}, 0),                  # more filters than the bias table
])
def test_decision_params(change, on):
    kw = dict(dma=64, psum_bits=20, clusters=4, glb_psum=4, quant=1024, enable=1)
    kw.update(change)
    params = params_for(**kw)
    layer = layer_for(16, 1, 4, 1)
    LayerParameters.set_bias_per_filter(layer, params)
    assert layer.bias_per_filter == on


@pytest.mark.parametrize("filters, groups, on", [
    (16, 1, 1), (16, 2, 1), (16, 4, 1),
    (10, 4, 0),                         # the last group would be partial
    (16, 3, 0),                         # 16 lanes do not split into 3 groups
])
def test_decision_groups(filters, groups, on):
    params = params_for()
    layer = layer_for(filters, groups, 4, 1)
    LayerParameters.set_bias_per_filter(layer, params)
    assert layer.bias_per_filter == on


def test_fully_connected_keeps_old_stream():
    params = params_for()
    layer = layer_for(16, 1, 1, 1)
    layer.fully_connected = 1
    LayerParameters.set_bias_per_filter(layer, params)
    assert layer.bias_per_filter == 0
