import os
import torch
import onnx
from onnx import numpy_helper
import onnxruntime as ort
import numpy as np
from onnxruntime.quantization import (quant_pre_process, quantize_dynamic, quantize_static, QuantType, QuantFormat,
                                      CalibrationDataReader)

# Mantissa of the requantization multiplier: the quantizers multiply by a 25-bit signed mantissa, so at most 24 bits
# (= float32's significand: the multiplier equals ONNX Runtime's float32 scale). Until bug #38 was fixed the RTL kept
# only the low 8 bits of the field, so this was 8.
MANT_BITS = 24
NEG_MANT_BITS = 8   # Leaky ReLU negative slope: the 8-bit status field act_neg_mant (regmap.yaml)
SHIFT_MAX = 127     # 7-bit shift field
COMPUTE_OPS = {'ConvInteger', 'QLinearConv', 'MatMulInteger', 'QLinearMatMul', 'QGemm', 'MaxPool'}
# The other nodes of the quantized graphs the toolchain handles (2026-11-07: the ReLU, Leaky ReLU, SiLU and hard-swish
# MNIST nets of doc/demo_notebooks): data movement, and the activation patterns find_activation / check_fused_relu
# read. check_supported_graph refuses every other node (bug #43: parse_pipeline used to drop them without a word).
PASS_OPS = {'QuantizeLinear', 'DequantizeLinear', 'Flatten', 'Reshape', 'Identity', 'Constant'}
STATIC_ACTIVATION_OPS = {'Relu', 'LeakyRelu', 'QLinearLeakyRelu', 'QLinearSigmoid', 'QLinearMul', 'HardSigmoid',
                         'HardSwish'}
# A dynamically quantized graph (no calibration data) dequantizes every layer in float (DynamicQuantizeLinear, Cast,
# Mul by the scales, Add of the bias) and carries only a ReLU to the hardware (check_fused_relu)
DYNAMIC_OPS = {'DynamicQuantizeLinear', 'Cast', 'Mul', 'Add'}
DYNAMIC_ACTIVATION_OPS = {'Relu'}
CONV_OPS = {'ConvInteger', 'QLinearConv'}

# Activations after a QLinearConv / QGemm of a statically quantized graph, as the planned hardware computes them
# (doc/experiments/2026-11-02_activation_plan.md): "relu" by the quantizer's lower clamp (act_min 0), "leaky_relu"
# by a second slope for negative sums, "silu" and "hardswish" by a 256-entry int8 -> int8 table after the clamp.
ACTIVATION_FUNCTIONS = {
    'leaky_relu': lambda x, alpha: np.where(x >= 0, x, alpha * x),
    'silu': lambda x, alpha: x / (1.0 + np.exp(-x)),
    'hardswish': lambda x, alpha: x * np.clip(x + 3.0, 0.0, 6.0) / 6.0,
}

class TensorShape:
    """Helper class to allow reading shapes via .shape property, similar to TensorFlow."""
    def __init__(self, shape_list):
        # Swap NCHW to NHWC if the shape belongs to a 4D image/feature tensor
        if len(shape_list) == 4:
            # shape_list layout: [batch_size, channels, height, width]
            # target layout:     [batch_size, height, width, channels]
            self.shape = [shape_list[0], shape_list[2], shape_list[3], shape_list[1]]
        else:
            self.shape = shape_list

    def __repr__(self):
        return str(self.shape)

