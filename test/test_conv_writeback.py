# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Write-back of a convolution into the iact buffer with 2 or 4 lanes (bug #25), on the cycle model of the RTL.

The psum FSM delivers, per transposition of 4 cycles, the channels c0..c3 of the pixels in the lanes (the GLBs of one
cluster, NUM_GLB_PSUM of them), cluster after cluster along a row; a row is read as iact_x_add_up pixels, of which the
first iact_size_x are activations (this read order was seen in RTL simulation,
doc/experiments/2026-10-26_bug25_glb_psum2.md). The next layer reads groups of 4 channels per pixel. The RTL before the
fix used the lane count as the group length (channels == lanes in the model).
"""
import pytest

from open_eye.writeback_model import pack


def conv_rows(width, add_up, rows, lanes, channels=4):
    pixels = [(r, x) for r in range(rows) for x in range(add_up)]

    def lane_value(s, a):
        i = lanes * (s // 4) + a
        if i >= len(pixels):
            return -2
        r, x = pixels[i]
        return -1 if x >= width else 10 * (r * width + x) + s % 4

    limit = len(pixels) * 4 // lanes + 11            # fsm_psum_limit of layer_parameters: ceil(x * F * y / lanes) + 11
    out = pack(lane_value, limit, lanes, 4, channels=channels, iact_size_x=width, add_up=add_up)
    return [v for row in out for v in row]


def expected(width, rows):
    return [10 * p + ch for p in range(rows * width) for ch in range(4)]


@pytest.mark.parametrize("lanes", [2, 4])
@pytest.mark.parametrize("width,add_up", [(6, 8), (7, 8), (8, 8), (14, 16), (28, 32)])
def test_pixels_in_order(width, add_up, lanes):
    """Every pixel with its 4 channels, rows without their padding pixels."""
    got = conv_rows(width, add_up, 4, lanes)
    want = expected(width, 4)
    assert got[:len(want)] == want


def test_old_grouping_with_two_lanes():
    """Before the fix: groups of 2 channels, the two pixels of a cluster interleaved (as in the RTL simulation)."""
    got = conv_rows(8, 8, 2, 2, channels=2)
    assert got[:8] == [0, 1, 10, 11, 2, 3, 12, 13]
    assert got[:len(expected(8, 2))] != expected(8, 2)


def test_old_grouping_with_four_lanes_is_right():
    """With 4 lanes the group length was 4 already: the fix leaves that case alone."""
    want = expected(28, 4)
    assert conv_rows(28, 32, 4, 4, channels=4)[:len(want)] == want
