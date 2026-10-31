# 2026-10-31: upstream review, commits not in `dev`

`git fetch upstream`: `upstream/main` = `93f0e82` (2026-10-29), nothing new since the check of 2026-10-30.
`git log upstream/main --no-merges ^dev` lists 22 commits; three of them were cherry-picked on 2026-10-21
(`b6fa369`, `2c8c324`, `2bf497d`, `git cherry-pick -x`), so **19 commits are not in `dev`**. Nothing was taken; this
note is the evidence for that decision. No RTL of `dev` was changed.

## 1. Method

* Upstream was checked out in a separate worktree (`git worktree add <wt> upstream/main`, removed afterwards) and run
  with its own RTL, testbench and Python (`PYTHONPATH=<wt>/src`).
* Each open bug of `dev` was reproduced on both trees with the same runner and the same random data:
  `2026-10-31_upstream_review/up_run.py <tree> <name> LAYER W H CH NF CR GLB_PSUM [layers] [KEY=VALUE...]` calls the
  tree's own `test_conv_const._run_conv_const` (no constant operands, `OPENEYE_SEED=1`, `OPENEYE_KEEP_GOING=1`,
  2 cluster columns, `NUM_GLB_IACT` 1). Bug #23 used the tree's own `test_conv3x3_sparse.py` case.
* Field widths (what `655a2ae` widens): `field_overflow.py` (Dense) and `field_overflow_conv.py` (conv, pooling) wrap
  `generator.pack_registers` of the mappers and report every status-register value that does not fit its regmap width.

## 2. Open bugs of `dev`, reproduced on both trees

| Bug | Case (`up_run.py` arguments) | upstream `93f0e82` | `dev` |
|---|---|---|---|
| #23 | `test_conv3x3_sparse.py::test_conv3x3_8ch_sparse50[3-4-3-2-1-8-4-32-3-3-1-16]` | FAIL | FAIL |
| #27 | `b27 Conv_Pool_Conv_Pool_Conv 8 8 4 4 2 4 5` | FAIL earlier: `Error found in Iact storage; word: 0` | FAIL: 4 of 4 maps differ |
| #28 | `b28 Convolution_Single 14 14 32 32 1 2 1` | FAIL, 32 of 32 maps differ | FAIL, 32 of 32 maps differ |
| #7 (3 channels) | `b7 Convolution_Single 8 4 3 4 2 4 1` | FAIL, 4 of 4 | FAIL, 4 of 4 |
| #9 | `b9 Convolution_Single 7 7 4 4 2 4 1` | values ok, reference file differs | values ok, reference file differs |
| #21 | `d21 FC 64 1 1 4 2 4 1 OUTPUT_SIZE=40` | FAIL, 30 of 40 | FAIL, 30 of 40 |
| #19b | `d19b FC 1568 1 1 4 1 4 1 OUTPUT_SIZE=32` (CR 1) | FAIL, 32 of 32 | FAIL, 32 of 32 |
| #29 | `d29 FC 3136 1 1 4 2 4 1 OUTPUT_SIZE=32` (one layer) | FAIL, 32 of 32 | FAIL, 32 of 32 |
| control | `c16 FC 3136 1 1 4 2 4 1 OUTPUT_SIZE=16` | **FAIL, 16 of 16** | PASS |
| control | `c10 FC 3136 1 1 4 2 4 1 OUTPUT_SIZE=10` | **FAIL, 10 of 10** | PASS (known: `test_dense_chain`, trained model) |

No upstream commit fixes an open bug of `dev`. New fact for #29: Dense 3136 -> 32 fails as a single layer too, not only
inside a chain. Upstream additionally fails the Dense 3136 -> 10 / 16 that `dev` runs (the Dense of the trained MNIST
model); the cause in upstream was not isolated.

Field widths: no status field overflows for Dense 3136 -> 10/16/32/64, 2560/2048/1568 -> 32, 1024 -> 64,
512/508 -> 32, 64 -> 40 (CR 1 and 2), the MNIST_REAL models, nor conv 56x56x64 -> 64, 112x112x32 -> 128,
28x28x256 -> 256. The widening of `655a2ae` therefore cannot be the cause of #19b, #21 or #29.

## 3. The commits