class HardwareLayer:
    """Represents an extracted layer as a configurable hardware object."""
    def __init__(self, index, layer_type, onnx_op, node_name, has_relu, input_shape, output_shape):
        self.index = index
        self.type = layer_type            # Type name (e.g., conv2d, dense, pooling2d)
        self.name = node_name            # Node name within the ONNX graph (get_model renames it for LayerParameters)
        self.node_name = node_name       # Node name within the ONNX graph, kept (check_supported_graph)
        self.onnx_op = onnx_op
        self.has_relu = has_relu
        
        # Nested shape objects convert NCHW arrays automatically to NHWC format
        self.input = TensorShape(input_shape)
        self.output = TensorShape(output_shape)
        self.kernel = TensorShape([0, 0]) 
        
        # Default structural attributes to prevent subscriptable/NoneType crashes
        self.kernel_size = [0, 0]
        self.strides = [1, 1]
        self.padding_pads = [0, 0, 0, 0]
        self.filters = 0                  
        
        # Channel and feature configurations
        self.out_channels = None
        self.in_channels = None
        self.out_features = None
        self.in_features = None
        
        # TensorFlow convention compatibility: weights[0] = Weights, weights[1] = Bias
        self.weights = [None, None]
        self.bias_fp32 = None
        self.bias_int32 = None
        self.scale = None
        self.zero_point = None

        # Activation after the layer (find_activation): "none", "relu", "leaky_relu", "silu" or "hardswish", its
        # Leaky ReLU slope, and the scale of its quantized output (the next layer's input scale; for "relu" the
        # layer's output scale itself). activation_negative_factor: [mant, shift] of the Leaky ReLU slope for negative
        # sums; activation_table: the 256 outputs of the table for the inputs -128 ... 127 ("silu", "hardswish");
        # activation_round: round to nearest instead of the quantizer's floor (on for these three, finish_activations).
        self.activation = 'none'
        self.activation_alpha = None
        self.activation_output_scale = None
        self.activation_negative_factor = None
        self.activation_table = None
        self.activation_round = False

    def __repr__(self):
        return f"<HardwareLayer [{self.index}] {self.type} (Name: {self.name})>"


def export_to_onnx(model, path="simple_mnist_convnet.onnx", input_shape=(1, 1, 28, 28)):
    """Stable export of PyTorch model into ONNX format. input_shape [N, C, H, W] of the dummy input: the shapes of the
    exported graph follow it (get_model takes it from the calibration data; MNIST when there is none)."""
    model.eval()
    dummy_input = torch.randn(*input_shape)
    torch.onnx.export(
        model, dummy_input, path,
        export_params=True, opset_version=18, do_constant_folding=True,
        input_names=['input'], output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}},
        dynamo=False
    )
    print(f"Model successfully exported to {path}!")
    return path

def quantize_to_int8(src_path, dest_path="simple_mnist_convnet_int8.onnx"):
    """Executes graph pre-processing and dynamic quantization to signed INT8."""
    prep_path = "simple_mnist_processed.onnx"
    quant_pre_process(input_model_path=src_path, output_model_path=prep_path)
    quantize_dynamic(
        model_input=prep_path, 
        model_output=dest_path, 
        weight_type=QuantType.QInt8
    )
    if os.path.exists(prep_path):
        os.remove(prep_path)
    print(f"Model successfully saved as SIGNED INT8: {dest_path}")
    return dest_path

def quantize_to_int8_static(src_path, calibration_data, dest_path="simple_mnist_convnet_int8.onnx"):
    """Static quantization for the hardware, calibrated on calibration_data (float32 [N, C, H, W], preprocessed as in
    training). Dynamic quantization keeps the activations in float, so it gives no activation scale and no
    requantization multiplier; the hardware needs both. Activations and weights are symmetric int8 (zero point 0: the
    hardware pads with a raw 0 and skips raw zeros), one weight scale per layer (the quantizer uses filter 0's
    multiplier for every filter, bug #12), QOperator format (QLinearConv / QGemm carry their scales as inputs)."""
    prep_path = "simple_mnist_processed.onnx"
    quant_pre_process(input_model_path=src_path, output_model_path=prep_path)

    class _Calibration(CalibrationDataReader):
        def __init__(self, data):
            self._items = iter({'input': data[i:i + 1].astype(np.float32)} for i in range(len(data)))

        def get_next(self):
            return next(self._items, None)

    quantize_static(prep_path, dest_path, _Calibration(calibration_data), quant_format=QuantFormat.QOperator,
                    activation_type=QuantType.QInt8, weight_type=QuantType.QInt8, per_channel=False,
                    extra_options={'ActivationSymmetric': True, 'WeightSymmetric': True})
    if os.path.exists(prep_path):
        os.remove(prep_path)
    print(f"Model statically quantized to SIGNED INT8 (zero point 0, per tensor): {dest_path}")
    return dest_path

def hardware_multiplier(m, mant_bits=None, shift_max=SHIFT_MAX):
    """Requantization multiplier m as the quantizer's mant / 2^shift: the largest shift for which mant fits mant_bits
    (default MANT_BITS, read at call time)."""
    if mant_bits is None:
        mant_bits = MANT_BITS
    if not m > 0:
        raise ValueError(f"multiplier {m} is not positive")
    shift = 0
    while shift < shift_max and round(m * 2 ** (shift + 1)) < (1 << mant_bits):
        shift += 1
    mant = int(round(m * 2 ** shift))
    if not 0 < mant < (1 << mant_bits):
        raise ValueError(f"multiplier {m} does not fit {mant_bits} mantissa bits and shift <= {shift_max}")
    return mant, shift

