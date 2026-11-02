# This file is part of the OpenEye project.
# © Fachhochschule Dortmund – University of Applied Sciences and Arts (until 2025), Universität Duisburg-Essen (since 2025).
# SPDX-License-Identifier: SHL-2.1
# For more details, see the LICENSE file in the root directory of this project.
import logging
import subprocess
import os
from unittest import case
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import tempfile
import math
import tensorflow as tf

logger = logging.getLogger("cocotb")

# Input transform the PyTorch MNIST model was trained with (doc/demo_notebooks/mnist_pytorch.ipynb:
# transforms.Normalize((0.1307,), (0.3081,)) after ToTensor, i.e. pixel / 255)
MNIST_MEAN, MNIST_STD = 0.1307, 0.3081


def mnist_images(split, indices):
    """MNIST images preprocessed as the PyTorch model of models/mnist_conv_net.py was trained: (pixel / 255 - mean) / std,
    float32 [N, 1, 28, 28] (NCHW), and their labels. split: "train" or "test" (tf.keras.datasets cache)."""
    import numpy as np
    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    x, y = (x_train, y_train) if split == "train" else (x_test, y_test)
    idx = list(indices)
    return ((x[idx].astype(np.float32) / 255.0 - MNIST_MEAN) / MNIST_STD)[:, None], y[idx]

def set_test_activation(layers, spec):
    """The test hook OPENEYE_ACTIVATION (create_layer): activation settings on Keras layers, read by
    LayerParameters through openeye_activation / activation_negative_factor / activation_table / activation_round /
    activation_keep_table (the Keras `activation` of a layer stays as it is)."""
    import numpy as np
    items = spec.split(":")
    rounding = "round" in items
    keep = "keep" in items
    items = [i for i in items if i not in ("round", "keep")]
    table = None
    if items and items[0] == "table":
        if items[1:2] == ["random"]:
            seed = int(os.environ.get("OPENEYE_SEED", "0"))
            table = [int(v) for v in np.random.default_rng(seed).integers(-128, 128, 256)]
        else:
            from open_eye import onnx2model
            table = onnx2model.activation_table(items[1], 0.1, float(items[2]), float(items[3]))
    for n, layer in enumerate(layers):
        layer.activation_round = rounding
        if items and items[0] == "leaky":
            layer.openeye_activation = "leaky"
            layer.activation_negative_factor = [int(items[1]), int(items[2])]
        elif table is not None:
            layer.openeye_activation = "table"
            layer.activation_table = list(table)
            layer.activation_keep_table = keep and n > 0


