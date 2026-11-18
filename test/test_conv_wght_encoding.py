# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Conv weight encoding with zero weights (bug #22): open_eye.conv_wght_encoding, ConvWghtStreamMapper, checked
against open_eye.wght_pipeline_model (the cycle model of hdl/data_pipeline_wght.v that matched the RTL)."""
import math
import random

import pytest

from open_eye import conv_wght_encoding as cwe
from open_eye import wght_pipeline_model as wpm

EXTRA_WORD = 0x200044          # a PE captures one word beyond its block; the worst case is real data


def pack(spad, words):
    """24-bit words as create_pe_data_wght_stream packs them: {overhead[3:0], value[7:0]} per entry."""
    return [sum((((oh & 0xF) << 8) | (v & 0xFF)) << (12 * i) for i, (v, oh) in enumerate(word)) for word in spad[:words]]


def decode(columns, words_per_block):
    spad = cwe.encode_columns(columns, 2, words_per_block, words_per_block + 4)
    words = pack(spad, words_per_block)
    addr, data, data_words = wpm.load(words, len(columns[0]), extra_word=EXTRA_WORD)
    got, pointers = wpm.read_columns(addr, data, len(columns), len(columns[0]))
    return words, got, pointers, data_words


@pytest.mark.parametrize("column,entries", [
    ([1, 2, 3, 4, 5, 6, 7, 8], [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0], [8, 0]]),     # dense
    ([0, 0, 3, 4, 5, 6, 7, 8], [[3, 2], [4, 0], [5, 0], [6, 0], [7, 0], [8, 0]]),                      # leading zeros
    ([1, 2, 3, 4, 5, 6, 7, 0], [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0]]),             # padding slot covers it
    ([1, 2, 3, 4, 5, 6, 0, 0], [[1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [6, 0], [0, 1]]),             # explicit end
    ([1, 0, 3, 4, 5, 6, 7, 0], [[1, 0], [0, 0], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0]]),             # gap split
    ([0] * 8, [[0, 7]]),                                                                                 # empty column
    ([0] * 32, [[0, 15], [0, 15]]),                                                                      # 4-bit overhead
    ([5] + [0] * 20 + [6] + [0] * 10, [[5, 0], [0, 15], [6, 4], [0, 9]]),                                # long runs
])
def test_column_entries(column, entries):
    assert cwe.column_entries(column) == entries


def test_column_that_needs_an_all_zero_word():
    with pytest.raises(ValueError):
        cwe.column_entries([1, 2, 0])        # even count, one trailing zero, no gap to split


def test_encode_columns_block():
    spad = cwe.encode_columns([[1, 2, 3, 0], [0, 0, 0, 0]], 2, 6, 8)
    assert spad[:2] == [[[1, 0], [2, 0]], [[3, 0], [0, 0]]]            # padding slot covers filter 3
    assert spad[2] == [[0, 3], [0, 0]]                                  # empty column + padding slot
    assert spad[3:6] == [[list(e) for e in cwe.FILLER]] * 3            # rest of the block
    assert spad[6:] == [[[0, 0], [0, 0]]] * 2                           # beyond the block
    with pytest.raises(ValueError):
        cwe.encode_columns([[1, 2, 3, 4]] * 4, 2, 7, 8)                # 8 words needed


def test_dense_columns_are_unchanged():
    columns = [[c * 10 + f + 1 for f in range(8)] for c in range(6)]
    spad = cwe.encode_columns(columns, 2, 24, 30)
    assert [e for word in spad[:24] for e in word] == [[v, 0] for col in columns for v in col]


# Columns of up to 16 filters: the RTL counts positions in a 5-bit register, and the mapper never makes longer
# columns (M0 = used_psum_per_PE is 16 for the 32- and 64-filter layers)
@pytest.mark.parametrize("filters", [4, 8, 16])
@pytest.mark.parametrize("zeros", [0.0, 0.05, 0.3, 0.6, 0.95, 1.0])
def test_rtl_model_reads_what_was_encoded(filters, zeros):
    rng = random.Random(filters * 100 + int(zeros * 100))
    for _ in range(20):
        columns = [[0 if rng.random() < zeros else rng.choice([v for v in range(-127, 128) if v])
                    for _ in range(filters)] for _ in range(6)]
        block = 6 * math.ceil(filters / 2)
        words, got, pointers, data_words = decode(columns, block)
        assert got == columns
        assert 0 not in words                                            # no all-zero word in the block
        assert data_words >= pointers[len(columns) - 1]                  # the MAC loop bound covers every column


def test_old_encoding_fails_in_the_rtl_model():
    """The format the mapper wrote before (zeros carried across columns, nothing for an empty column)."""
    columns = [[1, 2, 3, 4, 5, 6, 7, 8], [0] * 8, [1, 2, 3, 4, 5, 6, 7, 8]]
    old = [[[1, 0], [2, 0]], [[3, 0], [4, 0]], [[5, 0], [6, 0]], [[7, 0], [8, 0]],
           [[1, 8], [2, 0]], [[3, 0], [4, 0]], [[5, 0], [6, 0]], [[7, 0], [8, 0]]]
    addr, data, _ = wpm.load(pack(old, 8) + [0] * 4, 8)
    got, pointers = wpm.read_columns(addr, data, 3, 8)
    assert got != columns
    assert decode(columns, 12)[1] == columns


def nonzero(rng):
    return rng.choice([v for v in range(-127, 128) if v])


# Dense layout for the sparse PE (step 2 of the per-layer weight format P1, README_FI section 2): every weight an
# entry with overhead 0, zero weights included
@pytest.mark.parametrize("filters", [2, 3, 4, 5, 8, 16])
@pytest.mark.parametrize("zeros", [0.0, 0.05, 0.3, 0.6, 1.0])
@pytest.mark.parametrize("extra", [EXTRA_WORD, 0])
def test_dense_layout_reads_back_in_raw_mode(filters, zeros, extra):
    rng = random.Random(filters * 1000 + int(zeros * 100))
    for _ in range(20):
        columns = [[0 if rng.random() < zeros else nonzero(rng) for _ in range(filters)] for _ in range(6)]
        block = 6 * math.ceil(filters / 2)
        spad = cwe.encode_dense(columns, 2, block, block + 4)
        assert [e for word in spad[:block] for e in word if e[1]] == []            # overhead 0 everywhere
        addr, data, data_words = wpm.load(pack(spad, block), filters, extra_word=extra, raw_mode=True)
        got, pointers = wpm.read_columns(addr, data, len(columns), filters)
        assert got == columns
        assert data_words >= pointers[len(columns) - 1]
        assert pointers[:len(columns)] == [(k + 1) * math.ceil(filters / 2) for k in range(len(columns))]


def test_dense_layout_without_raw_mode():
    """Outside raw mode an all-zero word (two zero weights) is dropped and the layer reads wrong weights; without
    such a word the dense layout reads back as it is."""
    with_pair = [[1, 2, 0, 0, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7, 8]]
    without = [[1, 0, 3, 0, 5, 0, 7, 0], [0, 2, 0, 4, 0, 6, 0, 8]]
    for columns, ok in ((with_pair, False), (without, True)):
        spad = cwe.encode_dense(columns, 2, 8, 10)
        assert (cwe.count_zero_words(spad, 8) == 0) == ok
        addr, data, _ = wpm.load(pack(spad, 8), 8, extra_word=EXTRA_WORD)
        got, _ = wpm.read_columns(addr, data, 2, 8)
        assert (got == columns) == ok
        addr, data, _ = wpm.load(pack(spad, 8), 8, extra_word=EXTRA_WORD, raw_mode=True)
        assert wpm.read_columns(addr, data, 2, 8)[0] == columns


@pytest.mark.parametrize("zeros", [0.05, 0.3, 0.9])
def test_zero_compressed_layout_is_the_same_in_raw_mode(zeros):
    """Raw mode changes only what happens to all-zero words, and encode_columns makes none in the block."""
    rng = random.Random(int(zeros * 100))
    for extra in (EXTRA_WORD, 0):
        columns = [[0 if rng.random() < zeros else nonzero(rng) for _ in range(16)] for _ in range(6)]
        spad = cwe.encode_columns(columns, 2, 48, 52)
        read = []
        for raw in (False, True):
            addr, data, data_words = wpm.load(pack(spad, 48), 16, extra_word=extra, raw_mode=raw)
            got, pointers = wpm.read_columns(addr, data, 6, 16)
            read.append((got, pointers[:6]))                # pointers beyond the used columns may differ
        assert read[0] == read[1] and read[0][0] == columns


def test_dense_layout_block_too_short():
    with pytest.raises(ValueError):
        cwe.encode_dense([[1, 2, 3]] * 4, 2, 7, 8)                    # 8 words needed (padding slot per column)


tf = pytest.importorskip("tensorflow")
from open_eye import layer_parameters as lp  # noqa: E402
from open_eye import open_eye_parameters as oep  # noqa: E402
from open_eye import wght_stream_mapper as wsm  # noqa: E402

PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "64", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}


def mapper_layer(width, channels, filters, monkeypatch):
    for key, value in PLATFORM.items():
        monkeypatch.setenv(key, value)
    model = tf.keras.models.Sequential([tf.keras.Input((width, 8, channels)),
                                        tf.keras.layers.Conv2D(filters, (3, 3), padding="same")])
    params = oep.get_oep(1)
    return params, lp.LayerParameters([0], model.layers[0], params, 0, 1)


@pytest.mark.parametrize("width,channels,filters", [(20, 2, 8), (8, 8, 16), (8, 4, 32)])
@pytest.mark.parametrize("zeros", [0.0, 0.3, "channel 1"])
def test_mapper_blocks_decode_to_the_weights(width, channels, filters, zeros, monkeypatch):
    """Every PE block of every weight transmission, through the RTL model, gives the PE the layer's weights."""
    params, L = mapper_layer(width, channels, filters, monkeypatch)
    rng = random.Random(3)
    w = [[[[0 if (zeros == "channel 1" and c == 1) or (zeros != "channel 1" and rng.random() < zeros)
            else rng.choice([v for v in range(-127, 128) if v]) for x in range(3)] for y in range(3)]
          for f in range(filters)] for c in range(channels)]
    block = math.ceil(L.used_wght_per_PE / params.PARALLEL_MACS)
    column_length = math.ceil(L.used_wght_per_PE / L.used_iact_per_PE)
    filters_w = (L.used_psum_per_PE & 0x3F) or 16
    for rep in range(L.needed_wght_transmissions):
        mapper = wsm.ConvWghtStreamMapper(params, L, rep, w, 0)
        for cx in range(params.Clusters_X):
            for cy in range(params.Clusters_Y):
                for router in range(params.Wght_Routers):
                    if L.computing_mx[cx][cy][router][0] != 1:
                        continue
                    dense = mapper.write_dense_wght_data_storage(cx, cy, router)
                    wpc = math.ceil(column_length / 2)
                    want = [[e[0] for word in dense[k * wpc:(k + 1) * wpc] for e in word][:column_length]
                            for k in range(L.used_iact_per_PE)]
                    words = mapper.create_pe_data_wght_stream(mapper.write_wght_data_storage(cx, cy, router))
                    assert len(words) == block and 0 not in words
                    addr, data, data_words = wpm.load(words, filters_w, extra_word=EXTRA_WORD)
                    got, pointers = wpm.read_columns(addr, data, L.used_iact_per_PE, column_length)
                    assert got == want
                    assert data_words >= pointers[L.used_iact_per_PE - 1]
                    if zeros == 0.0:
                        assert mapper.write_wght_data_storage(cx, cy, router) == dense   # unchanged stream