def quantize_input(pipeline, x):
    """Float input x (preprocessed as in training) as the int8 activations of the first layer (its input scale, zero
    point 0). Needs a statically quantized pipeline."""
    scale = pipeline[0].input_scale
    return np.clip(np.rint(np.asarray(x, dtype=np.float64) / scale), -128, 127).astype(np.int64)

def build_graph_helpers(onnx_model):
    """Generates maps for look-ahead (ReLU fusion) and quick initializer lookups."""
    onnx_model = onnx.shape_inference.infer_shapes(onnx_model)
    inits = {i.name: numpy_helper.to_array(i) for i in onnx_model.graph.initializer}
    
    next_node_map = {}
    for node in onnx_model.graph.node:
        for inp in node.input:
            next_node_map[inp] = node
            
    return onnx_model, inits, next_node_map

def get_tensor_shapes(onnx_model):
    """Extracts all automatically inferred intermediate tensor shapes."""
    shapes = {}
    graph = onnx_model.graph
    for val in list(graph.value_info) + list(graph.input) + list(graph.output):
        if val.type.tensor_type.HasField("shape"):
            shapes[val.name] = [
                d.dim_value if d.HasField("dim_value") else d.dim_param 
                for d in val.type.tensor_type.shape.dim
            ]
    return shapes

def check_fused_relu(node, next_node_map):
    """Looks ahead in the dataflow to check if the next layer is a ReLU.

    Stops at the next layer's compute node: a static graph puts DequantizeLinear between a QLinearConv and its Relu, and
    without the stop the Relu of a following layer would be taken for this one's (e.g. a MaxPool before a conv)."""
    current_tensor = node.output[0]
    for _ in range(5):
        if current_tensor in next_node_map:
            next_node = next_node_map[current_tensor]
            if next_node.op_type == 'Relu':
                return True
            if next_node.op_type in COMPUTE_OPS:
                break
            current_tensor = next_node.output[0]
        else:
            break
    return False

def tensor_consumers(onnx_model):
    """Every node that reads a tensor (next_node_map keeps only the last one; SiLU's conv output feeds two)."""
    consumers = {}
    for node in onnx_model.graph.node:
        for inp in node.input:
            consumers.setdefault(inp, []).append(node)
    return consumers

def find_activation(node, consumers, inits):
    """Activation applied to the int8 output of a QLinearConv / QGemm in a statically quantized graph:
    (name, Leaky ReLU slope or None, scale of the activation's quantized output or None).

    The patterns ONNX Runtime's static quantization (QOperator) leaves for the PyTorch activations (opset 18):
      LeakyReLU  QLinearLeakyRelu(X = output, Y_scale)
      SiLU       QLinearSigmoid(output) and QLinearMul(output, sigmoid) -> C_scale (x * sigmoid(x))
      Hardswish  DequantizeLinear -> HardSigmoid (alpha 1/6, beta 1/2, float) -> QuantizeLinear, QLinearMul(output,
                 hard sigmoid) -> C_scale (ONNX Runtime has no quantized HardSwish); a HardSwish node left in float
                 between DequantizeLinear and QuantizeLinear is taken as well
      ReLU       DequantizeLinear -> Relu (float): the output scale stays the layer's (check_fused_relu)"""
    out = node.output[0]
    readers = consumers.get(out, [])

    def scale(name):
        return float(np.asarray(inits[name]).ravel()[0])

    def attribute(n, name, default):
        return next((a.f for a in n.attribute if a.name == name), default)

    def mul_with(other):
        return next((n for n in readers if n.op_type == 'QLinearMul' and other in (n.input[0], n.input[3])), None)

    for n in readers:
        if n.op_type == 'QLinearLeakyRelu':
            return 'leaky_relu', attribute(n, 'alpha', 0.01), scale(n.input[3])
        if n.op_type == 'QLinearSigmoid' and mul_with(n.output[0]) is not None:
            return 'silu', None, scale(mul_with(n.output[0]).input[6])
    for dq in (n for n in readers if n.op_type == 'DequantizeLinear'):
        for f in consumers.get(dq.output[0], []):
            if f.op_type == 'Relu':
                return 'relu', None, None
            if f.op_type == 'HardSigmoid':
                if not (abs(attribute(f, 'alpha', 0.2) - 1 / 6) < 1e-6 and abs(attribute(f, 'beta', 0.5) - 0.5) < 1e-6):
                    continue
                for q in consumers.get(f.output[0], []):
                    if q.op_type == 'QuantizeLinear' and mul_with(q.output[0]) is not None:
                        return 'hardswish', None, scale(mul_with(q.output[0]).input[6])
            if f.op_type in ('HardSwish', 'LeakyRelu'):
                for q in consumers.get(f.output[0], []):
                    if q.op_type == 'QuantizeLinear':
                        name = 'hardswish' if f.op_type == 'HardSwish' else 'leaky_relu'
                        return name, attribute(f, 'alpha', 0.01) if name == 'leaky_relu' else None, scale(q.input[1])
    return 'none', None, None

