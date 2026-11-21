"""Dense DMA capture against explicit wire-order fixtures, without a simulator.

One psum pass of a Dense layer carries Clusters_X x used_psum_per_PE outputs (at most 16 x Clusters_X). A layer with
more outputs sends output_cycles = needed_psum_transmissions passes one after another, in the order of the psum buffer
and of make_ref: pass r, buffer address a, cluster column c, so beat r*CX*P + a*CX + c carries output r*CX*P + c*P + a.
Until 2026-11-21 the fixtures below lacked output_cycles / needed_psum_transmissions (fields of upstream 23be043), and
compare_stream_Dense placed every pass after the first wrong (bug #21, doc/experiments/2026-11-21_test_dense_output.md).
"""
import asyncio
import logging
import random
from types import SimpleNamespace as NS

import pytest

from open_eye import rtl_test_utils as rtl
from open_eye import test_utils_main as tum

MASK = (1 << 20) - 1


def fake_dut(monkeypatch, words):
    """A DUT whose data_dma_o walks through words, one per Timer, with enable_dma_o high until the end."""
    class Word(int):
        def __getitem__(self, bits):
            return (self >> bits.stop) & ((1 << (bits.start - bits.stop + 1)) - 1)
    class Signal:
        @property
        def value(self):
            value = words[position[0]]
            return Word(value) if isinstance(value, int) else value
    class Enable:
        @property
        def value(self):
            return int(position[0] < len(words))
    position = [0]
    async def timer(*args, **kwargs):
        position[0] += 1
    monkeypatch.setattr(rtl, "Timer", timer)
    monkeypatch.setattr(rtl.cocotb, "start_soon", lambda coro: coro.close())
    monkeypatch.delenv("DUMP_PSUM_BUFFERS", raising=False)
    return NS(data_dma_o=Signal(), enable_dma_o=Enable(), ready_dma_i=NS(),
              _log=logging.getLogger("dense_capture_test"))


def decode(monkeypatch, words, layer, params, count, repetition=0):
    """Run compare_stream_Dense over words; returns the output list it fills (count entries)."""
    dram = NS(fmap=[None, [None] * count])
    asyncio.run(rtl.compare_stream_Dense(
        NS(clk_cycle=20, clk_cycle_unit="ns"), fake_dut(monkeypatch, words), 0, repetition,
        layer, params, NS(), dram, logging.INFO))
    return dram.fmap[1]


