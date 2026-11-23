# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.

import sys
import os
import cocotb
import tensorflow as tf
from cocotb.clock import Clock
import open_eye.test_utils_main as tum
import open_eye.rtl_test_utils as rtl_test_utils
import open_eye.timing_parameters as tp
import open_eye.generic_test_utils as gtu
import open_eye.DRAM as DRAM
import open_eye.time_stamper as time_stamper
import open_eye.open_eye_parameters as oep
import open_eye.layer_parameters as lp
import open_eye.simple_layer_operations as slo
import open_eye.layer_execution_state as les
import open_eye.data_create as data_create
import open_eye.channel_pad as channel_pad
import open_eye.tflite2model as tflite2model
import open_eye.onnx2model as o2m
from cocotb.logging import SimLogFormatter
import logging
import sys
import logging
from pathlib import Path
from cocotb.utils import get_sim_time
from cocotb.triggers import FallingEdge, RisingEdge, Timer, with_timeout, SimTimeoutError

class CustomSimTimeFormatter(logging.Formatter):
    """Custom logging formatter that adds simulation time to log messages.
    
    This formatter extends the standard logging.Formatter to prepend simulation
    time in nanoseconds to each log message.
    """
    def format(self, record):
        # Zeit in ns holen
        try:
            sim_time = get_sim_time('ns')
            sim_time_str = f"{sim_time:10.2f}ns"
        except:
            sim_time_str = "  -.--ns"
            
        # Das Standard-Format von cocotb nachbauen
        msg = super().format(record)
        return f"{sim_time_str} {msg}"

os.environ["CLOCK_LEN"] = "10"
os.environ["CLOCK_UNIT"] = "ns"
os.environ["CLOCK_DELAY_INPUT"] = "100"
os.environ["CLOCK_DELAY_UNIT_INPUT"] = "ps"

os.environ["CLOCK_DELAY_OUTPUT"] = "100"
os.environ["CLOCK_DELAY_UNIT_OUTPUT"] = "ps"

time_printer = time_stamper.time_stamper()

tests_dir = os.path.abspath(os.path.dirname(__file__))
hdl_dir = (os.path.abspath(os.path.join(os.getcwd(), os.pardir, os.pardir, "hdl")))
log_level = int(os.getenv("LOGGER_LEVEL"))
logger = logging.getLogger("cocotb")
async def setup_file_logging():
    global logger
    """Hilfsfunktion, um den Logger sauber zu konfigurieren."""
    log_path = os.getenv("COCOTB_LOG_FILE_PATH")
    if not log_path:
        return
    
    log_path = os.path.abspath(log_path)
    logger = logging.getLogger("cocotb")
    
    # Verhindere doppelte Handler, falls dieser Code mehrfach aufgerufen wird
    for h in logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            logger.removeHandler(h)
    
    # Handler erstellen
    fh = logging.FileHandler(log_path, mode='w')
    

    # Level setzen
    raw_level = os.getenv("LOGGER_LEVEL")
    level = int(raw_level) if raw_level else logging.INFO
    fh.setLevel(level)
    
    # Formatter mit Simulationszeit
    fh.setFormatter(CustomSimTimeFormatter("%(levelname)-8s %(name)-20s %(message)s"))

    logger.addHandler(fh)
    logger.info(f"File logging started at sim time {cocotb.utils.get_sim_time('ns')} ns")
def envvars_to_vars():    
    # Get variables that are used for the execution of the test
    only_files = gtu.load_env_to_variable("ONLY_FILES", 0)
    layer_mode = gtu.load_env_to_variable("LAYER", "Convolution")
    filters = gtu.load_env_to_variable("NUM_FILTERS", 4)
    kernelsize_x = gtu.load_env_to_variable("KERNEL_SIZE_X", 3)
    kernelsize_y = gtu.load_env_to_variable("KERNEL_SIZE_Y", 3)
    inputsize_x = gtu.load_env_to_variable("INPUT_SIZE_X", 64)
    inputsize_y = gtu.load_env_to_variable("INPUT_SIZE_Y", 1)
    outputsize = gtu.load_env_to_variable("OUTPUT_SIZE", 1)
    strides = gtu.load_env_to_variable("STRIDE", 1),gtu.load_env_to_variable("STRIDE", 1)
    channels = gtu.load_env_to_variable("INPUT_CHANNELS", 4)
    sparse_iacts = gtu.load_env_to_variable("USE_SPARSE_IACTS", 0)
    # Runners set USE_SPARSE_WGHTS; keep USE_SPARSE_WEIGHTS as fallback for
    # older callers.
    sparse_wghts = gtu.load_env_to_variable(
        "USE_SPARSE_WGHTS", gtu.load_env_to_variable("USE_SPARSE_WEIGHTS", 0))
    return only_files, layer_mode, filters, kernelsize_x, kernelsize_y, inputsize_x, inputsize_y, outputsize, strides, channels, sparse_iacts, sparse_wghts

