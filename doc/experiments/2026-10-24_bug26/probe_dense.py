"""Bug #26 probe (cocotb module, run through run_dense.py): the unmodified OpenEye_FPGA_tb plus switches (environment).

LAYER=D_<K>_<N1>[_<N2>...] builds a chain of Dense layers K -> N1 -> N2 ... (input (1,1,K)); every other LAYER goes to
data_create unchanged (MLP, PAPER_MNIST, ...).
  B26_DUMP=<file>        layer-0 inputs, weights, bias, quantize and the reference quantized outputs (json)
  B26_INJECT=1           after a failed iact check, write the expected image into BUFFER_A (isolates the write-back)
  B26_WB=1               Python-only write-back registers for a Dense that keeps its output on chip (install_writeback)
  B26_WB_KEEP_ADDUP=1    ... but leave iact_x_add_up at the layer's value (the FC converter needs it)
  B26_ADDUP=<n>          ... or set iact_x_add_up to n (default WRITEBACK_WORDS)
  B26_LIMIT_ROWS=1       ... with fsm_psum_limit = 8 + 8*IACT_RAM_CELLS*ceil(values / (8*IACT_RAM_CELLS))
  B26_EMU=1              emulate the proposed one-line RTL change (emulate_fc_xpos_wrap); the RTL source is not touched
The RTL is never modified: B26_EMU only deposits a register value in the simulation."""
import cocotb
import OpenEye_FPGA_tb as tb

_orig = tb.data_create.create_layer


def create_layer(layer_mode, *args, **kw):
    if not layer_mode.startswith("D_"):
        return _orig(layer_mode, *args, **kw)
    import tensorflow as tf
    sizes = [int(v) for v in layer_mode.split("_")[1:]]
    m = tf.keras.Sequential()
    m.add(tf.keras.layers.Dense(input_shape=(1, 1, sizes[0]), units=sizes[1], use_bias=True))
    for n in sizes[2:]:
        m.add(tf.keras.layers.Dense(units=n, use_bias=True))
    return m


def install_dump():
    """B26_DUMP=<file>: layer-0 inputs, weights, bias, quantize and the reference psums / quantized values (json)."""
    import json, os
    path = os.environ.get("B26_DUMP")
    if not path:
        return
    state = {}
    orig_collect, orig_bn = tb.tum.collect_results, tb.slo.batchnorm_output

    def collect_results(layer_number, lpar, dram, serial):
        res = orig_collect(layer_number, lpar, dram, serial)
        if layer_number == 0 and "Dense" in str(lpar.layer_name):
            state.update(fmap=[int(v) for v in dram.fmap[0]], weights=[[int(v) for v in row] for row in dram.weights[0]],
                         bias=[int(v) for v in dram.bias[0]], quantize=[list(map(int, q)) for q in lpar.quantize[:len(res)]],
                         psums=[int(v) for v in res])
        return res

    def batchnorm_output(lpar, divide, layer_number, dram):
        orig_bn(lpar, divide, layer_number, dram)
        if layer_number == 0 and "psums" in state:
            state["quantized"] = [int(v) for v in dram.fmap[1]]
            json.dump(state, open(path, "w"))

    tb.tum.collect_results = collect_results
    tb.slo.batchnorm_output = batchnorm_output


def install_inject():
    """B26_INJECT=1: when the iact check after a layer fails, write the expected image into BUFFER_A (the half the
    DUT has selected) so the next layer runs on the right activations; isolates the write-back from the rest."""
    import os
    if not os.environ.get("B26_INJECT"):
        return
    rtu = tb.rtl_test_utils
    orig = rtu.compare_iact_storage

    def compare_iact_storage(ptp, dut, iact_ref, oep, layer_params):
        ok = orig(ptp, dut, iact_ref, oep, layer_params)
        if not ok:
            expected = rtu._to_ram_format(rtu._iact_buffer_words(oep, layer_params, iact_ref), oep, layer_params)
            half = rtu.iact_half_offset(dut, oep)
            for index, word in enumerate(expected):
                cell, addr = index % oep.IACT_RAM_CELLS, index // oep.IACT_RAM_CELLS
                dut.BUFFER_A[cell].iact_layer_buffer.impl.mem[half + addr].value = word
            tb.logger.error("B26_INJECT: wrote the expected %d-word image into BUFFER_A", len(expected))
        return ok
    rtu.compare_iact_storage = compare_iact_storage


