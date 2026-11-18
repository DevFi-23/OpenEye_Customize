# 2026-11-18: step 2 of the per-layer weight format P1: the sparse PE with the dense weight layout, on today's RTL

Step 2 of the plan in README_FI section 2 ("sparse theo layer"). The plan and steps 0–1 are in
`doc/experiments/2026-11-18_layer_mode_study.md`. **No RTL change.** Files are in `2026-11-18_wght_layout_step2/`.

P1 keeps the sparse FSM and chooses the weight format per layer. One option is today's zero-compressed columns (CSC, 12-bit fields). The other is raw 8-bit words, which `GET_WGHT` expands to 12-bit fields with overhead 0 (the **dense layout**). Step 1 estimated P1 from the measured profiles but left three limits open. Step 2 measures them:

1. In the dense layout, zero weights are multiplied, while CSC skips them. Step 1 used a proportional upper bound, which predicted a loss of up to 1–1.6 points.
2. All-zero words. Outside raw mode, `data_pipeline_wght.v` drops an all-zero 24-bit word (#47), and two zero weights in one word make such a word. Does the sparse PE accept the dense layout when `raw_wght_i` is set?
3. Is the result bit-exact?

## 1. Method

The RTL is unchanged. Only Python hooks are added, and all of them are off when unset:

| Hook | Where | What |
|---|---|---|
| `OPENEYE_WGHT_LAYOUT=dense` | `wght_stream_mapper.py`, `conv_wght_encoding.encode_dense` | Conv weights on sparse hardware go in the dense layout: every weight is an entry `(w, 0)`, zero weights included, and each column is padded to a word boundary. The block length is the same as with CSC. If a PE block would contain an all-zero word and raw mode is not forced, the mapper refuses it. `dense_nocheck` sends the block anyway (negative control). |
| `OPENEYE_FORCE_RAW_WGHT=1` | `test/cocotb_fpga/OpenEye_FPGA_tb.py` | Simulation only (cocotb `Force`, Icarus): holds the `raw_wght_i` input of `OpenEye_Parallel` (today `FC \| GEMM`) at 1 for every layer. P1 would set this bit for a layer sent in the dense layout. The input reaches only `data_pipeline_wght.raw_mode_i`, through the PE configuration stream. |
| `OPENEYE_WGHT_ZERO_FRACTION=<f>` | `DRAM.py` | In every Conv2D layer, exactly round(f × N) weights are zero, at seeded positions; any other zero weight becomes ±1. |
| `OPENEYE_WGHT_ZERO_PARITY=1` | `DRAM.py` | Zeros are placed only where c + f + y + x is even, so two neighbouring filters are never both zero. The dense layout then has no all-zero word. |
| profile `info.weights` | `rtl_test_utils.profile_set_layer_weights` | Weight count, zero weights and layout of each layer, written into `profile.json`. |

The Python cycle model of `data_pipeline_wght.v` (`wght_pipeline_model.load`) gained `raw_mode`. Unit tests in `test/test_conv_wght_encoding.py` cover:
- the dense layout reads back exactly in raw mode, for 2–16 filters per column and 0–100 % zero weights;
- outside raw mode it reads back only when there is no all-zero word;
- raw mode does not change what the CSC layout reads;
- every PE block of the mapper reads back in raw mode, and the mapper refuses a block with all-zero words when raw mode is not forced.

The suite now has 116 tests (+74).

The runs are all on sparse hardware with the default build, and `step2.sh` runs them one part after the other:

| Part | What | Result |
|---|---|---|
| Single layers (`test_step2.py`) | The three Conv shapes of the Table 2 network × CR 1 X 2 / CR 2 X 4 / CR 8 X 4 × input zeros 0 / 50 % × weight zeros 0 / 5 / 25 / 50 % × layout CSC / dense (raw forced), plus 5 controls | 139 / 140 PASS. The FAIL is the negative control. |
| Table 2 network, without activation and with ReLU, 16 configurations each | Dense layout, raw forced | 32 / 32 PASS (bit-exact) |
| Trained MNIST (image 0), ReLU / Leaky ReLU / SiLU / hard-swish | Dense layout, raw forced | 4 / 4 PASS (bit-exact, class 7) |
| 12 baseline cases, hooks off | Against `baseline_2026-11-18` | see section 6 |

Profiles are in `doc/perf/wght_layout_2026-11-18` (single layers), `paper_table3_2026-11-18_wlayout` (Table 2, no activation), `paper_table3_2026-11-18_relu_wlayout` (Table 2, ReLU) and `wght_layout_2026-11-18_mnist`. Tables are in `single.md` and `networks.md`; the chart is `zero_weight_cost.png`.

## 2. Bit-exactness and controls

Control runs (conv2 14×14×16 → 32, CR 2 X 4, 50 % input zeros, 25 % weight zeros; cycles):

| Run | Result | total | load_wght | compute |
|---|---|---:|---:|---:|
| CSC (today) | PASS | 28,776 | 3,840 | 18,529 |
| CSC, raw forced | PASS | 28,776 | 3,840 | 18,529 |
| Dense layout, raw forced | PASS | 30,000 | 3,840 | 19,753 |
| CSC, zeros never on neighbouring filters | PASS | 28,759 | 3,840 | 18,512 |
| Dense layout of those weights, **no force** (today's RTL as it is) | PASS | 30,000 | 3,840 | 19,753 |
| The same, raw forced | PASS | 30,000 | 3,840 | 19,753 |
| Dense layout with all-zero words, no force | **FAIL**: hang (no FSM progress for 400,000 cycles) | | | |

- **The sparse PE computes the dense layout bit-exactly** when raw mode keeps the all-zero words:
  - 63 / 63 single-layer runs, 32 / 32 Table 2 networks, 4 / 4 trained MNIST models;
  - weight zeros 0.3–50 %, including pairs of zero weights.
  - With no zero weight, the two layouts are the same stream: equal cycles in 9 / 9 runs.
- **Raw mode changes nothing for today's CSC stream.** The cycles are equal in every phase, because the CSC encoding puts no all-zero word in a block.
- **Without raw mode, an all-zero word hangs the layer.** P1 must therefore set `raw_wght_i` for every layer sent in the dense layout, as the step 3 plan says (`raw_wght_i = FC | GEMM | wght_raw`). With no all-zero word, today's RTL already computes the dense layout correctly.
- **The PE needs no change.** The only RTL work left for P1 is `GET_WGHT` (3 DMA words per row instead of 5, expanded from 8 to 12 bits) and the `wght_raw` bit.
- **`load_wght` is equal in both layouts in every run.** The transfer size is fixed per PE block, so step 2 measures the compute effect only. The transfer saving comes from the dense hardware profiles, as in step 1.

## 3. Compute cost of zero weights

The table shows the `compute` increase of the dense layout over CSC, on the same data. In parentheses is its share of the proportional bound of step 1 (compute × weight zero share). Input without zeros:

| Layer | Config | filters per column | 5 % zero weights | 25 % | 50 % |
|---|---|---:|---:|---:|---:|
| Conv 28×28×1 → 16 | CR 1 X 2 / CR 2 X 4 | 16 | +0.0 % (0 %) | +4.2 / +4.7 % (17–19 %) | +11.2 / +12.6 % (22–25 %) |
| | CR 8 X 4 | 8 | +0.0 % | +1.4 % (6 %) | +4.4 % (9 %) |
| Conv 14×14×16 → 32 | CR 1 X 2 / CR 2 X 4 | 16 | +0.4 % (8 %) | +8.4 % (34 %) | +22.2 / +22.3 % (44–45 %) |
| | CR 8 X 4 | 8 | −0.0 % | +2.7 % (11 %) | +9.5 % (19 %) |
| Conv 7×7×32 → 32 | CR 1 X 2 / CR 2 X 4 | 16 | +0.3 / +0.5 % (7–10 %) | +7.0 / +8.3 % (28–33 %) | +20.2 / +22.5 % (40–45 %) |
| | CR 8 X 4 | 4 | −0.5 % | −0.8 % | −0.8 % |

With 50 % input zeros the increase is a little lower: 16.6–17.2 % instead of 22 % at 50 % zero weights. Full table: `single.md`.

- **The cost is far below the proportional bound:**
  - 0–10 % of the bound at 5 % zero weights, which is the range of real trained and random networks;
  - 6–34 % of the bound at 25 %, and 9–45 % at 50 %.
- **The reason is that the PE reads two entries per word.** CSC saves compute only when the zeros of a column remove a whole word. With few zeros, the CSC rules mostly pad instead: the padding slot of an odd entry count, and explicit zero entries at the column end and for gaps. With short columns (4 filters per column, Conv 7×7×32 at CR 8 X 4), the dense layout is even slightly faster than CSC.
- **In the dense layout, compute does not depend on where the zeros are, or how many.** The dense run with parity zeros has exactly the same cycles as the dense run with random zeros. The P1 cycles of a layer are therefore fixed, and only today's CSC baseline moves with the weight zeros.

## 4. P1 with the measured cost

### Networks

**P1 measured** = dense-layout run − (load_wght sparse − load_wght dense hardware), per layer.

| Network | sparse today | dense HW | P1 step 1 estimate | **P1 measured** | P1 vs sparse | P1 vs dense HW |
|---|---:|---:|---:|---:|---:|---:|
| MNIST ReLU | 196,238 | 202,895 | 180,686 | **180,686** | −7.9 % | −10.9 % |
| MNIST Leaky ReLU | 215,363 | 202,895 | 199,811 | **199,837** | −7.2 % | −1.5 % |
| MNIST SiLU | 217,512 | 202,959 | 201,960 | **201,973** | −7.1 % | −0.5 % |
| MNIST hard-swish | 217,569 | 202,959 | 202,017 | **202,017** | −7.1 % | −0.5 % |
| Table 2 ReLU, 16 configurations | | | | | **−2.8 to −13.5 %** | −0.7 to −6.6 % |
| Table 2 without activation, 16 configurations | | | | | **−2.6 to −13.3 %** | −0.3 to +0.6 % |

Examples (cycles):

| Network | sparse today | P1 step 1 estimate | P1 measured |
|---|---:|---:|---:|
| Table 2 ReLU, CR 2 X 4 Y 3 | 74,177 | 66,797 | 66,862 |
| Table 2 ReLU, CR 8 X 4 Y 3 | 50,199 | 44,331 | 44,314 |

- **The step 1 estimate holds.** The measured P1 differs from it by at most 376 cycles (0.2 points). It is faster in 8 of the 36 runs (shorter CSC columns, section 3) and equal in 2.
  - The zero-weight cost of the trained MNIST models is 0–26 cycles in a whole network (0.3–2.0 % zero weights in the Conv layers). The worst case of step 1 (MNIST ReLU −6.9 %) does not happen: the measured value is −7.9 %.
  - The Dense layers already use the dense layout today (raw mode, `DenseWghtStreamMapper`), so P1 changes only their transfer.
- **P1 is faster than dense hardware on every network with ReLU**, by 0.7–10.9 %. Without ReLU, P1 equals dense hardware within ±0.6 % (Table 2) or is 0.5–1.5 % faster (MNIST Leaky ReLU, SiLU, hard-swish).
- **Per layer, the dense layout is worth it in every Conv and Dense layer of all 36 runs**: the `load_wght` saving is larger than the added compute. The per-layer rule therefore changes nothing on these networks (`networks.md`).

### Single layers: when CSC stays better

The rule: CSC is better when the added compute exceeds the `load_wght` saving. This is the break-even share of zero weights, from the measured points (linear between them):

| Layer | CR 1 X 2 | CR 2 X 4 | CR 8 X 4 |
|---|---:|---:|---:|
| Conv 28×28×1 → 16 (saving 24 / 48 / 72 cycles) | 5–6 % | 9 % | 46 % |
| Conv 14×14×16 → 32 (saving 768 / 1,536 / 1,152) | 6–7 % | 22–30 % | dense layout always better (> 50 %) |
| Conv 7×7×32 → 32 (saving 1,536 / 1,536 / 1,152) | 13–18 % | 43 % to > 50 % | dense layout always better |

Ranges are for 0 / 50 % input zeros.

- The first layer (1 input channel, a small weight load) and the small configurations (CR 1 X 2) keep CSC above about 5–18 % zero weights. Larger configurations prefer the dense layout up to 22–50 % or more.
- Real networks (0.3–5 % zero weights) are below every break-even point. Pruned networks (≥ 25 %) need the per-layer rule.
- The mapper knows both layouts of each PE block (the number of words per column), so the rule can be computed in Python at mapping time. A model of the added compute is needed: about the CSC words saved per column × the non-zero inputs that read the column. This belongs to step 3 (the Python choice) and step 5.

## 5. P1 against dense hardware, per layer (no zero weights matter here)

The P1 cycles of a layer do not depend on its zero weights. The comparison with dense hardware is the one of step 1:

| Layer | Input without zeros | Input 50 % zeros |
|---|---|---|
| Conv 28×28×1 → 16 | P1 slower by 0.7–1.9 % (sparse FSM overhead, 1 channel) | −0.9 % to +0.7 % |
| Conv 14×14×16 → 32 | +0.1 to +0.6 % | P1 faster by 3.6–14.3 % |
| Conv 7×7×32 → 32 | P1 faster by 1.4–1.8 % at CR 1 X 2 / CR 2 X 4, slower by 0.9 % at CR 8 X 4 | P1 faster by 2.0–13.8 % |

## 6. Default path unchanged

With every hook unset, the default path is unchanged:
- the mapper calls `encode_columns` as before;
- `DRAM.py` and the testbench change nothing;
- the profile only gains `info.weights`.

| Check | Result |
|---|---|
| Unit tests | 578 PASS (504 + 74 new) + the 11 known `test_dense_output.py` failures |
| 12 baseline cases, hooks off, against `baseline_2026-11-18` | 12 / 12 PASS, every case identical in total cycles and DMA words (0 change) |

## 7. Verdict

- **Step 2 passes.**
  - The sparse PE computes the dense layout bit-exactly, with no PE change, as long as `raw_wght_i` is set for the layer. Without it, all-zero words hang the layer.
  - The compute cost of zero weights is negligible for real weights: 0–26 cycles per MNIST network and at most 0.2 % on the Table 2 network.
  - P1 measured: −7.1 to −7.9 % on trained MNIST and −2.6 to −13.5 % on the Table 2 network, the same as the step 1 estimate.
- **Step 3 (needs your approval, RTL):**
  1. A `wght_raw` bit per layer in the regmap. `raw_wght_i = FC | GEMM | wght_raw`.
  2. `GET_WGHT` of `OpenEye_FPGA.v` collects 3 DMA words per buffer row instead of 5 when `wght_raw` is set, and expands each 8-bit weight into a 12-bit field with overhead 0. Yosys estimate: +281 LUT (`p1_wght_row.v`).
  3. Python chooses the format per layer and packs the dense layout into 8-bit words:
     - the dense layout by default;
     - CSC when the predicted added compute exceeds the `load_wght` saving (pruned weights, the first layer at small configurations);
     - CSC for an odd number of filters per PE.
  4. The PE and `data_pipeline_wght.v` need no change.
- **No step remains open before step 3.** The `GET_WGHT` timing (limit 2 of step 1, the row written at the 3rd word instead of the 5th) is measured only by step 3 itself, and `p1_wght_row.v` gives no reason to expect a problem.

## 8. Files and commands

| File | What |
|---|---|
| `test_step2.py` | The 140 single-layer cases (pytest, `test_conv_const` with the hooks) |
| `run_step2.py` | Runs the cases 6 at a time and saves profiles and status |
| `step2.sh` | All of step 2 (about 3 hours, 6 jobs) |
| `analyse_step2.py` | `single` and `networks` tables |
| `plot_step2.py` | `zero_weight_cost.png` |
| `single.md`, `networks.md` | The tables |

```bash
bash doc/experiments/2026-11-18_wght_layout_step2/step2.sh <out dir>
cd doc/experiments/2026-11-18_wght_layout_step2
../../../venv/bin/python analyse_step2.py single ../../perf/wght_layout_2026-11-18 ../../perf/layer_sweep_2026-11-18_dense > single.md
../../../venv/bin/python analyse_step2.py networks ../../perf/activation_2026-11-18 ../../perf/activation_2026-11-18 \
    ../../perf/wght_layout_2026-11-18_mnist ../../perf/paper_table3_2026-11-18 ../../perf/paper_table3_2026-11-18_dense \
    ../../perf/paper_table3_2026-11-18_wlayout ../../perf/paper_table3_2026-11-18_relu_sparse \
    ../../perf/paper_table3_2026-11-18_relu_wlayout > networks.md
../../../venv/bin/python plot_step2.py ../../perf/wght_layout_2026-11-18 zero_weight_cost.png
```