def capture(monkeypatch, words, columns, count, *, repetition=0, tiles=1, passes=1):
    per_column = -(-count // (columns * passes))
    layer = NS(used_psum_per_PE=per_column, iact_transmissions_pe=1,
               psum_transmissions_pe=tiles, used_Y_cluster=2,
               psum_output_words=per_column * columns * passes, output_cycles=passes)
    params = NS(Clusters_X=columns, Clusters_Y=2, DATA_PSUM_BITWIDTH=20,
                DMA_BITWIDTH=64, PSUM_Trans_Bitwidth=40)
    return decode(monkeypatch, words, layer, params, count * tiles, repetition)


@pytest.mark.parametrize("columns,values,wire_order", [
    # The reported failure retained even-numbered outputs, then zeros.
    (1, [17, -4516, 5251, -9954, -7288, -10952, -2542, 4140, -3736, 29],
        [17, -4516, 5251, -9954, -7288, -10952, -2542, 4140, -3736, 29]),
    (2, [0, -1, 524287, -524288, 42, -7], [0, -524288, -1, 42, 524287, -7]),
    (3, [11, 12, 13, 14, 15, 16], [11, 13, 15, 12, 14, 16]),
    # An odd filter count leaves a padding slot in the last column.
    (2, [11, 12, 13, 14, 15], [11, 14, 12, 15, 13, 0]),
])
def test_dense_capture_wire_order(monkeypatch, columns, values, wire_order):
    words = [value & MASK for value in wire_order]
    assert capture(monkeypatch, words, columns, len(values)) == values


@pytest.mark.parametrize("columns,passes,values,wire_order", [
    # Two passes of 2 columns x 2 addresses: pass 0 holds outputs 0-3, pass 1 outputs 4-7 (bug #21: the old decoder
    # put outputs 4 and 5 in slots 2 and 3 and outputs 6 and 7 in slots 4 and 5)
    (2, 2, [10, 11, 12, 13, 14, 15, 16, 17], [10, 12, 11, 13, 14, 16, 15, 17]),
    # Seven outputs: the padding slot is the last one of the last pass
    (2, 2, [11, -12, 13, -14, 15, -16, 17], [11, 13, -12, -14, 15, 17, -16, 0]),
    (2, 3, list(range(12)), [0, 2, 1, 3, 4, 6, 5, 7, 8, 10, 9, 11]),
    (1, 3, [1, -2, 3, -4, 5], [1, -2, 3, -4, 5, 0]),
    (4, 2, list(range(100, 116)),
        [100, 102, 104, 106, 101, 103, 105, 107, 108, 110, 112, 114, 109, 111, 113, 115]),
    (2, 2, [524287, -524288, -1, 0, 42, -7], [524287, -1, -524288, 0, 42, 0, -7, 0]),
])
def test_dense_capture_passes(monkeypatch, columns, passes, values, wire_order):
    words = [value & MASK for value in wire_order]
    assert capture(monkeypatch, words, columns, len(values), passes=passes) == values


@pytest.mark.parametrize("words", [[1, 2, 3], [1, 2, 3, 4, 5]])
def test_dense_capture_rejects_wrong_length(monkeypatch, words):
    with pytest.raises(AssertionError, match="Dense DMA"):
        capture(monkeypatch, words, 1, 4)


@pytest.mark.parametrize("count", [7, 9])
def test_dense_capture_passes_rejects_wrong_length(monkeypatch, count):
    # two passes of 2 x 2 are 8 beats
    with pytest.raises(AssertionError, match="Dense DMA"):
        capture(monkeypatch, list(range(1, count + 1)), 2, 8, passes=2)


def test_dense_capture_passes_rejects_nonzero_padding(monkeypatch):
    with pytest.raises(AssertionError, match="padding output is nonzero"):
        capture(monkeypatch, [11, 13, 12, 14, 15, 17, 16, 5], 2, 7, passes=2)


def test_dense_capture_rejects_unknown_data(monkeypatch):
    with pytest.raises(ValueError):
        capture(monkeypatch, ["xxxx", 2], 1, 2)


def test_dense_capture_output_tile_offset(monkeypatch):
    assert capture(monkeypatch, [11, 13, 12, 14], 2, 4,
                   repetition=1, tiles=2) == [None] * 4 + [11, 12, 13, 14]


def reference_words(monkeypatch, tmp_path, params, layer, values):
    """The Dense DMA words make_ref writes for these outputs (layer 0, repetition 0)."""
    monkeypatch.chdir(tmp_path)
    for name in ("write_weight_file", "write_iact_file", "write_psum_file"):
        monkeypatch.setattr(tum, name, lambda *args: None)
    tum.make_ref(params, layer, 0, None, dict(enumerate(values)))
    lines = (tmp_path / "demo/layer_0_0/dma_stream_ref.txt").read_text().splitlines()
    assert all(len(line) == params.DMA_BITWIDTH for line in lines)
    return [int(line, 2) for line in lines]


@pytest.mark.parametrize("columns,passes,expected", [
    (1, 1, [11, -12, 13, -14, 15]),
    (2, 1, [11, -14, -12, 15, 13, 0]),
    (3, 1, [11, 13, 15, -12, -14, 0]),
    (2, 2, [11, 13, -12, -14, 15, 0, 0, 0]),
    (1, 3, [11, -12, 13, -14, 15, 0]),
])
def test_dense_serial_reference_words(monkeypatch, tmp_path, columns, passes, expected):
    params = NS(SERIAL=1, Clusters_X=columns, DMA_BITWIDTH=64, DATA_PSUM_BITWIDTH=20)
    layer = NS(layer_name="Dense", used_psum_per_PE=-(-5 // (columns * passes)),
               needed_total_transmissions=1, iact_transmissions_pe=1,
               psum_transmissions_pe=1, needed_psum_transmissions=passes)
    words = reference_words(monkeypatch, tmp_path, params, layer, [11, -12, 13, -14, 15])
    assert words == [v & MASK for v in expected]


# --- make_ref -> compare_stream_Dense round trip with the LayerParameters of real Dense layers ----------------------

PLATFORM = {"CLUSTER_ROWS": "2", "CLUSTER_COLUMNS": "2", "NUM_GLB_IACT": "1", "NUM_GLB_PSUM": "4",
            "NUM_GLB_WGHT": "3", "DATA_PSUM_BITWIDTH": "20", "TRANS_WORDS": "8", "BRANCHES": "1",
            "BUFFER_WIDTH": "12", "QUANT_AMOUNT": "128", "DMA_BITWIDTH": "64", "RAM_CELLS": "32"}


@pytest.mark.parametrize("cluster_columns,cluster_rows,inputs,outputs,passes", [
    (2, 2, 64, 10, 1),
    (2, 2, 64, 32, 1),
    (2, 2, 64, 34, 2),      # 6 padding slots at the end of pass 1
    (2, 2, 64, 40, 2),      # bug #21 as recorded: only the first 10 outputs were right
    (2, 2, 16, 64, 2),
    (2, 2, 3136, 40, 2),
    (2, 1, 64, 40, 2),
    (2, 4, 64, 100, 4),
    (1, 2, 64, 40, 3),
])
def test_dense_round_trip(monkeypatch, tmp_path, cluster_columns, cluster_rows, inputs, outputs, passes):
    tf = pytest.importorskip("tensorflow")
    from open_eye import layer_parameters as lp
    from open_eye import open_eye_parameters as oep
    for key, value in dict(PLATFORM, CLUSTER_COLUMNS=str(cluster_columns), CLUSTER_ROWS=str(cluster_rows)).items():
        monkeypatch.setenv(key, value)
    params = oep.get_oep(1)
    keras_layer = tf.keras.models.Sequential([tf.keras.Input((inputs,)), tf.keras.layers.Dense(outputs)]).layers[0]
    layer = lp.LayerParameters([0], keras_layer, params, 0, 1)
    assert layer.send_values_out == 1
    assert layer.needed_psum_transmissions == layer.output_cycles == passes
    slots = params.Clusters_X * layer.used_psum_per_PE * passes
    assert layer.psum_output_words == slots >= outputs
    rng = random.Random(outputs * 100 + inputs)
    values = [rng.randrange(-(1 << 19), 1 << 19) for _ in range(outputs)]
    words = reference_words(monkeypatch, tmp_path, params, layer, values)
    assert len(words) == slots
    assert decode(monkeypatch, words, layer, params, outputs) == values