def install_writeback():
    """B26_WB=1: Python-only Dense write-back configuration (no RTL change). For a Dense layer that keeps its output
    on chip (send_data_out = 0) the status registers are overridden at packing time:
      - read order: cluster column c, address a for value t = c*P + a (P = used_psum_per_PE = "filters"), via the
        psum cluster-select loops (stay P cycles on a column, then step one column) and the address loops (0..P-1);
      - fsm_psum_limit = CX*P + 6, so SEND_PSUM_TO_IACT runs until value CX*P-1 reaches the quantizer output;
      - iact_size_x = 1 and iact_x_add_up = B26_ADDUP (default WRITEBACK_WORDS): RECEIVE_PSUMS_TO_IACT then keeps only
        lane 0 (GLB 0) of every WRITEBACK_WORDS-wide group, which gives the flat Dense layout.
    B26_WB_KEEP_ADDUP=1 leaves iact_x_add_up alone (to see what it does to the layer's own computation)."""
    import os
    if not os.environ.get("B26_WB"):
        return
    import open_eye.generator as gen
    orig = gen.pack_registers
    cx = int(os.environ.get("CLUSTER_COLUMNS", "2"))
    w = min(int(os.environ.get("TRANS_WORDS", "8")), int(os.environ.get("NUM_GLB_PSUM", "4")))
    cells = int(os.environ.get("IACT_RAM_CELLS", "4"))

    def pack_registers(values, *a, **kw):
        if values.get("fully_connected_layer") == 1 and values.get("send_data_out") == 0:
            p = values["filters"]
            # psum transmissions: needed_wght_cycles = diff_iact_layer * needed_psum_transmissions
            k, uipp = values["fc_size_reg"], values["iact_channels_per_pe"]
            diff = -(-k // (int(os.environ.get("NUM_GLB_WGHT", "3")) * uipp * int(os.environ.get("CLUSTER_ROWS", "2"))))
            reps = max(1, values["needed_wght_cycles"] // diff)
            values = dict(values)
            limit = cx * p + 6
            if os.environ.get("B26_LIMIT_ROWS"):
                # SEND_PSUM_TO_IACT ends one cycle after the last group of a full buffer row (8*IACT_RAM_CELLS
                # values) is kept, so RECEIVE_PSUMS_TO_IACT's flush finds its storage counter at 0 and stops at once
                row = 8 * cells
                limit = 8 + row * -(-(reps * cx * p) // row)
            values.update(fsm_psum_limit=limit,
                          psum_pagu_loop_limit_0=p - 1, psum_pagu_addr_inc_0=1,
                          psum_pagu_loop_limit_1=cx - 1, psum_pagu_addr_inc_1=0,
                          psum_pagu_loop_limit_2=reps - 1, psum_pagu_addr_inc_2=p,
                          psum_pagu_loop_limit_3=255, psum_pagu_addr_inc_3=0,
                          psum_pagu_loop_limit_4=0, psum_pagu_addr_inc_4=0,
                          psum_pagu_cs_limit_0=p - 1, psum_pagu_cs_inc_0=0,
                          psum_pagu_cs_limit_1=cx - 1, psum_pagu_cs_inc_1=1,
                          psum_pagu_cs_limit_2=0, psum_pagu_cs_inc_2=0,
                          iact_size_x=1)
            if not os.environ.get("B26_WB_KEEP_ADDUP"):
                values["iact_x_add_up"] = int(os.environ.get("B26_ADDUP", w))
            tb.logger.info("B26_WB: P=%d CX=%d reps=%d W=%d fsm_psum_limit=%d iact_x_add_up=%s", p, cx, reps, w,
                           values["fsm_psum_limit"], values.get("iact_x_add_up"))
        return orig(values, *a, **kw)
    gen.pack_registers = pack_registers


async def emulate_fc_xpos_wrap(dut):
    """B26_EMU=1: emulate the proposed one-line RTL change in RECEIVE_PSUMS_TO_IACT (OpenEye_FPGA.v), i.e.
         if ((iact_to_psum_x_pos_counter >= iact_x_add_up - 1) | fully_connected_layer) x_pos <= 0;
    without touching the RTL: right after every group reload (trans_counter back at 1) of a fully connected layer the
    testbench deposits 0 into iact_to_psum_x_pos_counter, which is what the changed line would have stored."""
    from cocotb.triggers import FallingEdge
    n = 0
    while True:
        await FallingEdge(dut.clk_i)
        try:
            if (int(dut.fsm_current_state.value) == 11 and int(dut.fully_connected_layer.value) == 1
                    and int(dut.iact_to_psum_trans_counter.value) == 1 and int(dut.iact_to_psum_x_pos_counter.value) != 0):
                dut.iact_to_psum_x_pos_counter.value = 0
                n += 1
                if n <= 3:
                    tb.logger.info("B26_EMU: x_pos reset at the group reload (%d so far)", n)
        except ValueError:
            pass


@cocotb.test()
async def probe_test(dut):
    import os
    if os.environ.get("B26_EMU"):
        cocotb.start_soon(emulate_fc_xpos_wrap(dut))
    install_writeback()
    install_dump()
    install_inject()
    tb.data_create.create_layer = create_layer
    await tb.start_test_fpga.func(dut)