@pytest.mark.parametrize("width,channels,filters", [(8, 4, 16), (8, 8, 16), (28, 1, 32)])
def test_dense_hardware_gets_the_plain_layout(width, channels, filters, monkeypatch):
    """SPARSITY_EN=0: the dense PE reads every weight in its slot. No column encoding (bug #22 is the sparse format),
    8-bit entries without overhead, and all-zero words are two zero weights, so they stay in the stream
    (doc/experiments/2026-11-09_dense_vs_sparse.md)."""
    monkeypatch.setenv("SPARSITY_EN", "0")
    params, L = mapper_layer(width, channels, filters, monkeypatch)
    assert params.WGHT_WOH_Bitwidth == params.WGHT_Bitwidth == 8
    rng = random.Random(5)
    w = [[[[0 if (c == 0 and channels > 1) else rng.choice([v for v in range(-127, 128) if v]) for x in range(3)] for y in range(3)]
          for f in range(filters)] for c in range(channels)]
    block = math.ceil(L.used_wght_per_PE / params.PARALLEL_MACS)
    zero_words = 0
    for rep in range(L.needed_wght_transmissions):
        mapper = wsm.ConvWghtStreamMapper(params, L, rep, w, 0)
        for cx in range(params.Clusters_X):
            for cy in range(params.Clusters_Y):
                for router in range(params.Wght_Routers):
                    if L.computing_mx[cx][cy][router][0] != 1:
                        continue
                    dense = mapper.write_dense_wght_data_storage(cx, cy, router)
                    assert mapper.write_wght_data_storage(cx, cy, router) == dense
                    words = mapper.create_pe_data_wght_stream(dense)
                    assert len(words) == block
                    zero_words += words.count(0)
                    got = [[(word >> (8 * i)) & 0xFF for i in range(params.PARALLEL_MACS)] for word in words]
                    want = [[e[0] & 0xFF for e in word] for word in dense[:block]]
                    assert got == want
    assert channels == 1 or zero_words > 0          # channel 0 is all zero: its words are sent, not skipped


