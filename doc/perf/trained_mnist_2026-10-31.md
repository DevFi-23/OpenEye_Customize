# 2026-10-31: per-layer profile of the trained MNIST model on the RTL (real images)

After the fixes of bugs #31 and #32 (2026-10-30) the trained model runs on chip bit-exact. Profiles of four runs, files
`trained_mnist_2026-10-31/trained_mnist_img<i>.json`
(`venv/bin/python -m open_eye.profile_report --clock-mhz 250 doc/perf/trained_mnist_2026-10-31/*.json`).

* Model: `models/mnist_conv_net.SimpleMNISTConvNet` with the checkpoint `doc/demo_notebooks/mnist_unquantized_model.pth`
  (99.35 %), through the toolchain (`USE_RANDOM_VALUES=0`, `OPENEYE_MODEL_WEIGHTS`): `onnx2model` static int8 quantization
  (200 calibration images, zero point 0, one scale per layer), Conv 3x3 1->32 + ReLU, MaxPool, Conv 32->64 + ReLU, MaxPool,
  Conv 64->64 + ReLU, Dense 3136 -> 10, on chip end to end (write-back and pooling on chip).
* Input: MNIST test images 0, 1, 2, 7 (labels 7, 2, 1, 9; `OPENEYE_INPUT_IMAGE`), normalised as in training and quantized
  with the input scale 0.0222 (the background becomes -19, so the input has no zero); padded to 2 channels (bug #17).
* Platform: the MNIST_REAL case of the baseline (2x2 clusters, NUM_GLB_IACT 1, NUM_GLB_PSUM 4, psum 20 bit, DMA 64 bit,
  QUANT_AMOUNT 64), ideal memory. Every buffer check and the Dense psums bit-exact, DUT class = label on all four.
  Run with `doc/experiments/2026-10-30_bug32/run35.py prof_img<i> <i> OPENEYE_PROFILE=1`.

| Image | Cycles | us at 250 MHz | Conv1 | Pool1 | Conv2 | Pool2 | Conv3 | Dense |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 219,598 | 878.4 | 32,980 | 5,213 | 112,458 | 2,861 | 52,978 | 13,108 |
| 1 | 220,941 | 883.8 | 32,980 | 5,213 | 112,586 | 2,861 | 54,270 | 13,031 |
| 2 | 213,040 | 852.2 | 32,980 | 5,213 | 108,423 | 2,861 | 50,538 | 13,025 |
| 7 | 218,374 | 873.5 | 32,980 | 5,213 | 110,858 | 2,861 | 53,458 | 13,004 |
| `model_mnist_real_c1` (baseline, random weights and data) | 240,671 | 962.7 | 32,980 | 5,213 | 120,807 | 2,861 | 64,813 | 13,997 |

Image 0 by phase: compute 126,318 (57.5 %), load_wght 39,120 (17.8 %), load_bias 23,308 (10.6 %), writeback 11,951 (5.4 %),
convert_iact 10,376 (4.7 %), pooling 7,952 (3.6 %), load_iact / config / quant 559, readout 14. Everything but compute is
the same as with random data (the streams depend on the shape only).

Only the compute phase depends on the data (zero skipping):

| Layer (image 0) | zeros in its input, trained / random | compute, trained | compute, random | change |
|---|---:|---:|---:|---:|
| Conv1 | 0 % / 0 % (image channel; the normalised background is -19) | 9,582 | 9,582 | 0 |
| Conv2 | 44 % / 6 % | 81,489 | 89,838 | -9 % |
| Conv3 | 87 % / 11 % | 31,801 | 43,636 | -27 % |
| Dense | 74 % / 10 % | 3,446 | 4,335 | -21 % |

Random data has zeros too after the first layer (small values after the shift by 7, no ReLU; testbench reference of
MNIST_REAL with seed 1). The saving is much smaller than the difference in zeros: the passes keep their fixed cost (loading, the pass handshake, the
psum read-out of every pass) whatever the activations are. Over images 0-7 the zeros are 43-45 % (Conv2 input), 82-91 %
(Conv3 input), 74-78 % (Dense input).