#@cocotb.test()
async def model_test(dut):
    """ Test the DUT with a given DNN model.

    Load a trained DNN model (in TFLite format) 
    and simulate the execution using the OpenEye FPGA wrapper.
    """
    only_files, layer_mode, filters, kernelsize_x, kernelsize_y, \
    inputsize_x, inputsize_y, outputsize, strides, \
    channels, sparse_iacts, sparse_wghts = envvars_to_vars()
    layer_es = les.LayerExecutionState()
    serial = 1
    clk_cycle = int(os.environ["CLOCK_LEN"])
    clk_cycle_unit = os.environ["CLOCK_UNIT"]

    clk_delay_in = int(os.environ["CLOCK_DELAY_INPUT"])
    clk_delay_unit_in = os.environ["CLOCK_DELAY_UNIT_INPUT"]

    clk_delay_out = int(os.environ["CLOCK_DELAY_OUTPUT"])
    clk_delay_unit_out = os.environ["CLOCK_DELAY_UNIT_OUTPUT"]

    ptp = tp.PortTimingParameters()
    ptp.initiate_params(clk_cycle, clk_cycle_unit, clk_delay_in, clk_delay_unit_in, clk_delay_out, clk_delay_unit_out)
    
    tf_model_path = os.environ["MODEL_PATH"]
    model = tf.keras.models.load_model(tf_model_path)
    trunc_model = truncate_model(model)


    await execute_model(dut, only_files, sparse_iacts, sparse_wghts, layer_es, serial, ptp, trunc_model)
@cocotb.test()
async def start_test_fpga(dut):
    """
    Main cocotb test entry point for FPGA verification.
    """
    global logger
    await setup_file_logging()
    timeout_time = 15000000
    timeout_unit = 'ns'

    try:
        # Here the test gets started
        await with_timeout(single_layer_test(dut),timeout_time, timeout_unit)
    except SimTimeoutError:
        dut._log.error("Test did not finish in time!")
        raise # Error if does not finish in time
async def single_layer_test(dut):
    """Simulate a single layer.
    
    Simulate a single layer using the OpenEye FPGA wrapper.
    """

    only_files, layer_mode, filters, kernelsize_x, kernelsize_y, inputsize_x, inputsize_y, outputsize, strides, channels, sparse_iacts, sparse_wghts = envvars_to_vars()



    try:
        use_random = int((os.environ["USE_RANDOM_VALUES"]))
        print("try use random")
    except:
        use_random = 1
        logger.debug("USE_RANDOM_VALUES set to one")
        print("except use random")

    layer_es = les.LayerExecutionState()
    serial = 1
    clk_cycle = int(os.environ["CLOCK_LEN"])
    clk_cycle_unit = os.environ["CLOCK_UNIT"]

    clk_delay_in = int(os.environ["CLOCK_DELAY_INPUT"])
    clk_delay_unit_in = os.environ["CLOCK_DELAY_UNIT_INPUT"]

    clk_delay_out = int(os.environ["CLOCK_DELAY_OUTPUT"])
    clk_delay_unit_out = os.environ["CLOCK_DELAY_UNIT_OUTPUT"]

    ptp = tp.PortTimingParameters()
    ptp.initiate_params(clk_cycle, clk_cycle_unit, clk_delay_in, clk_delay_unit_in, clk_delay_out, clk_delay_unit_out)

    # OPENEYE_SEED makes the random model and data reproducible: the Keras
    # weight initializers (conv weights come from the model) and the numpy
    # draws of DRAMContents (Dense weights, inputs, zero replacement). Used by
    # the profiling baselines of whole models, where the zero-skipping makes
    # the cycle count depend on the data. tf.random.set_seed alone is not
    # enough: Keras 3 initializers draw from their own seed generator.
    if os.environ.get("OPENEYE_SEED"):
        tf.keras.utils.set_random_seed(int(os.environ["OPENEYE_SEED"]))
        logger.info("OPENEYE_SEED: random model and data seeded with %s", os.environ["OPENEYE_SEED"])

    # Create a test model
    gtu.select_gpu(0)

    #Here If-Condition test, wether use model or single Layer
    if(use_random):
        model = data_create.create_layer(layer_mode, filters, kernelsize_x, kernelsize_y, inputsize_x, inputsize_y, strides, channels, outputsize)
        trunc_model = [
        layer for layer in model.layers
        if not isinstance(layer, tf.keras.layers.Flatten)
        ]
    else:
        current_dir = Path(__file__).resolve().parent
        target_dir = current_dir.parent.parent / "models"
        sys.path.append(str(target_dir))
        from mnist_conv_net import SimpleMNISTConvNet
        model = SimpleMNISTConvNet()
        calibration = None
        if os.environ.get("OPENEYE_MODEL_WEIGHTS"):
            # A trained checkpoint (e.g. doc/demo_notebooks/mnist_unquantized_model.pth): onnx2model quantizes it
            # statically for the hardware, calibrated on MNIST training images preprocessed as in training. A
            # checkpoint of models/train_mnist.py names its activation (Leaky ReLU, SiLU, hard-swish); the
            # original one is ReLU.
            from train_mnist import load_activation_model
            model, checkpoint = load_activation_model(os.environ["OPENEYE_MODEL_WEIGHTS"])
            logger.info("OPENEYE_MODEL_WEIGHTS: activation %s", checkpoint.get("activation", "relu"))
            calibration, _ = data_create.mnist_images(
                "train", range(int(os.environ.get("OPENEYE_CALIBRATION_IMAGES", "200"))))
            logger.info("OPENEYE_MODEL_WEIGHTS: %s, static quantization calibrated on %d training images",
                        os.environ["OPENEYE_MODEL_WEIGHTS"], len(calibration))
        model = o2m.get_model(model, calibration)
        trunc_model = truncate_model(model)
    if os.environ.get("OPENEYE_EXPECT_LAYERS"):
        expected_layers = int(os.environ["OPENEYE_EXPECT_LAYERS"])
        assert len(trunc_model) == expected_layers, (
            f"{layer_mode}: expected {expected_layers} layers, got {len(trunc_model)}")
    await execute_model(dut, only_files, sparse_iacts, sparse_wghts, layer_es, serial, ptp, trunc_model)