@pytest.mark.parametrize("width,channels,filters", [(20, 2, 8), (8, 8, 16), (8, 4, 32)])
@pytest.mark.parametrize("zeros", [0.0, 0.3, "channel 1"])
def test_mapper_dense_layout_in_raw_mode(width, channels, filters, zeros, monkeypatch):
    """OPENEYE_WGHT_LAYOUT=dense (step 2 of P1): the same blocks as the zero-compressed layout when no weight is zero,
    otherwise every weight in its slot; through the RTL model in raw mode the PE gets the layer's weights. Without
    OPENEYE_FORCE_RAW_WGHT a block with an all-zero word is refused."""
    params, L = mapper_layer(width, channels, filters, monkeypatch)
    rng = random.Random(4)
    w = [[[[0 if (zeros == "channel 1" and c == 1) or (zeros != "channel 1" and rng.random() < zeros)
            else nonzero(rng) for x in range(3)] for y in range(3)]
          for f in range(filters)] for c in range(channels)]
    block = math.ceil(L.used_wght_per_PE / params.PARALLEL_MACS)
    column_length = math.ceil(L.used_wght_per_PE / L.used_iact_per_PE)
    filters_w = (L.used_psum_per_PE & 0x3F) or 16
    zero_words = 0
    for rep in range(L.needed_wght_transmissions):
        mapper = wsm.ConvWghtStreamMapper(params, L, rep, w, 0)
        for cx in range(params.Clusters_X):
            for cy in range(params.Clusters_Y):
                for router in range(params.Wght_Routers):
                    if L.computing_mx[cx][cy][router][0] != 1:
                        continue
                    monkeypatch.delenv("OPENEYE_WGHT_LAYOUT", raising=False)
                    compressed = mapper.write_wght_data_storage(cx, cy, router)
                    dense = mapper.write_dense_wght_data_storage(cx, cy, router)
                    wpc = math.ceil(column_length / 2)
                    want = [[e[0] for word in dense[k * wpc:(k + 1) * wpc] for e in word][:column_length]
                            for k in range(L.used_iact_per_PE)]
                    monkeypatch.setenv("OPENEYE_WGHT_LAYOUT", "dense")
                    monkeypatch.setenv("OPENEYE_FORCE_RAW_WGHT", "1")
                    spad = mapper.write_wght_data_storage(cx, cy, router)
                    if zeros == 0.0:
                        assert spad == compressed
                    words = mapper.create_pe_data_wght_stream(spad)
                    assert len(words) == block
                    zero_words += words.count(0)
                    addr, data, data_words = wpm.load(words, filters_w, extra_word=EXTRA_WORD, raw_mode=True)
                    got, pointers = wpm.read_columns(addr, data, L.used_iact_per_PE, column_length)
                    assert got == want
                    assert data_words >= pointers[L.used_iact_per_PE - 1]
                    monkeypatch.delenv("OPENEYE_FORCE_RAW_WGHT")
                    if words.count(0):
                        with pytest.raises(ValueError):
                            mapper.write_wght_data_storage(cx, cy, router)
    monkeypatch.delenv("OPENEYE_WGHT_LAYOUT", raising=False)
    assert (zero_words > 0) == (zeros != 0.0)