def activation_table(function, alpha, in_scale, out_scale):
    """The table of an int8 -> int8 activation: entry i = clamp(round(f((i - 128) * in_scale) / out_scale), -128, 127),
    rounded half away from zero."""
    y = ACTIVATION_FUNCTIONS[function](np.arange(-128, 128, dtype=np.float64) * in_scale, alpha) / out_scale
    return [int(v) for v in np.clip(np.sign(y) * np.floor(np.abs(y) + 0.5), -128, 127)]

def set_activation(layer_obj, node, consumers, inits):
    """Records the activation of a statically quantized layer (find_activation); finish_activations computes its
    hardware parameters once the whole pipeline is known."""
    if consumers is None:
        return layer_obj
    name, alpha, out_scale = find_activation(node, consumers, inits)
    layer_obj.activation = name
    layer_obj.activation_alpha = alpha
    layer_obj.activation_output_scale = out_scale
    return layer_obj

def _nhwc(shape):
    """A TensorShape that already holds an NHWC (or [batch, features]) list."""
    t = TensorShape([])
    t.shape = list(shape)
    return t

def fill_missing_shapes(pipeline):
    """Shapes ONNX shape inference leaves unknown: it does not know the com.microsoft ops (QLinearLeakyRelu,
    QLinearSigmoid, QLinearMul) of a quantized activation, so the tensors after one have no shape. A layer's input is
    the previous layer's output; a conv or pooling output follows from kernel, padding and stride; a Dense input is
    the flattened previous output."""
    previous = None
    for layer in pipeline:
        if not isinstance(layer.input.shape, list) and previous is not None:
            if layer.type == 'dense':
                n, rest = previous.output.shape[0], previous.output.shape[1:]
                layer.input = _nhwc([n, int(np.prod(rest))])
                layer.output = _nhwc([n, layer.filters])
            else:
                layer.input = _nhwc(previous.output.shape)
        if not isinstance(layer.output.shape, list) and isinstance(layer.input.shape, list) and layer.type != 'dense':
            n, h, w, c = layer.input.shape
            (kh, kw), (sh, sw) = layer.kernel_size, layer.strides
            top, left, bottom, right = layer.padding_pads
            out_h = (h + top + bottom - kh) // sh + 1
            out_w = (w + left + right - kw) // sw + 1
            layer.output = _nhwc([n, out_h, out_w, layer.filters if layer.type == 'conv2d' else c])
        previous = layer
    return pipeline

def finish_activations(pipeline):
    """Hardware parameters of the activations (doc/experiments/2026-11-02_activation_plan.md). The hardware writes a
    layer's activated output straight into the next compute layer's input, so the activation targets that layer's
    input scale (the activation node's own output scale unless ONNX Runtime requantizes in between, e.g. around a
    float Flatten before the Dense; the requantization is folded in). Leaky ReLU: the quantizer requantizes straight
    to the target, quantization_factor ~ s_in * s_w / s_out for sums >= 0 and activation_negative_factor ~
    alpha * s_in * s_w / s_out for negative sums. SiLU, hard-swish: quantization_factor stays the layer's (int8
    pre-activation at the layer's output scale), the table maps it to the target scale. These three round the
    requantization to nearest (activation_round; with the floor Leaky ReLU loses its zeros and every variant drifts
    from ONNX Runtime by -0.5 LSB per layer, doc/experiments/2026-11-02_activation.md); ReLU keeps the floor."""
    for k, layer_obj in enumerate(pipeline):
        name = layer_obj.activation
        if name not in ('leaky_relu', 'silu', 'hardswish'):
            continue
        following = next((l for l in pipeline[k + 1:] if l.type in ('conv2d', 'dense')), None)
        if following is not None and getattr(following, 'input_scale', None):
            layer_obj.activation_output_scale = following.input_scale
        out_scale = layer_obj.activation_output_scale
        layer_obj.activation_round = True
        m = layer_obj.input_scale * layer_obj.scale
        if name == 'leaky_relu':
            layer_obj.quantization_factor = [list(hardware_multiplier(m / out_scale))
                                             for _ in layer_obj.quantization_factor]
            layer_obj.activation_negative_factor = list(hardware_multiplier(layer_obj.activation_alpha * m / out_scale,
                                                                              NEG_MANT_BITS))
        else:
            layer_obj.activation_table = activation_table(name, layer_obj.activation_alpha, layer_obj.output_scale,
                                                          out_scale)
    return pipeline