def truncate_model(model):
    
    trunc_model = [
        layer for layer in model
        if not isinstance(layer, tf.keras.layers.Flatten)
    ]
    return trunc_model

async def execute_model(dut, only_files, sparse_iacts, sparse_wghts, layer_es, serial, ptp, model):
    global logger
    openeye_parameter = oep.get_oep(serial)
    time_printer.timestamp("OpenEye parameters set. ", logger)

    gtu.delete_files_in_directory('demo/')

    if (only_files == 0) :
        # Start the clock
        clk = Clock(dut.clk_i, ptp.clk_cycle, unit=ptp.clk_cycle_unit)
        cocotb.start_soon(clk.start())
        dut._log.info("Clock is %s " + ptp.clk_cycle_unit, ptp.clk_cycle)
        # reset the DUT
        await cocotb.start_soon(rtl_test_utils.reset_all_signals(ptp, dut, openeye_parameter.SERIAL))

    if os.environ.get("OPENEYE_TRACE_DMA") and only_files == 0:
        cocotb.start_soon(rtl_test_utils.trace_dma_input(ptp, dut))
    if os.environ.get("OPENEYE_PROFILE") and only_files == 0:
        cocotb.start_soon(rtl_test_utils.profile_dma_phases(ptp, dut, openeye_parameter))
    if os.environ.get("OPENEYE_FORCE_RAW_WGHT") == "1" and only_files == 0:
        # Experiment hook (step 2 of the per-layer weight format P1, README_FI section 2), simulation only, no RTL
        # change: hold the raw_wght_i input of OpenEye_Parallel (today FC | GEMM) at 1 for every layer, so
        # data_pipeline_wght keeps all-zero weight words, as P1 would set it for a layer sent in the dense layout
        # (OPENEYE_WGHT_LAYOUT=dense). The input only reaches data_pipeline_wght.raw_mode_i.
        from cocotb.handle import Force
        dut.OpenEye_Parallel.raw_wght_i.value = Force(1)
        logger.info("OPENEYE_FORCE_RAW_WGHT: OpenEye_Parallel.raw_wght_i forced to 1")
    if os.environ.get("OPENEYE_PROBE_FSM"):
        cocotb.start_soon(rtl_test_utils.probe_fsm_states(ptp, dut, oep=openeye_parameter))
        cocotb.start_soon(rtl_test_utils.monitor_iact_handoff(ptp, dut))
    if os.environ.get("DUMP_PSUM_BUFFERS") and not os.environ.get("OPENEYE_PROBE_FSM"):
        cocotb.start_soon(rtl_test_utils.monitor_iact_handoff(ptp, dut))
    if os.environ.get("TRACE_CONVERTER_GATE"):
        # Both cluster rows, to compare their acceptance windows directly.
        cocotb.start_soon(rtl_test_utils.trace_converter_gate(ptp, dut, openeye_parameter, col=0, row=0))
        cocotb.start_soon(rtl_test_utils.trace_converter_gate(ptp, dut, openeye_parameter, col=0, row=1))
    if os.environ.get("DUMP_IACT_BUFFER"):
        async def _dump_buf():
            from cocotb.triggers import Timer as _T
            for _ in range(400):
                await _T(ptp.clk_cycle, unit=ptp.clk_cycle_unit)
            rtl_test_utils.dump_iact_buffer_values(dut, openeye_parameter)
        cocotb.start_soon(_dump_buf())
    if os.environ.get("TRACE_CONVERT_WINDOW"):
        cocotb.start_soon(rtl_test_utils.trace_convert_window(ptp, dut, openeye_parameter))
    if os.environ.get("DUMP_CONVERT_LIMITS"):
        cocotb.start_soon(rtl_test_utils.dump_convert_iact_limits(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_IACT_LANES"):
        cocotb.start_soon(rtl_test_utils.trace_iact_lanes(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_PSUM_SLICES"):
        cocotb.start_soon(rtl_test_utils.trace_psum_capture_slices(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_CONV_WRITEBACK"):
        cocotb.start_soon(rtl_test_utils.trace_conv_writeback(ptp, dut))
    if os.environ.get("TRACE_PE_CALC"):
        cocotb.start_soon(rtl_test_utils.trace_pe_calc_loop(ptp, dut, openeye_parameter))
    if os.environ.get("DUMP_CLUSTER_IACT"):
        cocotb.start_soon(rtl_test_utils.monitor_cluster_iact(ptp, dut, openeye_parameter))
        cocotb.start_soon(rtl_test_utils.monitor_pe_iact(ptp, dut, openeye_parameter))
        cocotb.start_soon(rtl_test_utils.monitor_converter_store(ptp, dut, openeye_parameter))
    if os.environ.get("PROBE_PSUM_STREAM"):
        cocotb.start_soon(rtl_test_utils.probe_psum_stream(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_PSUM_CAPTURE"):
        cocotb.start_soon(rtl_test_utils.trace_psum_capture(ptp, dut, openeye_parameter))
        cocotb.start_soon(rtl_test_utils.trace_bias_load(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_CONVERTER"):
        cocotb.start_soon(rtl_test_utils.trace_converter(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_RAM_WRITES"):
        cocotb.start_soon(rtl_test_utils.trace_ram_writes(ptp, dut))
    if os.environ.get("TRACE_POOLING"):
        cocotb.start_soon(rtl_test_utils.trace_pooling(ptp, dut, max_lines=4000))
    if os.environ.get("TRACE_PE_SPADS"):
        cocotb.start_soon(rtl_test_utils.trace_pe_spads(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_PE_WADDR"):
        cocotb.start_soon(rtl_test_utils.trace_pe_wght_addrs(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_PE_WGHT"):
        cocotb.start_soon(rtl_test_utils.trace_pe_wght_writes(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_PE_PASSES"):
        cocotb.start_soon(rtl_test_utils.trace_pe_pass_counts(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_WB_EVENTS"):
        cocotb.start_soon(rtl_test_utils.trace_wb_events(ptp, dut))
    if os.environ.get("TRACE_ALL_PE"):
        cocotb.start_soon(rtl_test_utils.trace_all_pe_states(ptp, dut, openeye_parameter, max_lines=4000))
    if os.environ.get("TRACE_PE_IACT"):
        cocotb.start_soon(rtl_test_utils.trace_pe_iact(ptp, dut, openeye_parameter))
    if os.environ.get("TRACE_PE_PSUM"):
        cocotb.start_soon(rtl_test_utils.trace_pe_psum(ptp, dut, openeye_parameter))

    # Process the layers of the model one after another
    max_layers = len(model)

    def build_layer_parameters(model):
        layer_parameters = [0 for _ in range(len(model))]
        for layer_number, layer in reversed(list(enumerate(model))):
            layer_parameters[max_layers - layer_number - 1] = lp.LayerParameters(layer_parameters, layer, openeye_parameter, layer_number, max_layers)
        return list(reversed(layer_parameters))

    layer_parameters = build_layer_parameters(model)
    # A first convolution with an odd channel count above 1 gets one zero channel more (bug #7: the RTL moves
    # channel pairs). The former bug #17 workaround, off by default since the RTL fix (OPENEYE_PAD_CHANNELS=1 turns
    # it on), gives a one-channel first layer wider than one x pass a second one (open_eye.channel_pad).
    model, padded = channel_pad.pad_first_layer(model, layer_parameters)
    if padded:
        layer_parameters = build_layer_parameters(model)
        layer_parameters[0].pad_channels = model[0].pad_channels
        logger.info("layer 0 input padded from %d to %d channels with zero activations (%s)",
                    model[0].original_channels, layer_parameters[0].channels,
                    "bug #7, odd channel count" if model[0].original_channels > 1
                    else f"former bug #17 workaround, {channel_pad.PAD_CHANNELS_ENV}=1")
    if os.environ.get("DUMP_LAYER_PARAMS"):
        for n, lpar in enumerate(layer_parameters):
            fields = sorted(k for k in vars(lpar) if k.startswith(("iact_read_", "iact_write_", "psum_pagu_"))
                            or k in ("iact_x_lines", "iact_x_line_repetitions", "iact_words_per_compute",
                                     "needed_iact_buffer_words", "needed_Iact_writes", "channel_div_trans",
                                     "used_channels", "diff_iact_layer", "needed_wght_cycles",
                                     "iact_repetitions_per_write", "iact_converter_max_cycles",
                                     "buffer_cycles_for_x_iact", "iact_converter_buffer_addr_max_cycles",
                                     "lower_bound", "upper_bound", "used_Y_cluster", "y_lines_per_calculation",
                                     "different_kernels_per_calculation", "padding_y", "padding_x", "strideY",
                                     "used_X_cluster", "iact_x_add_up", "psum_size_y", "psum_size_x", "filters",
                                     "fsm_psum_limit", "used_psum_per_PE", "iact_size_x", "iact_size_y",
                                     "diff_iact_layer_next_layer", "psum_storage_cycles"))
            logger.info("layerparams %d: %s", n, " ".join("%s=%s" % (k, getattr(lpar, k)) for k in fields))
    for n, lpar in enumerate(layer_parameters):
        logger.info("layer %d/%d %s: in=%sx%s ch=%s filters=%s send_values_out=%s "
                    "store_in_psum=%s transmissions=%s output_cycles=%s psum_output_words=%s "
                    "used_Y_cluster=%s used_X_cluster=%s",
                    n, max_layers, lpar.layer_name, getattr(lpar, "iact_size_x", "?"),
                    getattr(lpar, "iact_size_y", "?"), getattr(lpar, "channels", "?"),
                    getattr(lpar, "filters", "?"), lpar.send_values_out,
                    getattr(lpar, "store_in_psum", "?"), getattr(lpar, "needed_total_transmissions", "?"),
                    getattr(lpar, "output_cycles", "?"), getattr(lpar, "psum_output_words", "?"),
                    getattr(lpar, "used_Y_cluster", "?"), getattr(lpar, "used_X_cluster", "?"))
    if os.environ.get("OPENEYE_PROFILE"):
        # Names and shapes for the per-layer part of profile.json.
        rtl_test_utils.profile_set_layer_info(layer_parameters)
    # Create the OpenEye parameters and the DRAM given the model
    dram = DRAM.DRAMContents(model, layer_parameters)
    time_printer.timestamp("Initialized DRAM. ", logger)
    dram.write_initial_data_to_dram(model, layer_parameters, sparse_iacts, sparse_wghts)
    if os.environ.get("OPENEYE_ZERO_IACTS"):
        # Debug: zero the first layer's input so every product is 0 and each
        # output must equal its bias alone. This isolates the bias/psum feed
        # from the iact and weight delivery paths. The reference is computed
        # from the same DRAM, so it stays consistent.
        def _zero(x):
            return [_zero(v) for v in x] if isinstance(x, list) else 0
        dram.fmap[0] = _zero(dram.fmap[0])
        logger.info("OPENEYE_ZERO_IACTS: layer-0 input zeroed")
    if os.environ.get("OPENEYE_CONST_IACTS"):
        # Debug: force every layer-0 activation to one constant. With c = 1 the
        # expected output of a Dense filter is sum(weights) + bias, so a DUT
        # value that is short by a factor or an offset says how many product
        # terms actually accumulated - which zeroed inputs cannot show, since
        # they make every product vanish regardless of how many are summed.
        const_iact = int(os.environ["OPENEYE_CONST_IACTS"])
        def _const(x):
            return [_const(v) for v in x] if isinstance(x, list) else const_iact
        dram.fmap[0] = _const(dram.fmap[0])
        logger.info("OPENEYE_CONST_IACTS: layer-0 input set to %d", const_iact)
    if os.environ.get("OPENEYE_CONST_WGHTS"):
        # Debug: force every weight to one constant. Combined with
        # OPENEYE_CONST_IACTS=1 each Dense output becomes exactly
        # (terms accumulated) * const + bias, so the DUT value minus the bias
        # counts how many products the PEs actually summed. That is the one
        # number neither the zero-input nor the constant-input control can give.
        const_wght = int(os.environ["OPENEYE_CONST_WGHTS"])
        def _const_w(x):
            return [_const_w(v) for v in x] if isinstance(x, list) else const_wght
        dram.weights = _const_w(dram.weights)
        logger.info("OPENEYE_CONST_WGHTS: all weights set to %d", const_wght)
    if os.environ.get("OPENEYE_ASYMMETRIC_KERNEL"):
        # Distinct kernel rows/columns expose permutations that constant
        # weights hide. Both the mapper and reference read this same DRAM.
        for layer_number, params in enumerate(layer_parameters):
            if "Conv" not in str(params.layer_name):
                continue
            for channel in dram.weights[layer_number]:
                for kernel in channel:
                    for y, row in enumerate(kernel):
                        for x in range(len(row)):
                            row[x] = 1 + x + len(row) * y
        logger.info("OPENEYE_ASYMMETRIC_KERNEL: weight[y][x] = 1 + x + kernel_width*y")
    if os.environ.get("OPENEYE_MIX_WEIGHTS"):
        # weight[c][f] = 1 + c + 5*f for every tap: exposes channel or filter
        # mix-ups that channel-independent kernels (ASYMMETRIC_KERNEL) hide.
        for layer_number, params in enumerate(layer_parameters):
            if "Conv" not in str(params.layer_name):
                continue
            for c, channel in enumerate(dram.weights[layer_number]):
                for f, kernel in enumerate(channel):
                    for row in kernel:
                        for x in range(len(row)):
                            row[x] = 1 + c + 5 * f
        logger.info("OPENEYE_MIX_WEIGHTS: weight[c][f] = 1 + c + 5*f")
    if os.environ.get("OPENEYE_RAMP_IACTS"):
        # Layer-0 activation k becomes k+1, so a PE's stored payloads name the
        # exact input positions it received. Constant operands can only show
        # how many activations arrived, never which ones.
        def _ramp(x, ctr=[0]):
            if isinstance(x, list):
                return [_ramp(v, ctr) for v in x]
            ctr[0] += 1
            # Wrap so large inputs stay inside int8; small inputs are unchanged.
            if os.environ.get("OPENEYE_RAMP_MULT"):
                # Deterministic pseudo-random activations, full-rank for fitting.
                return ((ctr[0] - 1) * int(os.environ["OPENEYE_RAMP_MULT"])) % 61 + 1
            return (ctr[0] - 1) % 100 + 1
        dram.fmap[0] = _ramp(dram.fmap[0])
        logger.info("OPENEYE_RAMP_IACTS: layer-0 input set to 1..N in flat order")
    if os.environ.get("OPENEYE_BIAS_STEP"):
        # Give each output channel a distinct value after quantization so a
        # channel permutation cannot pass a constant-weight regression.
        step = int(os.environ["OPENEYE_BIAS_STEP"])
        dram.bias = [[1 + step*f for f in range(len(bias))] for bias in dram.bias]
        logger.info("OPENEYE_BIAS_STEP: bias[f] = 1 + %d*f", step)
    if os.environ.get("DUMP_INPUT_IACTS"):
        # Print the first activations of layer 0 so the values a PE holds can
        # be matched against the input vector. Every PE holding the same window
        # means the converter broadcasts instead of partitioning K.
        try:
            flat = dram.fmap[0]
            while isinstance(flat, list) and flat and isinstance(flat[0], list):
                flat = [v for sub in flat for v in sub]
            logger.info("layer-0 input activations (first 34): %s", flat[:34])
        except Exception as exc:
            logger.info("could not flatten layer-0 input (%s)", type(exc).__name__)
    if os.environ.get("OPENEYE_TFLITE_CONV"):
        # Layer-0 conv weights of a trained int8 TFLite model ("<file>:<tensor name>"),
        # e.g. the MNIST model of doc/demo_notebooks: real zero weights (bug #22).
        tflite_path, tensor_name = os.environ["OPENEYE_TFLITE_CONV"].split(":", 1)
        zeros = dram.load_conv_weights_tflite(0, tflite_path, tensor_name)
        logger.info("OPENEYE_TFLITE_CONV: layer-0 weights from %s (%d zero weights)", tensor_name, zeros)
    if os.environ.get("OPENEYE_INPUT_IMAGE"):
        # MNIST test image <index> as the model's input: preprocessed as in training and quantized with the model's
        # input scale (onnx2model static quantization, zero point 0), fmap[0][0][row][column]
        image, label = data_create.mnist_images("test", [int(os.environ["OPENEYE_INPUT_IMAGE"])])
        dram.fmap[0][0] = o2m.quantize_input(model, image[0, 0]).tolist()
        logger.info("OPENEYE_INPUT_IMAGE: MNIST test image %s (label %d), input scale %g",
                    os.environ["OPENEYE_INPUT_IMAGE"], int(label[0]), model[0].input_scale)
    if os.environ.get("OPENEYE_ZERO_BLOCK"):
        # A block of zero activations in the layer-0 input, so a pass can have no non-zero activation while others
        # have (bug #31; DRAMContents replaces every random 0 by +-1, OPENEYE_ZERO_IACTS zeroes everything): "y:<a>:<b>"
        # zeroes the lines y = a..b-1 of every channel (fmap[c][x][y]), "k:<a>:<b>" the inputs a..b-1 of a Dense layer
        axis, first, last = os.environ["OPENEYE_ZERO_BLOCK"].split(":")
        first, last = int(first), int(last)
        if axis == "k":
            for k in range(first, last):
                dram.fmap[0][k] = 0
        else:
            for channel in dram.fmap[0]:
                for column in channel:
                    for y in range(first, last):
                        column[y] = 0
        logger.info("OPENEYE_ZERO_BLOCK: layer-0 input %s = %d..%d set to 0", axis, first, last - 1)
    # After the debug hooks above, which fill every channel
    channel_pad.fill_padding_channels(model, dram)
    if os.environ.get("OPENEYE_PROFILE"):
        rtl_test_utils.profile_set_layer_input(0, dram.fmap[0])
        rtl_test_utils.profile_set_layer_weights(dram.weights)
    # OPENEYE_KEEP_GOING: a failed iact buffer check between chained layers is
    # logged and the model runs on, so the profiler times every layer (the
    # later layers then compute on wrong inputs); the test still fails at the end.
    failed_iact_checks = []
    test_amount = 1
    for _ in range(test_amount) :
        for layer_number, layer in enumerate(model):
            time_printer.timestamp("Layer parameters created. ", logger)
            calculated_results = tum.collect_results(layer_number, layer_parameters[layer_number], dram, openeye_parameter.SERIAL)
            output_order = tum.make_ref(openeye_parameter, layer_parameters[layer_number], layer_number, dram, calculated_results)
            if os.environ.get("OPENEYE_DUMP_VERIFY") and "Convolution" in str(layer_parameters[layer_number].layer_name):
                # Raw operands, reference and stream order for the independent
                # check tools/verify_conv_output.py (recomputes the layer with
                # numpy, compares every output word of the DUT).
                rtl_test_utils.dump_conv_verify_data(layer_number, layer_parameters[layer_number], dram,
                                                     calculated_results, output_order, openeye_parameter)
            if(logging.DEBUG >= log_level):
                time_printer.timestamp("Reference data created. ", logger)
            dram_layer_content = [dram.fmap[layer_number], dram.weights[layer_number], dram.bias[layer_number]]
            time_printer.timestamp("Start creating stream. " , logger)
            # Sparsity is realized in the DRAM data (write_initial_data_to_dram
            # zeroes ~50% of iacts/wghts when the flags are set). The serial DMA
            # streams must stay on the standard path: iacts are sent as raw
            # pixels (the hardware iact_stream_constructor derives the sparse
            # stream), and the conv weight mapper always emits the
            # overhead-encoded (zero-compressed) SPad format. The mappers'
            # sparse_data=1 re-encoding only applies to the parallel-port flow
            # and is incompatible with the serial conv weight SPad layout.
            stream = tum.write_stream(openeye_parameter, layer_parameters[layer_number], dram_layer_content, 0, 0)
            time_printer.timestamp("Streams set. " , logger)
            for _ in range(1):
                for layer_repetition in range(layer_parameters[layer_number].needed_total_transmissions):
                    gtu.create_stream_file(stream[layer_repetition],layer_number,layer_repetition)
                    if (only_files == 0) :
                        logger.info("Send stream No. " + str(layer_number+1))
                        fc_write_check = None
                        if (os.environ.get("OPENEYE_CHECK_FC_WRITES") and
                                not os.environ.get("OPENEYE_SKIP_FC_WRITE_CHECK") and
                                "Dense" in str(layer_parameters[layer_number].layer_name)):
                            fc_write_check = cocotb.start_soon(rtl_test_utils.check_fc_activation_writes(
                                dut, openeye_parameter, layer_parameters[layer_number], dram.fmap[layer_number]))
                        await cocotb.start_soon(rtl_test_utils.send_stream(ptp, dut, stream[layer_repetition], openeye_parameter, layer_parameters[layer_number], layer_repetition))
                        logger.info("Stream is sent.")
                        if (layer_number == max_layers - 1) :
                            await cocotb.start_soon(rtl_test_utils.await_enable_signal(ptp, dut))
                            if fc_write_check is not None:
                                assert fc_write_check.done(), "FC activation RAM writes incomplete"
                                await fc_write_check
                            if("Depthwise" in str(layer_parameters[layer_number].layer_name)):
                                await cocotb.start_soon(rtl_test_utils.compare_stream_Dw(ptp, dut, layer_number, layer_repetition, layer_parameters[layer_number], openeye_parameter, layer_es, dram, log_level))
                            elif("Conv" in str(layer_parameters[layer_number].layer_name)):
                                await cocotb.start_soon(rtl_test_utils.compare_stream_Conv(ptp, dut, layer_number, layer_repetition, layer_parameters[layer_number], openeye_parameter, layer_es, dram, log_level, output_order))
                            elif("Dense" in str(layer_parameters[layer_number].layer_name)):
                                await cocotb.start_soon(rtl_test_utils.compare_stream_Dense(ptp, dut, layer_number, layer_repetition, layer_parameters[layer_number], openeye_parameter, layer_es, dram, log_level))
                            elif("Pooling" in str(layer_parameters[layer_number].layer_name)):
                                await cocotb.start_soon(rtl_test_utils.compare_stream_Pooling(ptp, dut, layer_number, layer_repetition, layer_parameters[layer_number], openeye_parameter, layer_es, dram, log_level))
                            if os.environ.get("DUMP_PSUM_BUFFERS") and "Dense" in str(layer_parameters[layer_number].layer_name):
                                # Debug listing of every filter; compare_dram_with_ref below
                                # asserts, but only logs the first few mismatches.
                                for f in range(len(calculated_results)):
                                    logger.info("dense f=%2d ref=%s dut=%s", f, calculated_results[f],
                                                dram.fmap[1 + layer_number][f])
                            # Check both decoded values and the complete DMA stream.
                            dram_ok = tum.compare_dram_with_ref(layer_parameters[layer_number], calculated_results, dram.fmap[1 + layer_number])
                            if os.environ.get("OPENEYE_INPUT_IMAGE") and "Dense" in str(layer_parameters[layer_number].layer_name):
                                outputs = [int(dram.fmap[1 + layer_number][f]) for f in range(layer_parameters[layer_number].filters)]
                                logger.info("OPENEYE_INPUT_IMAGE: DUT class %d (raw outputs %s)",
                                            max(range(len(outputs)), key=outputs.__getitem__), outputs)
                            file_ok = True
                            if(logging.DEBUG >= log_level):
                                # A convolution compares only the psum slots that hold an output (bug #9: the slot
                                # after a 7-wide row carries an idle PE's psum); output_order has their positions.
                                slots = None
                                name = str(layer_parameters[layer_number].layer_name)
                                if "Conv" in name and "Depthwise" not in name and openeye_parameter.SERIAL:
                                    slots = output_order[layer_repetition]
                                file_ok = gtu.check_results(openeye_parameter, 'demo/layer_' + str(layer_number) + '_' + str(layer_repetition) + '/dma_stream_ref.txt',\
                                                            'demo/layer_' + str(layer_number) + '_' + str(layer_repetition) + '/output.txt',
                                                            slot_positions=slots)
                            assert dram_ok and file_ok, "result check failed: values %s, reference file %s" % (
                                "ok" if dram_ok else "differ", "ok" if file_ok else "differs")
                        else :
                            await cocotb.start_soon(rtl_test_utils.await_ready_signal(ptp, dut))
                            time_printer.timestamp("Ready signal detected. Start new stream " , logger)
                            dram.fmap[1 + layer_number] = tum.fill_dram_with_ref(calculated_results, dram.fmap[1 + layer_number], layer_parameters[layer_number], layer_parameters[layer_number+1])
                        if (layer_parameters[layer_number].layer_name != "Pooling") :
                            slo.batchnorm_output(layer_parameters[layer_number], 1, layer_number, dram)
                        if os.environ.get("OPENEYE_PROFILE") and layer_number != max_layers - 1:
                            # the activated output = the next layer's input (zeros, for zero skipping)
                            rtl_test_utils.profile_set_layer_input(layer_number + 1, dram.fmap[1 + layer_number])
                        if (layer_number != max_layers - 1) :
                            logger.info("Iact check context: layer %d, repetition %d of %d",
                                        layer_number, layer_repetition,
                                        layer_parameters[layer_number].needed_total_transmissions)
                            # The buffer being checked is the next layer's input, so the
                            # layout parameters that describe it are that layer's.
                            # A Dense layer writes its N outputs back in filter order and
                            # pads the last buffer row with don't-care values (bug #26).
                            valid_values = None
                            if layer_parameters[layer_number].fully_connected:
                                valid_values = layer_parameters[layer_number].filters
                            iact_ok = rtl_test_utils.compare_iact_storage(
                                ptp, dut, dram.fmap[1 + layer_number], openeye_parameter,
                                layer_parameters[layer_number + 1], valid_values=valid_values)
                            if not iact_ok and os.environ.get("OPENEYE_KEEP_GOING"):
                                logger.error("Iact buffer check failed after layer %d (OPENEYE_KEEP_GOING: "
                                             "the model runs on)", layer_number)
                                failed_iact_checks.append(layer_number)
                            else:
                                assert iact_ok
                    else :
                        if (layer_number == max_layers - 1) :
                            dram.fmap[1 + layer_number] = tum.fill_dram_with_ref(calculated_results, dram.fmap[1 + layer_number], layer_parameters[layer_number], layer_parameters[layer_number+1])
                        if (layer_parameters[layer_number].layer_name != "Pooling") :
                            slo.batchnorm_output(layer_parameters[layer_number], 1, layer_number, dram)

    assert not failed_iact_checks, "iact buffer check failed after layer(s) %s" % failed_iact_checks
    if (only_files == 0) :
        assert dut.rst_ni.value == 1, "rst_ni is not 1!"
