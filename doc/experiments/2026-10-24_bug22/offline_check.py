"""Offline end-to-end check of the conv weight path: repository mapper -> serializer -> data_pipeline_wght model
(validated against the RTL) -> the SPads as the PE reads them -> compared with the layer's weights.

check(w, W, H, skip, encoder=None) -> report dict
  w        weights [c][f][ky][kx] (ints), layer W x H x C -> F, 3x3, platform of the cocotb_fpga tests
  skip     WghtStreamMapper.SKIP_ZERO_WORDS (True = repository default)
  encoder  optional replacement for the per-PE entry list (a function of the dense column list), to test fixes

Intended columns come from the mapper itself, run on unique ids instead of weights (dense: every column has exactly
filters_per_calculation entries); the delivered words per PE follow the serializer (word i of every PE, PE (0,0,0)'s
length) and the RTL takes trans_cycles_wght DMA words (= the dense length per PE) whatever the stream has."""
import math
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapper_words import layer
from open_eye import wght_stream_mapper as wsm
from wght_pipeline_model import run, final


def pe_spads(mp, cx, cy, r):
    return mp.write_wght_data_storage(cx, cy, r)


def entries_to_words(mp, spad_entries):
    """Pack [[v, oh], [v, oh]] words like create_pe_data_wght_stream, keeping zero words (positions matter)."""
    old = mp.SKIP_ZERO_WORDS
    mp.SKIP_ZERO_WORDS = False
    try:
        return mp.create_pe_data_wght_stream(spad_entries)
    finally:
        mp.SKIP_ZERO_WORDS = old


def check(w, W, H, skip=True, encoder=None, max_examples=3, extra_word=0x200044):
    C, F_all = len(w), len(w[0])
    params, L = layer(W, H, C, F_all)
    ids = [[[[1 + ((c * F_all + f) * 3 + y) * 3 + x for x in range(3)] for y in range(3)] for f in range(F_all)] for c in range(C)]
    flat = {1 + ((c * F_all + f) * 3 + y) * 3 + x: w[c][f][y][x] for c in range(C) for f in range(F_all) for y in range(3) for x in range(3)}
    fpc = math.ceil(L.used_wght_per_PE / L.used_iact_per_PE) * L.different_kernels_per_calculation
    M0 = L.used_psum_per_PE
    filters_w = (M0 & 0x3F) or 16                          # 6-bit config field, 0 -> 16 in the RTL
    n_dense = math.ceil(L.used_wght_per_PE / params.PARALLEL_MACS)
    rep_report = {"fpc": fpc, "dkpc": L.different_kernels_per_calculation, "reps": L.needed_wght_transmissions, "M0": M0, "filters_w": filters_w, "dense_words": n_dense, "pes": 0, "bad_pes": 0,
                  "stream_short": 0, "truncated_pes": 0, "examples": []}
    for rep in range(L.needed_wght_transmissions):
        mp_id = wsm.ConvWghtStreamMapper(params, L, rep, ids, 0)
        mp = wsm.ConvWghtStreamMapper(params, L, rep, w, 0)
        mp.SKIP_ZERO_WORDS = skip
        pes = [(cx, cy, r) for cx in range(params.Clusters_X) for cy in range(params.Clusters_Y)
               for r in range(params.Wght_Routers) if L.computing_mx[cx][cy][r][0] == 1]
        per_pe_sent, intended = {}, {}
        for pe in pes:
            dense_words = pe_spads(mp_id, *pe)
            col_len = fpc // L.different_kernels_per_calculation      # entries per column (filters step by dkpc)
            wpc = math.ceil(col_len / 2)                              # every column starts at a word boundary
            cols = [[flat.get(e[0], 0) for word in dense_words[k * wpc:(k + 1) * wpc] for e in word][:col_len]
                    for k in range(L.used_iact_per_PE)]
            intended[pe] = cols
            if encoder is None:
                spad = pe_spads(mp, *pe)
            else:
                spad = encoder(cols, params, n_dense)
            words = mp.create_pe_data_wght_stream(spad)          # honours SKIP_ZERO_WORDS like the repository
            per_pe_sent[pe] = words
        first_len = len(per_pe_sent[pes[0]])
        if first_len != n_dense:
            rep_report["stream_short"] += 1
        for pe in pes:
            rep_report["pes"] += 1
            sent = per_pe_sent[pe]
            # serializer: word i of every PE for i < len(PE (0,0,0)); missing words become 0
            delivered = [sent[i] if i < len(sent) else 0 for i in range(first_len)]
            if len(sent) > first_len:
                rep_report["truncated_pes"] += 1
            # the RTL takes dense_words words per PE; with a short stream the rest is not weight data
            delivered = (delivered + [None] * n_dense)[:n_dense]
            if None in delivered:
                rep_report["bad_pes"] += 1
                continue
            # the PE captures one word beyond its block (worst case: a non-zero word of another PE)
            a_w, d_w = run(delivered + [extra_word], filters_w)
            d_words = run.words[1]
            addr, data = final(a_w), final(d_w)
            ptr = [addr[a] for a in sorted(addr)]
            got_cols, problems = [], []
            for k, want in enumerate(intended[pe]):
                if k >= len(ptr):
                    problems.append(f"col {k} missing (want {want})")
                    continue
                start = ptr[k - 1] if k else 0
                got, pos, ent = [0] * len(want), 0, []
                for a in range(start, ptr[k]):
                    word = data.get(a, 0)
                    for sub in (word & 0xFFF, word >> 12):
                        v, oh = sub & 0xFF, sub >> 8
                        v = v - 256 if v >= 128 else v
                        ent.append((v, oh))
                        pos += oh
                        if pos < len(want):
                            got[pos] = v
                        elif v != 0:
                            got.append(("beyond", pos, v))
                        pos += 1
                if got != want:
                    problems.append(f"col {k}: entries {ent} -> {got}, want {want}")
            if ptr and len(ptr) >= len(intended[pe]) and d_words < ptr[len(intended[pe]) - 1]:
                problems.append(f"second_spad_words {d_words} < {ptr[len(intended[pe]) - 1]} data words: the PE hangs")
            if problems:
                rep_report["bad_pes"] += 1
                if len(rep_report["examples"]) < max_examples:
                    rep_report["examples"].append((rep, pe, problems[:3]))
    return rep_report