def extract_conv_params(node, w_arr, attrs):
    """Extracts specific structural hyperparameters for a Convolution."""
    return {
        "kernel_shape": [w_arr.shape[2], w_arr.shape[3]],
        "strides": attrs.get("strides", [1, 1]),
        "padding_pads": attrs.get("pads", [0, 0, 0, 0]),
        "out_channels": w_arr.shape[0],
        "in_channels": w_arr.shape[1]
    }

def process_weights_and_biases(layer_obj, node, inits, input_scale, next_node_map):
    """Extracts parameters and locates the split bias tensor from global initializers."""
    w_name = node.input[1]
    if w_name not in inits:
        return layer_obj
    
    raw_weights = inits[w_name]
    layer_obj.zero_point = 0 
    
    # Extract base name (e.g., "Conv1" from "Conv1.weight_quantized")
    base_name = w_name.split('.')[0]
    
    # 1. Target scale and zero-point retrieval
    for s_name in [f"{w_name}_scale", f"{base_name}.weight_scale", f"{base_name}_scale"]:
        if s_name in inits:
            layer_obj.scale = float(inits[s_name])
            break
    for zp_name in [f"{w_name}_zero_point", f"{base_name}.weight_zero_point"]:
        if zp_name in inits:
            layer_obj.zero_point = int(inits[zp_name])

    # 2. Direct bias lookup using PyTorch naming convention patterns
    possible_biases = [f"{base_name}.bias", f"{base_name}_bias", base_name]
    for b_name in possible_biases:
        if b_name in inits:
            layer_obj.bias_fp32 = inits[b_name]
            break

    # 3. Hardware INT32 bias transformation formula
    if layer_obj.bias_fp32 is not None and layer_obj.scale is not None:
        scale_effective = input_scale * layer_obj.scale
        layer_obj.bias_int32 = np.round(
            layer_obj.bias_fp32 / scale_effective
        ).astype(np.int32)
        
    # 4. Transpose weights to match target extraction sequence [x][y][c][f]
    if layer_obj.type == 'conv2d':
        # ONNX layout:  [f, c, y, x] (out_channels, in_channels, height, width)
        # Desired parsing structure: [x][y][c][f]
        layer_obj.weights[0] = np.transpose(raw_weights, (3, 2, 1, 0))
    else:
        layer_obj.weights[0] = raw_weights
        
    layer_obj.weights[1] = layer_obj.bias_int32
        
    return layer_obj

