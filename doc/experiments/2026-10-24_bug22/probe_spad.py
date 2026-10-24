"""Bug #22 probe: unique-valued conv weights with a zero pattern (B22_PATTERN), and a dump of every write into the weight
address SPad and the weight data SPad of every PE (B22_DUMP, json). Wraps the unmodified OpenEye_FPGA_tb; the weights are set
where channel_pad.fill_padding_channels runs (after every data hook), so the reference and the streams use them.

B22_NOSKIP=1 turns WghtStreamMapper.SKIP_ZERO_WORDS off. Patterns: none | chan1 | chan1_f0 | filter0 | rand<p> (seeded) | list:c.f.y.x,c.f.y.x,... (zero exactly these weights)."""
import json
import os
import random

import cocotb
from cocotb.triggers import FallingEdge

import OpenEye_FPGA_tb as tb
import open_eye.channel_pad as cp

_orig = cp.fill_padding_channels
VALS = list(range(1, 128)) + [-v for v in range(1, 129)]


def unique_value(c, f, y, x, F):
    return VALS[(((c * F + f) * 3 + y) * 3 + x) % len(VALS)]


def install_encoder():
    """B22_ENCODER=new: replace the conv weight SPad builder by encoder.encode (scratch prototype of the fix)."""
    import math
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import open_eye.wght_stream_mapper as wsm
    from encoder import encode
    orig = wsm.ConvWghtStreamMapper.write_wght_data_storage

    def write_wght_data_storage(self, cl_x, cl_y, router):
        w = self.dram_weights
        C, F, KY, KX = len(w), len(w[0]), len(w[0][0]), len(w[0][0][0])
        ids = [[[[1 + ((c * F + f) * KY + y) * KX + x for x in range(KX)] for y in range(KY)] for f in range(F)]
               for c in range(C)]
        self.dram_weights = ids
        try:
            dense = orig(self, cl_x, cl_y, router)        # dense column order of this PE, as ids
        finally:
            self.dram_weights = w
        L = self.layer_params
        col_len = math.ceil(L.used_wght_per_PE / L.used_iact_per_PE)       # entries per column
        wpc = math.ceil(col_len / 2)                     # every column starts at a word boundary
        flat = lambda i: (lambda c, r: w[c // F][c % F][r // KX][r % KX])(*divmod(i - 1, KY * KX)) if i else 0
        cols = [[flat(e[0]) for word in dense[k * wpc:(k + 1) * wpc] for e in word][:col_len]
                for k in range(L.used_iact_per_PE)]
        return encode(cols, self.params, math.ceil(L.used_wght_per_PE / self.params.PARALLEL_MACS))

    wsm.ConvWghtStreamMapper.write_wght_data_storage = write_wght_data_storage
    wsm.WghtStreamMapper.SKIP_ZERO_WORDS = False
    tb.logger.info("probe_spad: candidate encoder installed (SKIP_ZERO_WORDS off)")


def is_zero(pattern, c, f, y, x, rng):
    if pattern.startswith("list:"):
        return f"{c}.{f}.{y}.{x}" in pattern[5:].split(",")
    return ((pattern == "chan1" and c == 1) or (pattern == "chan1_f0" and (c, f) == (1, 0)) or
            (pattern == "filter0" and f == 0) or (pattern.startswith("rand") and rng.random() < float(pattern[4:])))


def set_weights(model, dram):
    n = _orig(model, dram)
    w = dram.weights[0]                                   # [c][f][ky][kx]
    pattern = os.environ.get("B22_PATTERN", "none")
    rng = random.Random(int(os.environ.get("B22_SEED", "7")))
    F = len(w[0])
    zeros = []
    if pattern == "keep":                                 # leave the testbench's weights (e.g. USE_SPARSE_WGHTS)
        return n
    if pattern.startswith("file:"):                      # weights of a real layer, e.g. the trained int8 MNIST
        src = json.load(open(pattern.split(":", 2)[1]))[pattern.split(":", 2)[2]]
        assert (len(src), len(src[0])) == (len(w), F), "weight file does not fit the layer"
        dram.weights[0] = src
        zeros = [[c, f, y, x] for c in range(len(src)) for f in range(F) for y in range(3) for x in range(3)
                 if src[c][f][y][x] == 0]
        tb.logger.info("probe_spad: weights from %s, %d zero weights", pattern, len(zeros))
        with open(os.environ["B22_DUMP"] + ".weights.json", "w") as fh:
            json.dump({"weights": src, "zeros": zeros}, fh)
        return n
    for c in range(len(w)):
        for f in range(F):
            for y in range(len(w[c][f])):
                for x in range(len(w[c][f][y])):
                    w[c][f][y][x] = unique_value(c, f, y, x, F)
                    if is_zero(pattern, c, f, y, x, rng):
                        w[c][f][y][x] = 0
                        zeros.append([c, f, y, x])
    tb.logger.info("probe_spad: pattern %s, %d zero weights", pattern, len(zeros))
    with open(os.environ["B22_DUMP"] + ".weights.json", "w") as fh:
        json.dump({"weights": w, "zeros": zeros}, fh)
    return n


async def dump_spads(dut):
    pes = []
    par = dut.OpenEye_Parallel
    for cx in range(2):
        for cy in range(2):
            for col in range(4):
                for row in range(3):
                    try:
                        pe = par.gen_x[cx].gen_y[cy].OpenEye_Cluster.pe_cluster.gen_X[col].gen_Y[row].pe
                        pes.append(((cx, cy, col, row), pe, pe.gen_wght_addr_spad.weight_addr_SPad, pe.weight_data_SPad))
                    except Exception as exc:
                        tb.logger.info("probe_spad: PE %s not reachable (%s)", (cx, cy, col, row), type(exc).__name__)
    log = {f"{k[0]}{k[1]}{k[2]}{k[3]}": [] for k, *_ in pes}
    cycle = 0

    def val(sig):
        try:
            return int(sig.value)
        except ValueError:
            return None

    while True:
        await FallingEdge(dut.clk_i)
        cycle += 1
        for key, pe, wa, wd in pes:
            k = f"{key[0]}{key[1]}{key[2]}{key[3]}"
            if val(wa.we_i) == 1:
                log[k].append(["A", cycle, val(wa.addr_i), val(wa.data_i)])
            if val(wd.we_i) == 1:
                log[k].append(["D", cycle, val(wd.addr_i), val(wd.data_i)])
            if val(pe.compute_i) == 1:
                log[k].append(["C", cycle])
            if val(pe.wght_enable_i) == 1:
                log[k].append(["I", cycle, val(pe.wght_data_i)])
        if cycle % 500 == 0:
            with open(os.environ["B22_DUMP"], "w") as fh:
                json.dump(log, fh)


PE_REGS = ["current_state_computing", "wght_data_vec", "first_spad_words_wght", "second_spad_words_wght",
           "second_spad_words_iact", "mux_iact_ready", "wght_addr_SPad_data_r", "iact_data_SPad_addr",
           "iact_addr_SPad_data_r", "iact_data_spad_oh", "compute_pe", "computing", "wght_data_SPad_addr",
           "wght_addr_SPad_addr", "values_valid"]
FSM_REGS = ["wght_data_start", "wght_data_end", "wght_data_end_pre", "wght_data_start_pre", "wght_addr_vec",
            "iact_addr_count", "iact_addr_current", "next_iact", "fast_cycle", "wght_start_set", "wght_end_set",
            "iact_oh_delay_1", "iact_oh_delay_2"]


async def snapshots(dut):
    """B22_SNAPSHOT=<every>: every <every> cycles, the compute registers of every PE (json, overwritten)."""
    every = int(os.environ["B22_SNAPSHOT"])
    par = dut.OpenEye_Parallel
    pes = []
    for cx in range(2):
        for cy in range(2):
            for col in range(4):
                for row in range(3):
                    pes.append((f"{cx}{cy}{col}{row}",
                                par.gen_x[cx].gen_y[cy].OpenEye_Cluster.pe_cluster.gen_X[col].gen_Y[row].pe))

    def val(obj, name):
        try:
            return int(getattr(obj, name).value)
        except Exception:
            return None

    cycle, history = 0, []
    while True:
        await FallingEdge(dut.clk_i)
        cycle += 1
        if cycle % every:
            continue
        snap = {"cycle": cycle}
        for key, pe in pes:
            regs = {n: val(pe, n) for n in PE_REGS}
            regs.update({n: val(pe.gen_sparse_fsm, n) for n in FSM_REGS})
            snap[key] = regs
        history = (history + [snap])[-6:]
        with open(os.environ["B22_DUMP"] + ".snap.json", "w") as fh:
            json.dump(history, fh)


@cocotb.test()
async def probe_test(dut):
    if os.environ.get("B22_SNAPSHOT"):
        cocotb.start_soon(snapshots(dut))
    if os.environ.get("B22_NOSKIP") == "1":
        import open_eye.wght_stream_mapper as wsm
        wsm.WghtStreamMapper.SKIP_ZERO_WORDS = False      # every PE gets its full, dense-length word list
    if os.environ.get("B22_ENCODER") == "new":
        install_encoder()
    cp.fill_padding_channels = set_weights
    if os.environ.get("B22_NO_DUMP") != "1":
        cocotb.start_soon(dump_spads(dut))
    await tb.start_test_fpga.func(dut)
