"""Multi-layer probe: (1) LAYER=MNIST_REAL builds the architecture of models/mnist_conv_net.py (Conv 28x28xC->32, MaxPool,
Conv 14x14x32->64, MaxPool, Conv 7x7x64->64, Dense 3136->10; C = MODEL_IN_CH) with random data; (2) a per-layer phase
profiler (same phase rules as rtl_test_utils.profile_dma_phases, split at every entry into GET_PARAMETERS), written to
LAYER_PROFILE (json). Wraps the unmodified OpenEye_FPGA_tb."""
import json
import os

import cocotb
from cocotb.triggers import RisingEdge

import OpenEye_FPGA_tb as tb
import open_eye.rtl_test_utils as rtu

_orig_create = tb.data_create.create_layer


def create_layer(layer_mode, *args, **kw):
    if layer_mode != "MNIST_REAL":
        return _orig_create(layer_mode, *args, **kw)
    import tensorflow as tf
    c = int(os.environ.get("MODEL_IN_CH", "1"))
    m = tf.keras.Sequential()
    m.add(tf.keras.layers.Conv2D(32, (3, 3), padding="same", input_shape=(28, 28, c)))
    m.add(tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="valid"))
    m.add(tf.keras.layers.Conv2D(64, (3, 3), padding="same", input_shape=(14, 14, 32)))
    m.add(tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="valid"))
    m.add(tf.keras.layers.Conv2D(64, (3, 3), padding="same", input_shape=(7, 7, 64)))
    m.add(tf.keras.layers.Flatten())
    m.add(tf.keras.layers.Dense(units=10, use_bias=True))
    return m


@cocotb.test()
async def probe_test(dut):
    tb.data_create.create_layer = create_layer
    layers = []
    state = {"started": False, "layer": -1, "last_main": None}

    def bit(sig):
        try:
            return int(sig.value)
        except ValueError:
            return 0

    def dump():
        with open(os.environ["LAYER_PROFILE"], "w") as f:
            json.dump(layers, f, indent=1)

    async def profile():
        psum_sig = dut.psum_pipeline_inst.fsm_psum_current_state
        cycle = 0
        while True:
            await RisingEdge(dut.clk_i)
            accepted = bit(dut.enable_dma_i_reg) & bit(dut.ready_dma_o)
            out_word = bit(dut.enable_dma_o) & bit(dut.ready_dma_i)
            if not state["started"]:
                if not accepted:
                    continue
                state["started"] = True
            try:
                main = int(dut.fsm_current_state.value)
                psum = int(psum_sig.value)
            except ValueError:
                main, psum = state["last_main"], None
            if main == 1 and state["last_main"] != 1:
                state["layer"] += 1
                layers.append({"layer": state["layer"], "start_cycle": cycle, "phases": {}, "in_words": 0, "out_words": 0})
            state["last_main"] = main
            if state["layer"] < 0:
                layers.append({"layer": 0, "start_cycle": cycle, "phases": {}, "in_words": 0, "out_words": 0})
                state["layer"] = 0
            # psum FSM (psum_pipeline.v): 1 WAIT_TO_SEND_READY_SIGNAL, 2 CALCULATE_PSUM, 3 PSUM_GET_RESULTS,
            # 4 WAIT_FOR_SENDING_RESULTS, 5 PSUM_SEND_RESULTS, 6 SEND_PSUM_TO_IACT. In a chained layer the main FSM
            # sits in state 11 (RECEIVE_PSUMS_TO_IACT) while the array computes and while results are written back,
            # so states 10/11 are split by the psum FSM.
            if psum == rtu.PSUM_SEND_RESULTS_STATE or out_word:
                phase = "readout"
            elif main in (10, 11) and psum in (1, 2, 3):
                phase = "compute"
            elif main in (10, 11) and psum in (4, 6):
                phase = "writeback"
            elif main in (10, 11):
                phase = "wait_psum_idle"
            else:
                phase = rtu.PROFILE_PHASES.get(main, f"state_{main}")
            L = layers[-1]
            L["phases"][phase] = L["phases"].get(phase, 0) + 1
            L["in_words"] += accepted
            L["out_words"] += out_word
            cycle += 1
            if cycle % 4096 == 0:
                dump()

    cocotb.start_soon(profile())
    try:
        await tb.start_test_fpga.func(dut)
    finally:
        dump()