def process_qlinear(layer_obj, node, inits, consumers=None):
    """QLinearConv / QGemm of a statically quantized graph: the int8 weights, the int32 bias (scale input * weight)
    and the input, weight and output scales are inputs of the node. Sets weights[0] (conv [kernel row][kernel column]
    [channel][filter], the order DRAMContents reads for a Keras kernel; dense [out][in]), weights[1] (bias), the
    scales and quantization_factor ([mant, shift] per filter of the quantizer, mant / 2^shift ~ s_in * s_w / s_out)."""
    if node.op_type == 'QLinearConv':     # x, x_scale, x_zp, w, w_scale, w_zp, y_scale, y_zp, [B]
        x_s, x_zp, w, w_s, w_zp, y_s, y_zp = node.input[1:8]
        b = node.input[8] if len(node.input) > 8 else None
    else:                                 # QGemm: A, a_scale, a_zp, B, b_scale, b_zp, C, y_scale, y_zp (transB = 1)
        x_s, x_zp, w, w_s, w_zp, b, y_s, y_zp = node.input[1:9]
    zero_points = [int(np.asarray(inits[z]).ravel()[0]) for z in (x_zp, w_zp, y_zp) if z in inits]
    if any(zero_points):
        raise ValueError(f"{node.name}: zero points {zero_points}; the hardware needs zero point 0 (symmetric)")
    w_scale = np.asarray(inits[w_s]).ravel()
    if w_scale.size != 1:
        raise ValueError(f"{node.name}: one weight scale per channel; the hardware needs one per layer (bug #12)")
    raw = inits[w].astype(np.int64)
    layer_obj.input_scale = float(np.asarray(inits[x_s]).ravel()[0])
    layer_obj.scale = float(w_scale[0])
    layer_obj.output_scale = float(np.asarray(inits[y_s]).ravel()[0])
    layer_obj.zero_point = 0
    filters = raw.shape[0]
    layer_obj.bias_int32 = inits[b].astype(np.int64) if b else np.zeros(filters, dtype=np.int64)
    if layer_obj.type == 'conv2d':
        # ONNX [filter][channel][kernel row][kernel column] -> [row][column][channel][filter]
        layer_obj.weights[0] = np.transpose(raw, (2, 3, 1, 0))
    else:
        layer_obj.weights[0] = raw                      # [out][in], the input in ONNX's flatten order (NCHW)
        layer_obj.flatten_order = 'NCHW'
    layer_obj.weights[1] = layer_obj.bias_int32
    mant, shift = hardware_multiplier(layer_obj.input_scale * layer_obj.scale / layer_obj.output_scale)
    layer_obj.quantization_factor = [[mant, shift] for _ in range(filters)]
    layer_obj.quantized = True
    return set_activation(layer_obj, node, consumers, inits)

def build_layer_dict(idx, node, shapes, next_node_map):
    """Instantiates a new HardwareLayer object instead of a raw dictionary."""
    op_mapping = {
        'ConvInteger': 'conv2d', 'QLinearConv': 'conv2d',
        'MatMulInteger': 'dense', 'QLinearMatMul': 'dense', 'QGemm': 'dense',
        'MaxPool': 'pooling2d'
    }
    l_type = op_mapping[node.op_type]
    
    return HardwareLayer(
        index=idx,
        layer_type=l_type,
        onnx_op=node.op_type,
        node_name=node.name,
        has_relu=check_fused_relu(node, next_node_map),
        input_shape=shapes.get(node.input[0], "Unknown"),
        output_shape=shapes.get(node.output[0], "Unknown")
    )

