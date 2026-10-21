# 2026-10-21: three upstream commits cherry-picked into `dev`

Approved by the user after the comparison of 2026-10-19 (README_FI section 2). `dev` was at `3717d12` (bug #14 fix).

| Commit in `dev` | Upstream | Author | Change |
|---|---|---|---|
| `0cacda1` | `b6fa369` | DenLeb | `OpenEye_FPGA.v`: comment of `TRANS_WORDS` ("words per transmission from layer to layer") |
| `22614d2` | `2c8c324` | DenLeb | `OpenEye_Parallel.v`: the 4 generate blocks of the **psum** router were labelled `gen_router_iact_*`, now `gen_router_psum_*` |
| `9c0c8dc` | `2bf497d` | DenLeb | `PE.v`: `first_spad_words_wght` 5 -> `$clog2(WGHT_ADDR_ADDR+1)` bits, `filters_reg_M0` 6 -> `$clog2(WGHT_ADDR_ADDR+1)+1` bits, the widths of the `data_pipeline_wght` ports they connect to |
| next commit | - | (own) | `PE.v`: explicit zero extension of `filters_reg_M0` (generate-if, also valid for `WGHT_ADDR_ADDR=16` where the field is exactly 6 bits); lint baseline |

Cherry-picked with `git cherry-pick -x` (no conflict): the original author is kept and each message records the upstream hash,
so a later `git merge upstream/main` recognises them. Not taken: `fc9ace3` (Makefile defaults, not used by the pytest flow),
`18772d6` (disables the live FC write check with a string literal, also the value comparison), `81173dc` (2026-10-20, new:
`hdl/config/regmap.yaml` made identical to `test/cocotb_fpga/regmap.yaml`; no code reads the `hdl/config` copy).

## What the PE change fixes

`data_pipeline_wght` counts the words of the weight address SPad in a `$clog2(FIRST_SPAD_ADDR+1)` = 7-bit register
(`FIRST_SPAD_ADDR = WGHT_ADDR_ADDR = 64`). `PE.v` received it in a 5-bit wire, so a count of 32 or more would wrap
(`(first_spad_words_wght - 1) > wght_addr_vec` in the sparse FSM, 4 places). The other port, `first_spad_max_i`, is 8 bits and
got the 6-bit `filters_reg_M0`. Bug #11 (first part, `PE.v:2210`, Vivado Synth 8-689).

Is the wrap reachable today? Measured with `probe_spad.py` (largest `first_spad_words_o` over all PEs): Conv layers of all sizes tried (4-64 channels, 4-64 filters) stay at **13** or less (3-wide kernel x at most 4 channels per PE + 1); 8 sampled GEMM/Dense tests reach 3 to **25**. **Dense K = 512 (10 outputs) reaches 64** (the whole 64-word address SPad), with 3,564 samples >= 32, so the old 5-bit wire did truncate. Yet the old PE passes K = 512 too, and the PE lock-step (old PE as shadow) on that layer gives **0 mismatches in 161,088 PE-cycles** (48 PEs): in every case tried the truncated comparisons give the same decisions. So the fix is defensive (correct widths, clean lint and Vivado), it does not change any result seen so far.

Side result for bug #19 (Dense K > 512 wrong, found 2026-10-19): K = 520 fails 10/10 outputs with the old **and** the new PE, so the width fix is not its cause. Lead for later: at K = 512 the address SPad is exactly full (64 words), K = 520 needs more.

## Verification

| Check | Result |
|---|---|
| Lint, Verilator 5.020 (`tools/lint_check.py`) | fpga 470 -> 468, parallel 38 -> 36: the two `WIDTHEXPAND` port warnings of `PE.v` gone, **0 new**. Upstream's version alone adds one new warning (`assign filters_reg_M0 = stream_data[5:0]`, 6 -> 8 bit); the explicit zero extension avoids it. Baselines lowered |
| Elaboration of `PE` alone with `WGHT_ADDR_ADDR` = 8, 16, 64 (both generate branches) | Icarus and Verilator: 0 errors |
| `2c8c324` (rename only): Yosys `proc; flatten; opt_clean -purge` of `OpenEye_Parallel` (48 PEs) before / after | **byte-identical netlists** (198,236 cells, 47 MB): the labels name generate scopes that declare no signal |
| **PE lock-step in the system**: every PE carries the old PE (`3717d12`) as a shadow, same inputs, 8 outputs compared with `!==` at every falling clock edge, `$fatal` on the first difference; all 125 tests of `test_conv_const.py` (34), `test_gemm_layer.py` (63), `test_mnist_layers.py` (19), `test_profile.py` (9) | **5,708 PE instances (arrays of 8 to 128 PEs), all OK, 0 mismatches, 36,363,008 PE-cycles compared** |
| Same, the 23 GEMM/Dense tests again with `OPENEYE_SKIP_FC_WRITE_CHECK=1` (run to the end) | 23/23 PASS; 592 PE instances OK, 607,944 PE-cycles, 0 mismatches |
| Control: lock-step with a mutant new PE (`filters_reg_M0 + 1`) | detected at once (`PE LOCKSTEP MISMATCH ... iact_ready_o`, FAIL). A first mutant (`>` -> `>=` in one `first_spad_words_wght` comparison) did not change the behaviour of the 8x1 case and passed, as it should |
| Test verdicts | identical to before: Conv 34/34; GEMM/Dense 40 PASS / 23 FAIL (all 23 raised by the live FC write check: 17 value, 6 destination, bug #5); MNIST/random 15 passed + 4 xfailed; baseline 9/9 |
| 9 baseline cases (`tools/run_profile.py --compare doc/perf/baseline_2026-10-15`) | 9/9 PASS, **0 cycles and 0 DMA words difference** |
| Vivado 2024.2 full design, synth + place and route at 4 ns (`doc/synth/2026-10-21_route4ns_up3_zu7ev/`) | 0 ERROR / 0 CRITICAL; Synth 8-689 (`PE.v:2210/2211`) 2 -> 0, no other warning ID changed; FF +101 (+2 per PE: the two upper bits of the 7-bit counter are now used), LUT -209 / -80 (synth / route); BRAM / URAM / DSP / CARRY8 unchanged; WNS +0.219 / +0.070 ns (fix14: +0.219 / +0.097), 250 MHz met; the worst paths now lie inside one PE (`gen_sparse_fsm` state -> `iact_data_handler` enables, 89 % route), not on the changed signals |
| Yosys resources of one PE | **not usable**: Yosys mis-elaborates `PE.v:829-830` (bug #20 below), old and new PE gave identical netlists |

## New finding while checking: `PE.v:829-830` forward hierarchical references (bug #20, not fixed)

```verilog
if (SPARSITY_EN == 1) begin : gen_sparse_wght_addr
  assign wght_addr_SPad_addr = gen_sparse_fsm.wght_addr_use_vec ? gen_sparse_fsm.wght_addr_vec : ...;
  assign wght_data_SPad_addr = gen_sparse_fsm.wght_data_use_vec ? wght_data_vec : wght_addr_SPad_data_r;
```

`gen_sparse_fsm` is declared later (line 978). Icarus, Verilator and Vivado resolve the reference; Yosys 0.69 does not:
`Identifier '\gen_sparse_wght_addr.gen_sparse_fsm.wght_addr_vec' is implicitly declared` (also `wght_addr_use_vec`,
`wght_data_use_vec`) and creates new undriven 1-bit wires instead, so a Yosys-built PE does not contain the simulated
weight-SPad address selection (impact on a Yosys netlist not simulated yet). Same class as bug #14 (meaning depends on the tool).
Consequence for this check: Yosys resource numbers of a PE are not trustworthy (old and new PE gave byte-identical Yosys netlists,
which says nothing). Proposed fix (needs approval): declare the three signals at module level before both generate blocks.

## Scripts (`2026-10-21_upstream_cherry_pick/`)

- `make_pe_lockstep.py` + `pe_lockstep_plugin.py`: every PE gets a shadow copy of the old PE (`3717d12`, renamed `PE_orig`)
  with the same inputs; the 8 outputs are compared with `!==` at each falling clock edge, `$fatal` on the first difference.
  `PYTHONPATH=<dir> pytest -p pe_lockstep_plugin ...` compiles it instead of `hdl/PE.v`. The real PE hierarchy is unchanged, so
  the testbench probes still work.
- `probe_spad.py` + `spad_plugin.py`: largest `first_spad_words_o` over all PEs during any test (`SPAD_PROBE_OUT=<json>`).
- `dense_k.py <K> <old|new|lockstep>`: one Dense layer (K inputs, 10 outputs) with the old PE, the new PE or the PE lock-step,
  through `probe_spad.py`.
