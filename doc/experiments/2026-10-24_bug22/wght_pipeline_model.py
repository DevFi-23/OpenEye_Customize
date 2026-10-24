"""Cycle model of hdl/data_pipeline_wght.v (sparse mode, PARALLEL_MACS = 2, raw_mode_i = 0) for one weight load.

Only the registers that reach the SPad write ports are modelled (overhead_reg, overhead_delay_reg,
overhead_new_calc_reg, over_ending, data_storage_2, enable_delay, first/second SPad address and data, the running word
count first_spad_data_delay), with the widths of the RTL (5-bit overhead registers, 4-bit overhead_w / tags, 7-bit
first_spad_data). Input: the 24-bit words of one PE, delivered on consecutive cycles (as the RTL dump shows), starting
from the state after compute_i. Output: the address SPad writes and data SPad writes in order, as (addr, data)."""

def fields(word):
    lo, hi = word & 0xFFF, (word >> 12) & 0xFFF
    return lo >> 8, hi >> 8                       # 4-bit tags of sub-word 0 and 1


def run(words, filters_w, first_data_bits=7, idle_after=3, seq=None):
    F = 16 if filters_w == 0 else filters_w
    s = dict(enable_delay=0, data2=0, ov=0, ov_delay=0, ov_new=0, over_end=0, a_addr=0, a_data=0, a_en=0,
             d_addr=0, d_data=0, d_en=0, cnt=0, a_words=0, d_words=0, compute_sent=1)
    a_writes, d_writes = [], []
    if seq is None:
        seq = [(1, w) for w in words] + [(0, 0)] * idle_after
    for en, d in seq:
        n = dict(s)
        n["a_en"] = 0
        n["a_data"] = 0
        n["d_en"] = 0
        n["enable_delay"] = en
        n["data2"] = d
        n["over_end"] = 0
        # combinational overhead_output for the word in data_storage_2
        tag = (s["data2"] >> 8) & 0xF
        if tag != 0 and s["ov_delay"] + tag >= F:
            ov_out = (tag + s["ov_delay"] - F - s["over_end"]) & 0xF
        else:
            ov_out = tag
        premade = (s["data2"] & ~0xF00 & 0xFFFFFF) | (ov_out << 8)
        # delayed write path
        if s["enable_delay"] and s["data2"] != 0:
            n["a_en"] = 1
            n["d_en"] = 1
            n["d_data"] = premade
            if s["ov_new"] >= F:
                n["a_addr"] = s["a_addr"] + 1
                n["a_words"] = s["a_addr"] + 2
            if s["d_data"] != 0:
                n["d_addr"] = s["d_addr"] + 1
            n["a_data"] = s["cnt"]
            n["d_words"] = s["d_addr"] + 2
        else:
            n["d_addr"] = 0
        # capture path
        if en and d != 0:
            n["compute_sent"] = 0
            if s["compute_sent"]:
                n["d_words"] = 0
            t0, t1 = fields(d)
            ow = (t0 + t1) & 0xF
            n["ov_delay"] = s["ov"]
            n["cnt"] = (s["cnt"] + 1) & ((1 << first_data_bits) - 1)
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
            a_writes.append((n["a_addr"], n["a_data"]))
        if n["d_en"]:
            d_writes.append((n["d_addr"], n["d_data"]))
        s = n
    run.words = (s["a_words"], s["d_words"])         # first_spad_words_o, second_spad_words_o after the load
    return a_writes, d_writes


def final(writes):
    out = {}
    for a, v in writes:
        out[a] = v
    return out