def check_supported_graph(onnx_model, inits, pipeline=None):
    """Stop a quantized graph that the hardware pipeline would compute differently from the model (bug #43). The
    pipeline is a chain of COMPUTE_OPS layers; parse_pipeline used to drop every other node without a word, so a
    residual Add, an AveragePool / GlobalAveragePool, a Concat, a Softmax, a grouped or depthwise convolution or an
    unrecognised activation vanished and the hardware computed another network. Refuses:
      * a node outside COMPUTE_OPS, PASS_OPS and the activation ops of the graph's quantization (static: the patterns
        of find_activation; dynamic: only Relu, plus its own DynamicQuantizeLinear / Cast / Mul / Add);
      * a dynamic Add without an initializer input (the bias Add has one; a residual Add adds two activations);
      * a convolution with group, dilations or auto_pad other than 1 / 1 / NOTSET;
      * compute nodes that are not one chain: each one's data input must come, through pass and activation nodes, from
        the previous compute node (the first: from the graph input), so branches and skip connections are refused;
      * with pipeline (after parse_pipeline): an activation node that does not follow a Conv / Dense layer whose
        activation was recognised (e.g. a ReLU after a MaxPool, which the pooling layer does not apply).
    Returns the compute nodes in order."""
    nodes = list(onnx_model.graph.node)
    dynamic = any(n.op_type in ('ConvInteger', 'MatMulInteger', 'DynamicQuantizeLinear') for n in nodes)
    activation_ops = DYNAMIC_ACTIVATION_OPS if dynamic else STATIC_ACTIVATION_OPS
    transparent = PASS_OPS | activation_ops | (DYNAMIC_OPS if dynamic else set())
    unknown = sorted({n.op_type for n in nodes} - COMPUTE_OPS - transparent)
    if unknown:
        raise NotImplementedError(
            f"ONNX nodes {unknown} are not computed by the hardware pipeline (Conv, Gemm / MatMul, 2 x 2 MaxPool and the "
            f"activations ReLU, Leaky ReLU, SiLU, hard-swish); they would be dropped (bug #43)"
            + ("; a dynamically quantized graph carries only ReLU: pass calibration data for static quantization"
               if dynamic else ""))
    producer = {o: n for n in nodes for o in n.output}
    constant = {}

    def is_constant(tensor):
        """A tensor computed from initializers only (the dynamic bias goes through a Reshape)."""
        if tensor not in constant:
            node = producer.get(tensor)
            constant[tensor] = tensor in inits or (node is not None and all(is_constant(i) for i in node.input if i))
        return constant[tensor]

    for n in nodes:
        attrs = {a.name: onnx.helper.get_attribute_value(a) for a in n.attribute}
        if n.op_type == 'Add' and not any(is_constant(i) for i in n.input):
            raise NotImplementedError(f"{n.name}: Add of two activations (residual connection) is not computed by the "
                                      f"hardware pipeline (bug #43)")
        if n.op_type in CONV_OPS:
            auto_pad = attrs.get('auto_pad', b'NOTSET')
            auto_pad = auto_pad.decode() if isinstance(auto_pad, bytes) else auto_pad
            if attrs.get('group', 1) != 1 or any(d != 1 for d in attrs.get('dilations', [1, 1])) or \
                    auto_pad not in ('NOTSET', ''):
                raise NotImplementedError(
                    f"{n.name}: group {attrs.get('group', 1)}, dilations {list(attrs.get('dilations', [1, 1]))}, "
                    f"auto_pad {auto_pad}; the hardware computes one group (no depthwise / grouped convolution), "
                    f"dilation 1 and explicit pads only (bug #43)")

    def source(tensor):
        """The compute node whose output reaches tensor through transparent nodes (their first input), None for the
        graph input."""
        for _ in range(len(nodes) + 1):
            node = producer.get(tensor)
            if node is None or node.op_type in COMPUTE_OPS:
                return node
            tensor = node.input[0]
        return None

    compute = [n for n in nodes if n.op_type in COMPUTE_OPS]
    for i, n in enumerate(compute):
        came_from = source(n.input[0])
        expected = compute[i - 1] if i else None
        if came_from is not expected:
            raise NotImplementedError(
                f"{n.name}: its input comes from {came_from.name if came_from is not None else 'the graph input'}, not "
                f"from {expected.name if expected is not None else 'the graph input'}; the hardware runs one chain of "
                f"layers (no branches or skip connections, bug #43)")
    if pipeline is not None:
        by_node = {layer.node_name: layer for layer in pipeline}
        for n in nodes:
            if n.op_type not in activation_ops:
                continue
            owner = source(n.input[0])
            layer = by_node.get(owner.name) if owner is not None else None
            fused = layer is not None and layer.type in ('conv2d', 'dense') and (
                getattr(layer, 'activation', 'none') != 'none' or (n.op_type == 'Relu' and layer.has_relu))
            if not fused:
                raise NotImplementedError(
                    f"{n.name} ({n.op_type}) after {owner.name if owner is not None else 'the graph input'} is not an "
                    f"activation of a Conv / Dense layer the hardware applies; it would be dropped (bug #43)")
    return compute


def parse_pipeline(onnx_model, inits, next_node_map, shapes):
    """Iterates through nodes to build the clean object-oriented hardware pipeline."""
    pipeline = []
    input_scale = inits.get('input_scale', 1.0)
    consumers = tensor_consumers(onnx_model)
    
    for node in onnx_model.graph.node:
        if node.op_type not in COMPUTE_OPS:
            continue
            
        layer = build_layer_dict(len(pipeline), node, shapes, next_node_map)
        attrs = {a.name: (list(a.ints) if a.type == onnx.AttributeProto.INTS else a.i) for a in node.attribute}
        
        if layer.type in ['conv2d', 'dense']:
            if node.op_type in ('QLinearConv', 'QGemm'):        # statically quantized graph (quantize_to_int8_static)
                layer = process_qlinear(layer, node, inits, consumers)
                w_input = 3
            else:
                layer = process_weights_and_biases(layer, node, inits, input_scale, next_node_map)
                w_input = 1
            if layer.type == 'conv2d' and layer.weights[0] is not None:
                params = extract_conv_params(node, inits[node.input[w_input]], attrs)
                layer.kernel = TensorShape(params["kernel_shape"])
                layer.kernel_size = params["kernel_shape"]
                layer.strides = params["strides"]
                layer.padding_pads = params["padding_pads"]
                layer.out_channels = params["out_channels"]
                layer.in_channels = params["in_channels"]
                layer.filters = params["out_channels"]
            elif layer.type == 'dense' and layer.weights[0] is not None:
                layer.out_features = layer.weights[0].shape[0]
                layer.in_features = layer.weights[0].shape[1]
                layer.filters = layer.weights[0].shape[0]
                if not isinstance(layer.output.shape, list):
                    # ONNX shape inference does not know com.microsoft QGemm: [batch, outputs] from the weights
                    layer.output = TensorShape([layer.input.shape[0], layer.filters])
        elif layer.type == 'pooling2d':
            pool_kernel = attrs.get("kernel_shape", [2, 2])
            layer.kernel = TensorShape(pool_kernel)
            layer.kernel_size = pool_kernel
            layer.strides = attrs.get("strides", [2, 2])
            layer.padding_pads = attrs.get("pads", [0, 0, 0, 0])
            
        pipeline.append(layer)
    return pipeline

