# 2026-11-18: sparse / dense per layer, steps 0 and 1 (verification, new baselines, measurement, evaluation)

Plan: README_FI section 2, "Chọn sparse / dense theo layer: kế hoạch từng bước". The user approved steps 0 and 1
and asked for an evaluation: what each layer gains against the resources it costs (is it worth it), with the profiler
phases of the different cases, against today's hardware. No RTL changed; one testbench hook was added (step 1b).

Terms used below:
- **Sparse HW** is today's default build: `SPARSITY_EN=1`, with the bias table and the #49 fix.
- **Dense HW** is the `SPARSITY_EN=0` build.
- **P1** keeps the sparse FSM and chooses the weight format per layer: CSC 12 bit as today, or 8-bit raw words expanded to 12-bit fields in `GET_WGHT`. P1 is estimated: the sparse layer with the dense HW's `load_wght`.
- **P2** chooses the FSM per layer: both FSMs in every PE.

## Step 0: the committed state `ae5665f` (#49 fix, bias table on by default)

Driver `2026-11-18_layer_mode_study/step01.sh` ran all steps one after another, from 2026-11-17 22:08 to 2026-11-18 03:33.

| Check | Result |
|---|---|
| Python unit tests | 504 PASS + the 11 known failures of `test_dense_output.py` |
| Regression `regression.sh` (with `test_bias_per_filter`, `test_bug49`) | **225 = 221 PASS + 4 known xfail** |
| `test_bug49` (CR 2 X 2 Y 3 / Y 4, ReLU, sparse) | 2/2 PASS: **#49 is fixed** |
| New testbench check of a convolution output read by a pooling layer (`compare_pooling_input`) | 129 checks in the last logs, 48 to 25,088 values each, all with 0 differing values and 0 skipped: the buffer layout is right at CR 1, 2, 4 and 8 |
| 12 baseline cases against `bias_2026-11-17_on` (before the #49 fix) | 11 identical; `model_mnist_real_c1` +1 cycle (Conv 7×7×64: the collection waits one cycle for an odd column, as the fix intends) |
| Table 3 sparse (16 configurations) | 16/16 PASS, every configuration identical to `paper_table3_2026-11-17_bias` |
| Table 3 dense | 16/16 PASS |
| Table 3 with ReLU, sparse | **16/16 PASS**: before the #49 fix 14/16, with CR 2 X 2 Y 3 / Y 4 wrong |
| Trained MNIST, 4 activations × 2 modes | 8/8 PASS |
| Vivado (4 ns, place and route, default build; `doc/synth/2026-11-18_route4ns_default_zu7ev`) | 0 CRITICAL, 310 warnings (same IDs and counts as the bias run); **250 MHz met**, WNS +0.096 ns post-route; LUT 60,113, FF 39,556, BRAM 188, URAM 12, DSP 4. The #49 fix costs no measurable logic: `psum_pipeline` has the same LUT count post-synthesis, +20 LUT for the whole design. |

New baselines of the default build (they replace `baseline_2026-11-04` and `paper_table3_2026-11-04`, which were made without the bias table):

| Baseline | Directory | Contents |
|---|---|---|
| 12 cases | `doc/perf/baseline_2026-11-18` (+ `.md`) | |
| Table 3 sparse | `doc/perf/paper_table3_2026-11-18` | sum of the 16 configurations 1,584,737 cycles |
| Table 3 dense | `doc/perf/paper_table3_2026-11-18_dense` | 1,472,347 cycles |
| Table 3 with ReLU, sparse | `doc/perf/paper_table3_2026-11-18_relu_sparse` | 1,518,296 cycles |
| Trained MNIST | `doc/perf/activation_2026-11-18/trained_<act>_img0_<sparse\|dense>.json` | |

With the bias table on, the dense and ReLU runs of 2026-11-17 got −4 to −20 % per configuration.

## Step 1: what was run

| Part | What |
|---|---|
| (a) | Per-layer and per-phase tables, sparse against dense HW. Runs: trained MNIST (Conv 32, Pool, Conv 64, Pool, Conv 64, Dense 3136 → 10; CR 2 X 4 Y 3; 4 activations) and the Table 2 network of the paper (16 configurations, no activation and ReLU). Output: `2026-11-18_layer_mode_study/networks.md`. |
| (b) | Testbench hook `OPENEYE_IACT_ZERO_FRACTION` (`src/open_eye/DRAM.py`, `apply_iact_zero_fraction`). It sets that share of the first layer's input to 0 (random positions, seed `OPENEYE_SEED` + 4049). Without the variable nothing changes. |
| (c) | Sweep. Shapes: the 4 compute layers of the Table 2 network on their own (Conv 28×28×1 → 16, Conv 14×14×16 → 32, Conv 7×7×32 → 32, Dense 1568 → 32). Input zero shares 0 / 25 / 50 / 75 / 90 %. Configurations CR 1 X 2, CR 2 X 4, CR 8 X 4 (Y 3), both modes. That is 120 runs, all PASS. The 15 runs of the 7×7 layer pass on values, but the testbench reference file differs in padding slots (the same with the bias table off, an existing strictness of the testbench). Output: `sweep.md`, `sweep.png`. |
| (d) | Cost model check. The per-layer choice is predicted from the sweep (the compute ratio sparse / dense interpolated at the layer's input zero share, `load_wght` from the transfer sizes) and compared with the measured choice on MNIST and the Table 2 network with ReLU. Output: `model.md`. |

## Results

### 1. Phases: where the two modes differ

In every run only two phases differ between the modes. All the others are cycle-identical in every run: `load_config`, `load_iact`, `load_bias`, `load_quant`, `load_act`, `convert_iact`, `writeback`, `pooling`, `readout`.

- **`load_wght`** in dense HW is −33 % (DMA 32 bit, or 64-bit configurations with 3 rows) to −40 % (MNIST, CR 2 X 4). The cause is the transfer format (12-bit fields against 8-bit weights). In sparse HW its size does not depend on the weight zeros: every PE block has a fixed length.
- **`compute`** in sparse HW is lower in proportion to the input zeros (ReLU). It is about 1–3 % higher when the input has no zeros: the FSM overhead, partly offset by skipping zero weights.

Whole network, sum over the layers (cycles):

| Run | `load_wght` sparse → dense | `compute` sparse → dense | Other phases | Total sparse / dense / P1 |
|---|---|---|---:|---|
| MNIST ReLU | 38,880 → 23,328 (−40 %) | 125,647 → 147,856 (**+17.7 %**) | 31,711 | 196,238 / 202,895 / **180,686** |
| MNIST Leaky ReLU | 38,880 → 23,328 | 144,772 → 147,856 (+2.1 %) | 31,711 | 215,363 / 202,895 / 199,811 |
| MNIST SiLU | 38,880 → 23,328 | 146,857 → 147,856 (+0.7 %) | 31,775 | 217,512 / 202,959 / 201,960 |
| MNIST hard-swish | 38,880 → 23,328 | 146,914 → 147,856 (+0.6 %) | 31,775 | 217,569 / 202,959 / 202,017 |
| Table 2, CR 1 X 2, ReLU | 19,764 → 13,176 (−33 %) | 146,172 → 159,489 (+9.1 %) | 23,583 | 189,519 / 196,248 / 182,931 |
| Table 2, CR 2 X 4, ReLU | 18,450 → 11,070 (−40 %) | 39,095 → 42,667 (+9.1 %) | 16,632 | 74,177 / 70,369 / 66,797 |
| Table 2, CR 8 X 4, ReLU | 17,604 → 11,736 (−33 %) | 15,975 → 16,440 (+2.9 %) | 16,620 | 50,199 / 44,796 / 44,331 |
| Table 2, CR 2 X 4, no activation | 18,450 → 11,070 | 42,573 → 42,667 (+0.2 %) | 16,632 | 77,655 / 70,369 / 70,275 |
| Table 2, CR 8 X 4, no activation | 17,604 → 11,736 | 16,754 → 16,440 (**−1.9 %**) | 16,620 | 50,978 / 44,796 / 45,110 |

Pros and cons against today's sparse HW:
- **Dense HW** wins `load_wght` everywhere, and loses `compute` in proportion to the zeros. It is better wherever `load_wght` weighs more than the zero gain. That covers every network without zeros, and with ReLU every configuration of CR 2 and up, where compute is short and the weight transfer is a large share.
- **P1** keeps the sparse `compute` and takes the dense `load_wght`, so it gets both advantages. P1 is never slower than sparse HW: in the estimate it is −2.8 to −13.5 % on every run. It is slower than dense HW only where the sparse FSM's compute overhead stays: no zeros at CR 4 / CR 8, +0.1 to +0.7 %.

### 2. Per layer

Full per-layer and per-phase tables: `networks.md`. The cycles each option saves against today's sparse HW, as a share of the network:

| Layer (class) | Input zeros | P1 saves | Better FSM per layer (P2) saves on its own | P2 on top of P1 |
|---|---|---|---|---|
| Conv 1 (1 input channel, the image) | 0 % | 24–96 cycles (≤ 0.1 %) | 149–505 (0.2–0.3 %): dense FSM | **77–481 (0.1–0.3 %)**: P2's only clear gain |
| Conv 2 (14×14, 16 / 32 channels) | 5–44 % | MNIST 6,144 (3.1 %); Table 2 768–1,536 (0.4–2.3 %) | 0–6,078 (0–2.8 %) | 0–102 (≤ 0.2 %) |
| Conv 3 (7×7, 32 / 64 channels) | 7–87 % | MNIST 6,144 (2.8–3.1 %); Table 2 1,152–1,536 (0.8–2.3 %) | 0–5,086 (0–2.5 %) | 0–124 (≤ 0.2 %) |
| Dense 1568 / 3136 → N | 7–85 % | **3,168–4,224 (1.5–6.9 %)** | 1,130–4,284 (0.6–6.8 %) | 0–117 (≤ 0.1 %) |
| Dense 32 → 10 | 6–69 % | 36 (≤ 0.1 %) | 32–36 | 0 |

- **Conv 1** is the only layer where the FSM choice still matters after P1. Its input (the image) has no zeros, so the sparse FSM is 1.1–2.2 % slower on this layer. The layer is bound by `writeback` and `convert_iact`, so the whole gain is at most 0.3 % of the network.
- **Conv 2 / Conv 3**: what P1 saves (6,144 cycles each in MNIST) is the same as what dense HW saves on the transfer, but without losing the zero gain in `compute`.
- **The large Dense layer** gains most from P1 in relative terms. Without P1 it is always faster on dense HW (weights are most of the work), even at 85 % zeros. With P1 it is −3.8 to −16.9 % against dense HW with ReLU. MNIST: 13,107 (sparse) / 10,733 (dense) / **9,939 (P1)**.

### 3. Sweep: the crossover zero share

Below this share of input zeros, dense HW is faster on the whole layer (`sweep.md`, `sweep.png`):

| Layer | Config | Today: sparse = dense | With P1: P1 = dense |
|---|---|---:|---:|
| Conv 28×28×1 → 16 | CR 1 X 2 / CR 2 X 4 / CR 8 X 4 | 42 % / 60 % / dense always | 41 % / 57 % / 76 % |
| Conv 14×14×16 → 32 | CR 1 X 2 / CR 2 X 4 / CR 8 X 4 | 4 % / 36 % / 73 % | **0 % / 1 % / 18 %** |
| Conv 7×7×32 → 32 | CR 1 X 2 / CR 2 X 4 / CR 8 X 4 | 6 % / 48 % / dense always | **P1 always / P1 always / 29 %** |
| Dense 1568 → 32 | CR 1 X 2 / CR 2 X 4 / CR 8 X 4 | dense always | **8 % / 12 % / 9 %** |

- The threshold the proposal of 2026-11-17 asked for ("at what density does sparse really win") **depends on the cluster configuration more than on the layer**. With more clusters, compute is shorter and the weight transfer weighs more. With P1 the threshold of most layers drops to 0–30 %. Only the first layer (1 channel) keeps a high threshold, because its sparse compute gains little from zeros: a single input channel means few weights per iact.
- The sparse compute is close to linear in the non-zero share for Conv 2 / Conv 3 / Dense (R² 0.95–0.99), but not for Conv 1 (0.74–0.90: almost flat up to 50 %, then falling).

### 4. Cost model check (step 1d)

Prediction from the sweep only (shape class, cluster configuration, the layer's measured input zero share). Checked on 28 compute layers: MNIST in 4 activations at CR 2 X 4, which has more filters and channels than the swept shapes, and the Table 2 network with ReLU at CR 1 X 2, CR 2 X 4 and CR 8 X 4.

- **Choice between today's two modes: 28 of 28 right.** Predicted sparse − dense within 0.1–3.5 points of the measured value (the largest error is Conv 3 at 87 % zeros, beyond the densest steps of the sweep).
- **Choice of FSM with P1: 26 of 28 right.** The 2 wrong ones are MNIST Leaky ReLU / hard-swish Dense at +0.3 / +0.8 % measured against −0.5 / −0.1 % predicted, together 110 cycles.

A Python cost model is therefore enough to choose per layer (step 5). The input must be the zero share per layer, measured on calibration images.

### 5. Resources: is it worth it

| Option | Area (ZU7EV, post-route LUT) | Cycles against today's sparse HW | Cycles × LUT (area-normalised) | Worth it? |
|---|---|---|---|---|
| Today's sparse HW | 60,113 LUT, 188 BRAM, 12 URAM (Vivado 2026-11-18) | 0 | 0 | baseline |
| Dense HW | about 43,960 LUT (−26.9 %; measured 43,523 on 2026-11-10 plus the bias table +434), −4 BRAM, −2 URAM | ReLU (17 runs): −12.0 to +3.7 % (slower at CR 1 and on MNIST); others (19 runs): −13.4 to −2.4 % | **−24.2 to −36.7 %** | Best per area on every run |
| **P1** | **+281 LUT, +0 FF** (Yosys, `p1_wght_row.v`, once at the top level), about +0.5 % | **−2.8 to −13.5 %** (MNIST ReLU −7.9 %) | −2.3 to −13.1 % | **Yes**: the best option at today's area |
| P2 | +8–16 % LUT (estimate, two FSMs in every PE), about +4,800–9,600 | 0 to −1.7 % against the better mode | −6.5 to +7.1 % at +8 % LUT, always worse than P1 | No (below the 3 % gate of step 1) |
| P1 + P2 | P1 + P2 | 0.1–0.4 % more than P1 | worse than P1 | No |

Ranges are over all 36 runs (`networks.md`, last table: MNIST in 4 activations, the Table 2 network in 16 configurations with and without ReLU). The LUT counts used are sparse 60,113, dense 43,957, P1 60,394 and P2 64,922 (+8 %). Figure `options.png` shows both measures for 10 of the runs.

- **P1 pays off**: about 0.5 % LUT for −3 to −13 % cycles on every measured run. That is 6–29 times the cost in percent.
- **P2 does not pay off**: after P1 it saves at most 0.4 % (Conv 1), for 8–16 % LUT. Its alternative is cheaper: lower the sparse FSM's overhead on inputs without zeros (step 4 of the plan, second option).
- **Dense HW stays the best per area**: −24 to −37 % cycles × LUT. Against P1 it is:
  - **slower with ReLU** (MNIST +12.3 %, Table 2 +0.7 to +7.3 %);
  - about equal with few zeros (−0.7 to +1.5 %: the Table 2 network without activation, and MNIST with Leaky ReLU / SiLU / hard-swish).

  Which to build depends on the binding constraint:
  - **ZU7EV**: the design uses 26 % of the LUTs but 60 % of the BRAM (188 / 312). The LUTs saved by dense HW cannot buy more PEs: more PEs need more GLB BRAM. Latency on ReLU networks favours sparse HW + P1.
  - **An FPGA where LUTs are the limit**, for example a small Zynq-7000: this configuration needs 184–188 BRAM tiles, so it would have to shrink first. There the −27 % LUT of dense HW is what counts.

### 6. Limits of the P1 estimate

1. **Zero weights.** In the raw format every weight gets a field, zeros included, and the sparse FSM then multiplies them. Today it skips them. Upper bound, if compute grows in proportion to the weight zeros:
   - **Trained MNIST**: int8 per-layer scale, 0.3–2.9 % zeros (Conv 1 0.3–0.7 %, Conv 2/3 1.5–2.0 %, Dense 1.4–2.9 %). P1 goes from −7.9 % to about **−6.9 %** for ReLU and from −7.1/−7.2 % to −6.0/−6.1 % for the others.
   - **Table 2 network**: random weights, 1–5 % zeros. At 5 %, P1 against sparse HW is −1.9 to −10.1 % instead of −3.3 to −11.7 %. Against dense HW: −1 to −5.4 % with ReLU (CR 8 X 4: +0.8 %), and +1 to +2.8 % without zeros.

   A per-layer rule handles this: use raw only if the `load_wght` saving exceeds compute × the weight zero share. Step 2 measures the real effect.
2. **No extra cycles in `GET_WGHT`.** The row is written when the third DMA word instead of the fifth arrives. The estimate assumes the 8 → 12 bit expansion fits in that cycle, as in `p1_wght_row.v`.
3. **All-zero weight words.** Outside raw mode, `data_pipeline_wght.v` takes an all-zero word as "no data" (#47). P1 must therefore send `raw_wght_i` for such layers, and the sparse PE must accept a dense layout with zero pairs. This is the purpose of step 2 (a Python experiment on today's RTL).

**Step 2 measured limits 1 and 3** (`doc/experiments/2026-11-18_wght_layout_step2.md`):
- **Limit 3:** the sparse PE computes the dense layout bit-exactly once `raw_wght_i` is set. It was forced in simulation, with no PE change. Without raw mode, an all-zero word hangs the layer.
- **Limit 1:** the proportional bound is far too pessimistic:
  - 0–26 cycles for a whole trained MNIST network, and at most 0.2 % on the Table 2 network;
  - in single layers, ≤ 0.5 % compute at 5 % zero weights and ≤ 22.5 % at 50 %.
- The measured P1 equals the estimate of section 4 within 0.2 points.

### 7. Verdict

- **Step 1 gate** ("stop if choosing right per layer gains < about 3 % on the target networks"):
  - P2 (FSM per layer): 0–1.7 %, at most 0.4 % after P1. **Stop.**
  - P1 (weight format per layer): −2.8 to −13.5 % (−1.9 to −10.1 % at the upper bound of limit 1). **Go on**, to step 2 (Python experiment, no RTL change), then step 3 (RTL, needs your approval).
- **Per layer**: P1's gain comes from Conv 2 / Conv 3 (weight-heavy, 1.5–6k cycles each) and the large Dense layer (3–4k, the largest share at large CR). The FSM choice matters only for the first layer, by 0.1–0.3 % of the network.
- **Unless LUTs are the limit, P1 is the next step**. Where LUTs are the limit, dense HW without the sparse logic is the right build: −27 % LUT, and with this datapath it is no slower than sparse HW except on ReLU networks at small CR.

## Files

- `2026-11-18_layer_mode_study/`
  - `step01.sh`: driver
  - `test_sweep.py`, `run_sweep.py`: sweep
  - `analyse_study.py`: `networks`, `sweep`, `model`
  - `plot_sweep.py`, `plot_options.py`
  - `p1_wght_row.v`: area estimate, not part of the RTL
  - outputs `networks.md`, `sweep.md`, `model.md`, `sweep.png`, `options.png`
- Profiles:
  - `doc/perf/baseline_2026-11-18`, `paper_table3_2026-11-18{,_dense,_relu_sparse}`
  - `activation_2026-11-18`
  - `layer_sweep_2026-11-18_{sparse,dense}`
- Hardware baseline: `doc/synth/2026-11-18_route4ns_default_zu7ev`.

To regenerate (from the repository root):

```bash
D=doc/experiments/2026-11-18_layer_mode_study
venv/bin/python $D/analyse_study.py networks --mnist doc/perf/activation_2026-11-18 --t3 doc/perf/paper_table3_2026-11-18 doc/perf/paper_table3_2026-11-18_dense doc/perf/paper_table3_2026-11-18_relu_sparse --lut 60113 43957 60394 64922 > $D/networks.md
venv/bin/python $D/analyse_study.py sweep doc/perf/layer_sweep_2026-11-18_sparse doc/perf/layer_sweep_2026-11-18_dense --t3relu doc/perf/paper_table3_2026-11-18_relu_sparse > $D/sweep.md
venv/bin/python $D/analyse_study.py model doc/perf/layer_sweep_2026-11-18_sparse doc/perf/layer_sweep_2026-11-18_dense --mnist doc/perf/activation_2026-11-18 --t3relu doc/perf/paper_table3_2026-11-18_relu_sparse --t3dense doc/perf/paper_table3_2026-11-18_dense > $D/model.md
venv/bin/python $D/plot_sweep.py doc/perf/layer_sweep_2026-11-18_sparse doc/perf/layer_sweep_2026-11-18_dense $D/sweep.png
venv/bin/python $D/plot_options.py doc/perf/activation_2026-11-18 doc/perf/paper_table3_2026-11-18 doc/perf/paper_table3_2026-11-18_dense doc/perf/paper_table3_2026-11-18_relu_sparse $D/options.png 60113 43957 60394 64922
```

Re-running the measurements: `bash doc/experiments/2026-11-18_layer_mode_study/step01.sh <output directory>` (about 5.5 hours, sequential).
