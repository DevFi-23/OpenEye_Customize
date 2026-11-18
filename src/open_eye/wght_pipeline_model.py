# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Cycle model of hdl/data_pipeline_wght.v for one weight load (sparse mode, PARALLEL_MACS = 2, raw_mode_i = 0 or 1).

Only the registers that reach the SPad write ports are modelled, with the RTL widths (5-bit overhead registers,
4-bit tags, 7-bit word count). It matched the RTL write for write on 336 PE weight loads of the bug #22 investigation
(doc/experiments/2026-10-24_bug22/validate_model.py). Used by the tests of the conv weight encoding, which decode the
SPads the way the PE reads them: column k = data words [addr[k-1], addr[k]), inside a column position += overhead,
weight[position] = value, position += 1.
"""


def load(words, filters_w, extra_word=0, count_bits=7, raw_mode=False):
    """Feed one PE's words on consecutive cycles (plus the word the PE captures after its block).

    raw_mode: the RTL input raw_mode_i (today FC | GEMM): an all-zero word is stored and counted like any other word
    instead of being skipped (the three "!= 0 | raw_mode_i" conditions of the RTL).
    Returns (address SPad {addr: data}, data SPad {addr: word}, second_spad_words)."""
    F = 16 if filters_w == 0 else filters_w
    s = dict(enable_delay=0, data2=0, ov=0, ov_delay=0, ov_new=0, over_end=0, a_addr=0, a_data=0, a_en=0,
             d_addr=0, d_data=0, d_en=0, cnt=0, d_words=0, compute_sent=1)
    addr_spad, data_spad = {}, {}
    for en, d in [(1, w) for w in words] + [(1, extra_word), (0, 0), (0, 0), (0, 0)]:
        n = dict(s, a_en=0, a_data=0, d_en=0, enable_delay=en, data2=d, over_end=0)
        tag = (s["data2"] >> 8) & 0xF
        if tag != 0 and s["ov_delay"] + tag >= F:
            tag_out = (tag + s["ov_delay"] - F - s["over_end"]) & 0xF
        else:
            tag_out = tag
        if s["enable_delay"] and (s["data2"] != 0 or raw_mode):          # delayed write path
            n["a_en"] = n["d_en"] = 1
            n["d_data"] = (s["data2"] & 0xFFF0FF) | (tag_out << 8)
            if s["ov_new"] >= F:
                n["a_addr"] = s["a_addr"] + 1
            if s["d_data"] != 0 or (raw_mode and s["d_en"]):
                n["d_addr"] = s["d_addr"] + 1
            n["a_data"] = s["cnt"]
            n["d_words"] = s["d_addr"] + 2
        else:
            n["d_addr"] = 0
        if en and (d != 0 or raw_mode):                     # capture path
            t0, t1 = (d >> 8) & 0xF, (d >> 20) & 0xF
            ow = (t0 + t1) & 0xF
            n["compute_sent"] = 0
            if s["compute_sent"]:
                n["d_words"] = 0
            n["ov_delay"] = s["ov"]
            n["cnt"] = (s["cnt"] + 1) & ((1 << count_bits) - 1)
            n["ov"] = (s["ov"] + 2 + ow) & 0x1F
            n["ov_new"] = s["ov"]
            if s["ov"] + t0 >= F:
                n["ov"] = (2 + s["ov"] + ow - F) & 0x1F
                if s["ov"] == F + 1:
                    n["ov"] = (2 + s["ov"] + ow - F - 1) & 0x1F
                    n["over_end"] = 1
                if s["ov"] < F:
                    n["ov_new"] = (s["ov"] + 2 + t0) & 0x1F
        if n["a_en"]:
            addr_spad[n["a_addr"]] = n["a_data"]
        if n["d_en"]:
            data_spad[n["d_addr"]] = n["d_data"]
        s = n
    return addr_spad, data_spad, s["d_words"]


def read_columns(addr_spad, data_spad, columns, column_length):
    """The weights the PE reads for its first `columns` columns (None for a missing column pointer)."""
    pointers = [addr_spad[a] for a in sorted(addr_spad)]
    out = []
    for k in range(columns):
        if k >= len(pointers):
            out.append(None)
            continue
        weights, pos = [0] * column_length, 0
        for a in range(pointers[k - 1] if k else 0, pointers[k]):
            word = data_spad.get(a, 0)
            for entry in (word & 0xFFF, word >> 12):
                value, overhead = entry & 0xFF, entry >> 8
                pos += overhead
                if pos < column_length:
                    weights[pos] = value - 256 if value >= 128 else value
                elif value:
                    weights.append(("beyond", pos, value))
                pos += 1
        out.append(weights)
    return out, pointers