def print_summary(pipeline):
    """Prints a structured summary of the custom hardware pipeline."""
    print("\n--- Generated Dynamic Hardware Pipeline (including Tensor Shapes) ---")
    for l in pipeline:
        print(f"[{l.index}] Type: {l.type:<15} | In: {str(l.input.shape):<22} | Out: {str(l.output.shape):<22} | Fused ReLU: {str(l.has_relu)} | Activation: {l.activation}")

def get_model(torch_model, calibration_data=None):
    """Main Orchestrator: Controls export, quantization, parsing, and verification.

    calibration_data (float32 [N, C, H, W], preprocessed as in training): quantize statically for the hardware
    (quantize_to_int8_static); without it the weights only are quantized (dynamic), as before."""
    # The dummy input of the export has the calibration data's shape (MNIST 1 x 28 x 28 without calibration data)
    shape = (1,) + tuple(np.asarray(calibration_data).shape[1:]) if calibration_data is not None else (1, 1, 28, 28)
    fp32_path = export_to_onnx(torch_model, input_shape=shape)
    if calibration_data is None:
        int8_path = quantize_to_int8(fp32_path)
    else:
        int8_path = quantize_to_int8_static(fp32_path, calibration_data)
    
    loaded_model = onnx.load(int8_path)
    onnx_model, inits, next_node_map = build_graph_helpers(loaded_model)
    shapes = get_tensor_shapes(onnx_model)
    
    pipeline = finish_activations(fill_missing_shapes(parse_pipeline(onnx_model, inits, next_node_map, shapes)))
    check_supported_graph(onnx_model, inits, pipeline)      # nothing of the model may be dropped (bug #43)
    print_summary(pipeline)
    
    for layer_number in range(len(pipeline)):
        # LayerParameters picks the layer type, and max or average pooling ("max" in the name), from the name
        pipeline[layer_number].name = {'MaxPool': 'max_pooling2d', 'AveragePool': 'average_pooling2d'}.get(
            pipeline[layer_number].onnx_op, pipeline[layer_number].type)
    
    # =========================================================================
    # STABLE HARDWARE REFERENCE GENERATOR (Via Graph Modification)
    # =========================================================================
    raw_fp32_model = onnx.load("simple_mnist_convnet.onnx")
    target_fp32_tensor = None
    for node_fp32 in raw_fp32_model.graph.node:
        if node_fp32.op_type == 'MaxPool':
            target_fp32_tensor = node_fp32.output[0]
            break

    if target_fp32_tensor is not None:
        try:
            new_output = onnx.ValueInfoProto()
            new_output.name = target_fp32_tensor
            raw_fp32_model.graph.output.append(new_output)
            
            debug_model_path = "simple_mnist_convnet_debug_nodes.onnx"
            onnx.save(raw_fp32_model, debug_model_path)
            
            session_fp32 = ort.InferenceSession(debug_model_path)
            test_image_fp32 = np.zeros((1, 1, 28, 28), dtype=np.float32)
            test_image_fp32[0, 0, 5, 5] = 1.0
            input_name_fp32 = session_fp32.get_inputs()[0].name
            
            outputs_fp32 = session_fp32.run([target_fp32_tensor], {input_name_fp32: test_image_fp32})
            fp32_intermediate_values = outputs_fp32[0]
            
            if os.path.exists(debug_model_path):
                os.remove(debug_model_path)
            
            conv2_scale = pipeline[2].scale if pipeline[2].scale is not None else 1.0
            input_for_conv2_int8 = np.round(fp32_intermediate_values / conv2_scale).astype(np.int8)
            
        except Exception as e:
            print(f"\n[Hint] Failed executing intermediate FP32 simulation: {e}")
            
    return pipeline