| Commit (date) | Content | Relation to `dev` | Take? |
|---|---|---|---|
| `fc9ace3` (12/10) | `test/cocotb_fpga/Makefile` restructured | Our runners (`run_profile`, pytest) do not use it | No |
| `18772d6` (15/10) | `rtl_test_utils.check_fc_activation_writes`: comments out the "extra FC write" assert and turns the bank/address and bubble checks into a string (so they no longer run) | Same symptom as our #5 (false alarm, temporary zeros with `NUM_GLB_IACT` > 1); `dev` keeps the check and skips it with `OPENEYE_SKIP_FC_WRITE_CHECK=1` | No |
| `240bc35`, `28415e5` (16/10) | `test_nets.py` / `test_conv_const.py` values (CR 8 -> 4, 2 and 3 channel input mapping) | Test values only; 3 channels fails on both trees (#7) | No |
| `81173dc` (20/10) | `hdl/config/regmap.yaml` synced | Copy not read by the toolchain (it uses `test/cocotb_fpga/regmap.yaml`, which in `dev` has more fields, e.g. `quant_clamp_low`) | No |
| `c48899f` (21/10) | `psum_pipeline.v`: every `results_ready` assignment becomes blocking `=` | Upstream's fix of #14, opposite to the fix of `dev` (3717d12: combinational part split out, only `<=`). Conflicts and loses the Yosys/Verilator netlist benefit | No |
| `e78e5b7` (21/10) | `OpenEye_FPGA.v`: removes `temp_var = 0;` outside the `if (!rst_n)` of an async-reset block | No functional change, only a cleaner reset template | Optional (RTL, needs approval) |
| `3ba44e3` (23/10) | Removes an obsolete check from the doc parser test | Nothing for us | No |
| `2dde2db` (26/10) | Unit testbenches: removed ports (`fc_size_i`) and parameters (`TRANS_BITWIDTH_WGHT` in `hdl/debug/PE_IO_debug.v`) | Testbenches we do not run | No |
| `551cf85` (27/10) | `iact_stream_constructor.v` back to the version before `23be043` plus a separate FC path ("fixes 3x3 conv regression") | The regression is our #6 / #7 (`NUM_GLB_IACT=3`), fixed in `dev` on 2026-10-14 with a small change; this replaces 249 lines of tested RTL. Upstream fails Dense 3136 -> 10/16 where `dev` passes | No |
| `c342d04` (27/10) | DAG: `DRAMContents`, references and testbench keyed by layer name (`Residual_Block`) | Rewrites `DRAM.py`, `test_utils_main.py`, the testbench: large conflicts with our DRAM model, profiler hooks and quantization path | Not now (idea for residual nets) |
| `3258813` (27/10) | Weight tiling: removes the duplicated `used_wght_per_PE` key in `conv_mapper.py`; keeps zero weight words when there are several weight transmissions; `OpenEye_FPGA.v` weight send ends at `wghts_per_pe + 1` instead of `+ 2` | First part = our #18 (2026-10-15); second part is a subset of our #22 (`dev` never skips zero words in conv, `ConvWghtStreamMapper.SKIP_ZERO_WORDS = False`); the RTL line is not needed by any bug of ours (`dev` passes with `+ 2`) | No (the `+ 1` could save one clock per weight send: possible latency experiment, RTL, needs approval and full regression) |
| `80d6e67`, `c2bf7a9`, `93f0e82` (27-29/10) | Verilator flow; `make_stream` in a process pool, then sequential again because the pool dropped `layer_params` updates; layer buffer stream computation | `dev` `make_stream` is sequential and has the `trans_cycles` fix | No |
| `d1da389` (28/10) | `router_iact.v`: removes the route e12 (port 1 -> port 2), adds priority terms, to break a Verilator combinational loop | Changes routing; `dev` has no Verilator simulation flow, Icarus and Vivado are fine | No |
| `655a2ae` (28/10) | Wider fields and counters for bigger nets (`iact_read/write_limit_*` 18 bit, psum loops 12/24 bit) in `OpenEye_FPGA.v`, `OpenEye_Parallel.v`, `psum_pipeline.v`, `iact_stream_constructor.v`, regmap; CC != 2 links | Fixes none of our bugs (section 2: no field overflow in our models) | Reference for bigger nets |
| `57781cd` (28/10) | Testbench: Flatten in the DAG topology | Only for the DAG | No |

## 4. Decision

Take none of the 19 commits now. They fix nothing that is still open in `dev`; the bugs they fix (#6/#7, #14, #18, #22,
the FC write check) are already fixed in `dev`, in a way that is tested by our regression; and the whole upstream tree
fails the Dense 3136 -> 10/16 that the trained MNIST model needs. Worth keeping in mind: `655a2ae` (when a layer
outgrows a field), `c342d04` (residual nets), the `+ 1` weight-send end of `3258813` (one clock per weight send,
latency experiment, RTL approval needed).

## 5. Follow-up on the same day (user decisions)

* `e78e5b7` **taken** (approved): `git cherry-pick -x e78e5b7` = `5595d15` (original author kept). Verification: RTL
  regression 162 tests 157 PASS + 5 known xfail, 0 FAIL (identical to before); `test_quantization_unit` 2/2; Python
  unit tests 290 pass, 11 old fails; 12 baseline cases 0 cycles and 0 DMA words of change; Table 3 of the paper
  13/16, 0 cycles of change in all 16 configurations; lint `fpga` 462 -> 461 (the `BLKSEQ` of this line), baseline
  lowered; Vivado: see README_FI section 6d (`doc/synth/2026-10-31_route4ns_e78_zu7ev/`).
* `551cf85` compared in detail with the module of `dev`: `2026-10-31_upstream_551cf85_iact.md`. It is a byte-for-byte
  revert to `f84f064`, brings bug #13 back, fails a Conv with 8 channels and three banks, is not faster. Not taken.
* The `wghts_per_pe + 1` line of `3258813` tested as an experiment (approved): `2026-10-31_wght_send_end.md`. Correct
  everywhere, -0.1 % to -0.3 % cycles. Not in `dev` until the user decides.
* `up_run.py` got the option `GLBI=<n>` (`NUM_GLB_IACT` of the platform) for these comparisons.