def create_layer(layer_mode, filters, kernelsize_x, kernelsize_y, inputsize_x, inputsize_y, strides, channels, outputsize):
    """Create a TensorFlow/Keras neural network layer based on the specified configuration.

    Constructs a Keras Sequential model containing the requested layer type with the
    given parameters. Supports various layer types including convolution, depthwise
    convolution, fully connected (dense), and pooling layers.

    Args:
        layer_mode (str): Type of layer to create. Supported values:
            - "Convolution": Legacy two-layer convolution model
            - "Convolution_Single": One 2D convolution layer (no write-back)
            - "Convolution_Stack": Two stacked 2D convolution layers (exercises
              the interlayer psum->iact write-back)
            - "Depthwise_Convolution": Depthwise 2D convolution layer
            - "FC": Fully connected (Dense) layer
            - "Pooling": Conv2D followed by MaxPooling2D and another Conv2D
            - "Pooling_OLD": Conv2D, MaxPooling2D, and Dense layer sequence
            - "MNIST": Conv-MaxPool-Conv-MaxPool-Conv-Dense net on 28x28x2 (16 filters)
            - "MNIST_REAL": the architecture of models/mnist_conv_net.py (32/64/64
              filters, FC 3136 -> 10); `channels` = input depth (2 pads the real 1)
            - "PAPER_MNIST": the network of Table 2 of the OpenEye paper (arXiv
              2606.01450): Conv 16, MaxPool, Conv 32, MaxPool, Conv 32, Dense 32, Dense 10
            - "MLP": Dense 6 -> 32 -> 16 -> 4
            - "DENSE_CHAIN_<K>_<N1>_<N2>...": Dense layers K -> N1 -> N2 ... on an
              input of shape (1, 1, K) (on-chip Dense -> Dense write-back, bug #26)
            - any of the above with the suffix "_RELU": every Conv2D/Dense except the
              last one gets activation='relu' (a fused ReLU, realised by the
              quantizer's saturation, LayerParameters.act_min = 0)
        Test hook OPENEYE_QUANT_SHIFT=<s>: every Conv2D/Dense quantizes with
        multiplier 1 and shift s (quantization_factor), so a small s drives values
        out of the int8 range and exercises the saturation.
        Test hook OPENEYE_ACTIVATION (activation hardware, LayerParameters.act_mode;
        every Conv2D/Dense except the last; items separated by ":"):
            leaky:<mant>:<shift>          Leaky ReLU, negative sums use [mant, shift]
            table:random                  a random int8 table (seed OPENEYE_SEED)
            table:<f>:<s_in>:<s_out>      the table of f = silu / hardswish / leaky_relu
                                          from the int8 scale s_in to s_out
            round                         alone or as an extra item: round to nearest
            keep                          extra item of a table: the layers after the
                                          first keep its table (same table, no reload)
        filters (int): Number of output filters/channels for convolution layers
        kernelsize (int): Size of the convolution kernel (assumes square kernel)
        inputsize_x (int): Width of the input tensor
        inputsize_y (int): Height of the input tensor
        strides (int or tuple): Stride value(s) for convolution operations
        channels (int): Number of input channels
        outputsize (int): Number of output units for fully connected layers

    Returns:
        tf.keras.models.Sequential: Compiled Keras Sequential model containing the
            specified layer(s). The model is compiled with Adam optimizer and
            sparse categorical crossentropy loss.

    Note:
        - All convolution layers use "same" padding
        - The "Pooling" and "Pooling_OLD" modes use hardcoded dimensions for
          specific network architectures
        - Invalid layer_mode values will log an error and return an empty model
    """
    logger.debug("Start compiling.")
    # Deterministic weight initialization when a seed is provided. Without
    # this, Keras draws fresh random weights every run, which makes GEMM/Dense
    # layer tests non-reproducible (a given run may pass or fail purely on the
    # random draw). Set OPENEYE_LAYER_SEED to fix the weights across runs.
    _seed = os.environ.get("OPENEYE_LAYER_SEED")
    if _seed is not None:
        import numpy as np
        tf.keras.utils.set_random_seed(int(_seed))
        np.random.seed(int(_seed))
    model = tf.keras.models.Sequential()
    relu = layer_mode.endswith("_RELU")
    if relu:
        layer_mode = layer_mode[:-len("_RELU")]
    match layer_mode:
        case "Convolution_Single":
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides=strides))
        case "Convolution":
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides = strides))
            #model.add(tf.keras.layers.Conv2D(filters, (3, 3), padding="same", input_shape=(inputsize_x, inputsize_y, filters), strides = 1))
            #model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, filters), strides = strides))
            #model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, filters), strides = strides))
            #model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(64, 4, filters), strides = 1))
            #model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(64, 4, filters), strides = 1))
            #model.add(tf.keras.layers.Flatten())
            #model.add(tf.keras.layers.Dense(units=outputsize, use_bias = True))

        case "Convolution_Stack":
            # Two stacked Conv2D layers. The first layer's psums are quantised
            # and written back into the iact buffer as the second layer's input,
            # so this mode exercises the interlayer psum->iact write-back that
            # "Convolution_Single" never reaches.
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides = strides))
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, filters), strides = strides))
        case "Conv_Pool_Conv":
            # Conv, 2x2 max-pool, conv: the smallest net whose pooling output is
            # written back into the iact buffer and read by a conv layer, as in
            # the MNIST net, without its 28x28 input.
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides = strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size = (2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(math.ceil(inputsize_x/2), math.ceil(inputsize_y/2), filters), strides = strides))
        case "Conv_Pool_Conv_Pool_Conv":
            # As Conv_Pool_Conv with a second pool/conv pair: catches state that
            # the first pooling pass leaves behind for the second, as in MNIST.
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides = strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size = (2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(math.ceil(inputsize_x/2), math.ceil(inputsize_y/2), filters), strides = strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size = (2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(math.ceil(inputsize_x/4), math.ceil(inputsize_y/4), filters), strides = strides))
        case "Depthwise_Convolution":
            model.add(tf.keras.layers.DepthwiseConv2D((kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides = strides))
        case "GEMM":
            # Pure matrix multiplication C = A x B (+ bias), realized as a single
            # Dense layer. Combined with DATAFLOW="output_stationary" (or the
            # GemmMapper) it runs on the output-stationary GEMM datapath
            # (gemm_mode=1) instead of the row-stationary conv routing.
            model.add(tf.keras.layers.Dense(input_shape=(inputsize_x,), units=outputsize, use_bias=True))
        case "FC":
            #model.add(tf.keras.layers.Conv2D(filters, (kernelsize_x, kernelsize_y), padding="same", input_shape=(inputsize_x, inputsize_y, channels), strides = strides))
            #model.add(tf.keras.layers.Flatten())
            #model.add(tf.keras.layers.Dense(units=10, use_bias = True))
            #model.add(tf.keras.layers.Dense(units=outputsize, use_bias = True))
            model.add(tf.keras.layers.Dense(input_shape=(1,1,inputsize_x), units=outputsize, use_bias = True))
        case "MNIST":
            x_axis = 28
            y_axis = 28
            channels = 2
            filters = 16
            pool_x_axis = 2
            pool_y_axis = 2
            
            model.add(tf.keras.layers.Conv2D(filters, (3, 3), padding="same", input_shape=(x_axis, y_axis, channels), strides = strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size = (pool_x_axis, pool_y_axis), strides=(pool_x_axis,pool_y_axis), padding="valid"))
            channels = filters
            x_axis   = math.ceil(x_axis/pool_x_axis)
            y_axis   = math.ceil(y_axis/pool_y_axis)
            filters  = 16
            model.add(tf.keras.layers.Conv2D(filters, (3, 3), padding="same", input_shape=(x_axis, y_axis, channels), strides = strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size = (pool_x_axis, pool_y_axis), strides=(pool_x_axis,pool_y_axis), padding="valid"))
            channels = filters
            x_axis   = math.ceil(x_axis/pool_x_axis)
            y_axis   = math.ceil(y_axis/pool_y_axis)
            filters  = 16
            model.add(tf.keras.layers.Conv2D(filters, (3, 3), padding="same", input_shape=(x_axis, y_axis, channels), strides = strides))
            model.add(tf.keras.layers.Flatten())
            output_size  = 10
            model.add(tf.keras.layers.Dense(units=output_size, use_bias = True))
        case "MNIST_REAL":
            # The architecture of models/mnist_conv_net.py (Conv 32, MaxPool,
            # Conv 64, MaxPool, Conv 64, FC 3136 -> 10) with random weights.
            # `channels` is the input depth: 1 is the real model, 2 pads it
            # with a zero channel (works around bug #17, one input channel on
            # images wider than one x pass). The 64-filter layers need
            # QUANT_AMOUNT >= 64.
            model.add(tf.keras.layers.Conv2D(32, (3, 3), padding="same", input_shape=(28, 28, channels), strides=strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(64, (3, 3), padding="same", input_shape=(14, 14, 32), strides=strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(64, (3, 3), padding="same", input_shape=(7, 7, 64), strides=strides))
            model.add(tf.keras.layers.Flatten())
            model.add(tf.keras.layers.Dense(units=10, use_bias=True))

        case "PAPER_MNIST":
            # Table 2 of the OpenEye paper (arXiv 2606.01450), the network of its
            # Table 3 timing: 28x28x1 -> Conv 16, MaxPool, Conv 32, MaxPool,
            # Conv 32, Flatten (1568), Dense 32, Dense 10, random weights.
            model.add(tf.keras.layers.Conv2D(16, (3, 3), padding="same", input_shape=(28, 28, channels), strides=strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(32, (3, 3), padding="same", input_shape=(14, 14, 16), strides=strides))
            model.add(tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding="valid"))
            model.add(tf.keras.layers.Conv2D(32, (3, 3), padding="same", input_shape=(7, 7, 32), strides=strides))
            model.add(tf.keras.layers.Flatten())
            model.add(tf.keras.layers.Dense(units=32, use_bias=True))
            model.add(tf.keras.layers.Dense(units=10, use_bias=True))

        case "AveragePooling":
            x_axis = inputsize_x
            y_axis = inputsize_y

            model.add(tf.keras.layers.Conv2D(
                filters, 
                (3, 3), 
                padding="same",
                input_shape=(x_axis, y_axis, channels), 
                strides=strides
            ))

            pool_x_axis = 4
            pool_y_axis = 4
            model.add(tf.keras.layers.AveragePooling2D(
                pool_size=(pool_x_axis, pool_y_axis), 
                strides=(pool_x_axis, pool_y_axis), 
                padding="valid"
            ))
            model.add(tf.keras.layers.Flatten())
            model.add(tf.keras.layers.Dense(units=outputsize, use_bias = True))
                      
        case "MaxPooling":
            x_axis = inputsize_x
            y_axis = inputsize_y
            model.add(tf.keras.layers.Conv2D(
                filters, 
                (3, 3), 
                padding="same",
                input_shape=(x_axis, y_axis, channels), 
                strides=strides
            ))

            pool_x_axis = 2
            pool_y_axis = 2
            model.add(tf.keras.layers.MaxPooling2D(
                pool_size=(pool_x_axis, pool_y_axis), 
                strides=(pool_x_axis, pool_y_axis), 
                padding="valid"
            ))
            model.add(tf.keras.layers.Flatten())
            model.add(tf.keras.layers.Dense(units=outputsize, use_bias = True))
            """x_axis = math.ceil(x_axis/pool_x_axis)
            y_axis = math.ceil(y_axis/pool_y_axis)
            model.add(tf.keras.layers.Conv2D(
                filters, 
                (3, 3), 
                padding="same",
                input_shape=(x_axis, y_axis, channels), 
                strides=strides
            ))"""
        case _ if layer_mode.startswith("DENSE_CHAIN_"):
            sizes = [int(v) for v in layer_mode[len("DENSE_CHAIN_"):].split("_")]
            model.add(tf.keras.layers.Dense(input_shape=(1, 1, sizes[0]), units=sizes[1], use_bias=True))
            for units in sizes[2:]:
                model.add(tf.keras.layers.Dense(units=units, use_bias=True))
        case "MLP":
            inputsize_x = 6
            model.add(tf.keras.layers.Dense(input_shape=(1,1,inputsize_x), units=32, use_bias = True))
            model.add(tf.keras.layers.Dense(units=16, use_bias = True))
            model.add(tf.keras.layers.Dense(units=4, use_bias = True))
            """
            model.add(tf.keras.layers.Flatten())

            outputsize = 32
            model.add(tf.keras.layers.Dense(units=outputsize, use_bias=True))"""
        case _:
            logger.error("Layer not detected!")

    weighted = [layer for layer in model.layers
                if isinstance(layer, (tf.keras.layers.Conv2D, tf.keras.layers.Dense))]
    if relu:
        for layer in weighted[:-1]:
            layer.activation = tf.keras.activations.get("relu")
    shift = os.environ.get("OPENEYE_QUANT_SHIFT")
    if shift:
        for layer in weighted:
            outputs = layer.units if isinstance(layer, tf.keras.layers.Dense) else layer.filters
            layer.quantization_factor = [[1, int(shift)] for _ in range(outputs)]
    if os.environ.get("OPENEYE_ACTIVATION"):
        set_test_activation(weighted[:-1], os.environ["OPENEYE_ACTIVATION"])

    # Compile the model
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    logger.debug("Model compiled.")
    return model
