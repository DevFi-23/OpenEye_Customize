# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""The weight staging buffer check (bug #29, doc/experiments/2026-11-03_table3_cr1.md): rows a weight stream fills and
the refusal of a layer that does not fit 2^BUFFER_WIDTH_WGHT rows."""
import types

import pytest

from open_eye import layer_parameters as lp
from open_eye import open_eye_parameters


def params(cluster_rows=1, num_glb_wght=3, dma=64, bww=12):
    return types.SimpleNamespace(Clusters=2 * cluster_rows, WGHT_Trans_Bitwidth=24, NUM_GLB_WGHT=num_glb_wght,
                                 DMA_BITWIDTH=dma, BUFFER_WIDTH_WGHT=bww)


def test_words_per_row():
    # WGHT_ONE_WORD_ALL_RAM of OpenEye_FPGA.v: ceil(CLUSTERS * 24 * NUM_GLB_WGHT / DMA_BITWIDTH)
    assert lp.wght_buffer_rows(params(1, 3), 3) == 1                  # 144 bits: 3 words
    assert lp.wght_buffer_rows(params(1, 4), 3) == 1                  # 192 bits: 3 words
    assert lp.wght_buffer_rows(params(2, 3), 5) == 1                  # 288 bits: 5 words
    assert lp.wght_buffer_rows(params(8, 4), 24) == 1                 # 1536 bits: 24 words
    assert lp.wght_buffer_rows(params(1, 3, dma=32), 5) == 1          # 144 bits: 5 words at DMA 32


def test_paper_dense_rows():
    # load_wght words of Dense 1568 -> 32 measured in Table 3 (doc/perf/paper_table3_2026-11-02)
    assert lp.wght_buffer_rows(params(1, 3), 12672) == 4224           # CR 1 Y 3: 44 K passes x 96 rows
    assert lp.wght_buffer_rows(params(1, 4), 9504) == 3168            # CR 1 Y 4
    assert lp.wght_buffer_rows(params(2, 3), 10560) == 2112           # CR 2 Y 3


def test_check_at_the_limit():
    assert lp.check_wght_buffer(params(bww=12), 3 * 4096) == 4096     # exactly full
    with pytest.raises(NotImplementedError, match="4097 rows"):
        lp.check_wght_buffer(params(bww=12), 3 * 4096 + 1, "Dense")
    with pytest.raises(NotImplementedError, match="BUFFER_WIDTH_WGHT=12"):
        lp.check_wght_buffer(params(bww=12), 12672)                   # the failing Table 3 layer
    assert lp.check_wght_buffer(params(bww=13), 12672) == 4224        # fits the 13-bit buffer
    with pytest.raises(NotImplementedError):
        lp.check_wght_buffer(params(bww=13), 3 * 8192 + 1)


def test_default_depth(monkeypatch):
    monkeypatch.delenv("BUFFER_WIDTH_WGHT", raising=False)
    assert open_eye_parameters.get_oep(1).BUFFER_WIDTH_WGHT == 13


def test_iact_buffer_check():
    # bug #37: the iact buffer fields are IACT_BUFFER_ADDR_WIDTH = 13 bits (were 12, so 4,096 words arrived as 0)
    layer = types.SimpleNamespace(layer_name="Conv", iact_buffer_words_per_write=4096)
    assert lp.check_iact_buffer(layer) == 4096                        # conv 14 x 14 x 32 at CR 1 X 2
    layer.iact_buffer_words_per_write = 8191
    assert lp.check_iact_buffer(layer) == 8191                        # the largest value of the field
    layer.iact_buffer_words_per_write = 8192
    with pytest.raises(NotImplementedError, match="8192 words per pass"):
        lp.check_iact_buffer(layer)
