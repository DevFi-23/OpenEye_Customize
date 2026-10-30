# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Order of the conv bias stream against a model of the RTL bias load (bug #32).

A Conv2D layer with short output lines computes different_kernels_per_calculation (D) filters at a time: kernel group k
on the k-th block of CLUSTERS / D clusters, cluster 0 first (calculate_conv_serial, the psum read-out). One psum buffer
address holds the biases of D filters. GET_BIAS in psum_pipeline.v shifts every DMA word in at the low end of the
buffer bus (lane = cluster * NUM_GLB_PSUM + g) and writes an address after CONV_BIAS_CYCLES words, so the first word
of an address ends up in the last cluster. Before the fix the stream sent the filters in plain order and with D = 2 the
filters of every pair got each other's bias (doc/experiments/2026-10-30_bug32_bias_order.md).
"""
import types

import pytest

from open_eye import generic_test_utils as gtu
from open_eye.psum_stream_mapper import ConvPsumStreamMapper, PsumStreamMapper


def mapper(filters, groups, lines=2, reps=1, dma=64, psum_bits=20, glb_psum=4, clusters=4, bias=None):
    params = types.SimpleNamespace(SERIAL=1, DMA_BITWIDTH=dma, DATA_PSUM_BITWIDTH=psum_bits, NUM_GLB_PSUM=glb_psum,
                                   Clusters=clusters)
    layer = types.SimpleNamespace(filters=filters, different_kernels_per_calculation=groups, iact_size_y=lines,
                                  iact_x_line_repetitions=reps)
    bias = bias if bias is not None else [-500 + 37 * f for f in range(filters)]   # distinct, negative ones too
    return ConvPsumStreamMapper(params, layer, 0, bias)


def rtl_bias_load(stream, dma=64, psum_bits=20, glb_psum=4, clusters=4):
    """psum_pipeline.v, PSUM_IDLE during GET_BIAS (conv): the buffer addresses as lists of lane values."""
    words = min(2, dma // psum_bits)                                 # PSUM_OUTPUT_WORDS: psums per DMA word
    lanes = clusters * glb_psum
    cycles = (lanes + words - 1) // words                            # CONV_BIAS_CYCLES
    bus = [0] * lanes
    addresses = []
    for n, word in enumerate(stream):
        new = [(word >> (psum_bits * i)) & ((1 << psum_bits) - 1) for i in range(words)]
        bus = (new + bus)[:lanes]                                    # (bus << payload) | word: lane i -> lane i + words
        if n % cycles == cycles - 1:
            addresses.append([v - (1 << psum_bits) if v >> (psum_bits - 1) else v for v in bus])
    return addresses


def bias_per_cluster(m, **platform):
    """[address][cluster] -> the bias every lane of that cluster holds (asserts that they agree)."""
    glb_psum, clusters = platform.get("glb_psum", 4), platform.get("clusters", 4)
    out = []
    for lanes in rtl_bias_load(m.get_psum_stream(), **platform):
        per_cluster = [set(lanes[c * glb_psum:(c + 1) * glb_psum]) for c in range(clusters)]
        assert all(len(s) == 1 for s in per_cluster), per_cluster
        out.append([s.pop() for s in per_cluster])
    return out


def wanted(filters, groups, lines, reps, bias, clusters=4):
    """The bias the compute expects: address a of an output line, cluster c -> filter groups * a + c // (clusters / D)."""
    per_line = [[bias[groups * a + c // (clusters // groups)] for c in range(clusters)] for a in range(filters // groups)]
    return per_line * (lines * reps)


@pytest.mark.parametrize("dma,psum_bits", [(64, 20), (64, 32), (32, 20)])
@pytest.mark.parametrize("filters,groups", [(4, 1), (64, 1), (8, 2), (64, 2), (16, 4), (64, 4)])
def test_every_cluster_gets_the_bias_of_its_filter(filters, groups, dma, psum_bits):
    m = mapper(filters, groups, lines=3, reps=2, dma=dma, psum_bits=psum_bits)
    got = bias_per_cluster(m, dma=dma, psum_bits=psum_bits)
    assert got == wanted(filters, groups, 3, 2, m.dram_bias)


@pytest.mark.parametrize("filters,groups", [(8, 2), (16, 4)])
def test_plain_filter_order_swaps_the_kernel_groups(filters, groups, monkeypatch):
    """The stream before the fix, on the same load model: the groups of every address arrive reversed (bug #32)."""
    monkeypatch.setattr(PsumStreamMapper, "bias_stream_filter_order", lambda self: list(range(self.layer_params.filters)))
    m = mapper(filters, groups)
    got = bias_per_cluster(m)
    want = wanted(filters, groups, 2, 1, m.dram_bias)
    assert got != want
    assert got == [row[::-1] for row in want]                      # pairs swapped (D = 2), groups of 4 reversed (D = 4)


def test_one_kernel_group_keeps_the_stream():
    """Layers with one kernel group (every regression model until the real MNIST conv3) send exactly the old stream."""
    m = mapper(32, 1, lines=4, reps=2)
    old = []
    for _ in range(2 * 4):
        for f in range(32):
            b = gtu.to_twos_complement(m.dram_bias[f], 20)
            old.extend([b + (b << 20)] * 8)
    assert m.get_psum_stream() == old


def test_filter_order():
    assert mapper(8, 1).bias_stream_filter_order() == list(range(8))
    assert mapper(8, 2).bias_stream_filter_order() == [1, 0, 3, 2, 5, 4, 7, 6]
    assert mapper(8, 4).bias_stream_filter_order() == [3, 2, 1, 0, 7, 6, 5, 4]
