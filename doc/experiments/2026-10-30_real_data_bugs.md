# 2026-10-30: three hardware bugs seen with real MNIST data (#31, #32, #33), not investigated

Found while running the trained MNIST int8 model (`doc/demo_notebooks/mnist_quantized_model.tflite`) on real test images
through the RTL. The code that did it (`src/open_eye/ptq.py`, testbench hook `OPENEYE_PTQ`, `test/test_ptq.py`,
`test/cocotb_fpga/test_ptq_mnist.py`, commit `440f36d`) was reverted at the user's request: the project keeps its own
Python flow. This file keeps the record of the bugs; reproduce them on `440f36d` (section 4).

## 1. Setup

Each layer of the trained model ran alone on the RTL (raw psums read out) with the model's own int8 weights, biases in psum
units, and as input the model's int8 activation at that layer for test images 0 and 1 (labels 7 and 2): conv1 on the image
(28x28, padded to 2 channels for bug #17), conv2 on pool1's output, conv3 on pool2's output, and fc1's first 10 outputs on
conv3's output (the whole 3136 -> 64 layer hits bug #29). Activations were quantized with zero point 0, weights per tensor
(one multiplier per layer). Platform as `test/cocotb_fpga/test_conv_const._run_conv_const`: 2x2 clusters, NUM_GLB_IACT 1,
NUM_GLB_PSUM 4, 20-bit psums, DMA 64 bit.

The testbench reference was checked twice: against a numpy model of the int8 network, and by `tools/verify_conv_output.py`
(numpy recomputed from the raw integers the DUT received, `OPENEYE_DUMP_VERIFY=1`): 0 differences in conv1-3. The DUT is
wrong:

| Layer (input zeros) | Images 0 and 1 |
|---|---|
| conv1 on the image (85 % of the pixels 0) | DUT = **bias** at all 25,088 outputs: 6,591 differ (image 0) from numpy (the outputs whose products do not sum to 0) |
| conv2 on pool1's output (68 %) | DUT = bias at 12,320 of 12,544 outputs; all 12,544 differ (image 0) |
| conv3 on pool2's output (73 %) | products right; DUT - numpy constant per filter, in pairs: f0 -21 / f1 +21, f2 -81 / f3 +81, f4 -847 / f5 +847 |
| fc1 rows 0-9 on conv3's output (78 %) | image 1: 10/10 bit-exact; image 0: 10/10 differ (-6,372 .. +5,276) |
| the model on chip (Conv 32, MaxPool, Conv 64, MaxPool, Conv 64, Dense 3136 -> 10 probe of fc1) | the buffer after the first max pooling holds the per-channel background (the output for a blank image) at every position (image 0: 1,220 of 6,272 values wrong) |

## 2. The bugs

* **#31: products lost on real sparse inputs.** conv1 and conv2 return the bias where the products should add up. The same
  layers pass with random data (`test_mnist_layers.py`, random and trained-weight conv1/2/3) because `DRAMContents` replaces
  every zero activation by +-1: no layer loaded through the DMA had zero runs before. The fused-ReLU tests
  (`test_int8_clamp.py`, the paper network with ReLU) only had zeros written back on chip, and scattered. conv3 (7 pixels
  wide, one x pass) keeps its products with 73 % zeros. Candidates: the Python iact stream for sparse data, or
  `iact_stream_constructor` / the PE side.
* **#32: biases of the filter pairs (2k, 2k+1) swapped in conv3 (7x7x64 -> 64).** The offsets are exactly
  b[2k+1] - b[2k] and its negative (conv3 biases -398, -419, -423, -504, -126, -973, ...). Every earlier test gave all filters
  bias 1; conv1 and conv2 return their own bias. Cheap reproduction without the model: conv 7x7x64 -> 64 with random data and
  `OPENEYE_BIAS_STEP`. Candidates: bias order in `psum_stream_mapper` or the RTL for this geometry (4 cluster columns used).
* **#33: Dense 3136 -> 10 wrong on image 0's input, right on image 1's.** Not explained by a shift of the inputs (+-1, 2, 4, 8),
  a swap of input or bias pairs, or a dropped block of inputs (blocks of 8 .. 2048).

The testbench skips the buffer check after a conv layer that is followed by pooling (no pooling layout), so in the chained run
#31 shows only after the pooling.

## 3. What this means

Random test data hides all three: it has no zero activations at the DMA input and the same bias for every filter. Any real
model (zeros after ReLU, background pixels, distinct biases) meets them. Testing with zeros in the input and distinct biases
(`OPENEYE_BIAS_STEP`) is worth adding to the regression once they are understood.

## 4. Reproduction (code of commit 440f36d)

```bash
git worktree add ../oe_ptq 440f36d
cd ../oe_ptq
export PYTHONPATH=$PWD/src      # the venv's editable open_eye points to OpenEye_orig/src, which no longer has ptq.py
cp ../OpenEye_orig/doc/demo_notebooks/mnist_quantized_model.tflite doc/demo_notebooks/   # *.tflite is git-ignored
../OpenEye_orig/venv/bin/python -m pytest -q "test/cocotb_fpga/test_ptq_mnist.py::test_ptq_layer[conv1-0]"   # xfail(strict) = the bug is there
# other ids: conv2-0, conv3-0, fc1_probe-0 (fc1_probe-1 passes), test_ptq_mnist[0] (the chained model)
OPENEYE_DUMP_VERIFY=1 ../OpenEye_orig/venv/bin/python -m pytest -q "test/cocotb_fpga/test_ptq_mnist.py::test_ptq_layer[conv3-0]"
../OpenEye_orig/venv/bin/python tools/verify_conv_output.py "test/.temp/test_cocotb_fpga_test_ptq_mnist.py_test_ptq_layer_conv3-0_"
git worktree remove ../oe_ptq      # afterwards
```

Single layers take 1-8 minutes, the chained model about 5 minutes up to the failure. Needs `~/.keras/datasets/mnist.npz`.
Checked on 2026-10-30 after the revert: `fc1_probe-0` xfailed (#33 there), `fc1_probe-1` passed.
