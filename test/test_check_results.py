# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""generic_test_utils.check_results: the line-by-line check of the DUT stream against dma_stream_ref.txt, and the
psum slots without an output it skips when it gets their positions (bug #9: the slot after a 7-wide row)."""
import types

from open_eye import generic_test_utils as gtu

PARAMS = types.SimpleNamespace(DMA_BITWIDTH=64, DATA_PSUM_BITWIDTH=20)


def line(*slots, upper=0):
    """A 64-bit conv stream word: slot 0 in the low 20 bits, slot 1 above it, then the unused upper bits."""
    value = upper << 40
    for k, v in enumerate(slots):
        value |= (v & 0xFFFFF) << (20 * k)
    return format(value, "064b") + "\n"


def check(tmp_path, ref, out, positions=None):
    (tmp_path / "ref.txt").write_text("".join(ref))
    (tmp_path / "out.txt").write_text("".join(out))
    return gtu.check_results(PARAMS, str(tmp_path / "ref.txt"), str(tmp_path / "out.txt"), slot_positions=positions)


# a 7-wide row in 4 words of 2 slots: x = 0..6 and one padding slot
ROW = [[0, x, 0] for x in range(7)] + [None]
REF = [line(1, 2), line(3, 4), line(5, 6), line(7, 0)]


def test_equal_streams_pass(tmp_path):
    assert check(tmp_path, REF, REF)
    assert check(tmp_path, REF, REF, ROW)


def test_padding_slot_difference(tmp_path, caplog):
    out = REF[:3] + [line(7, 123)]          # the idle PE's psum in the padding slot
    assert not check(tmp_path, REF, out)    # the plain check: a difference (the old xfail of bug #9)
    assert check(tmp_path, REF, out, ROW)   # with the positions: no output there, not compared
    assert "only in psum slots without an output" in caplog.text


def test_real_slot_difference_still_fails(tmp_path):
    assert not check(tmp_path, REF, REF[:3] + [line(8, 0)], ROW)        # x = 6 wrong
    assert not check(tmp_path, REF, REF[:3] + [line(8, 123)], ROW)      # x = 6 wrong and padding slot non-zero
    assert not check(tmp_path, REF, [line(1, 9)] + REF[1:], ROW)        # x = 1 wrong


def test_upper_bits_are_still_compared(tmp_path):
    assert not check(tmp_path, REF, REF[:3] + [line(7, 0, upper=1)], ROW)


def test_positions_must_fit_the_file(tmp_path):
    assert not check(tmp_path, REF, REF, ROW[:-1])


def test_missing_lines_fail(tmp_path):
    assert not check(tmp_path, REF, REF[:2], ROW)
