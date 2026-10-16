# Investigation 2026-10-16: bug #14, `results_ready` written by blocking and non-blocking assignments

No RTL was changed. Tools: the fix67 synthesis checkpoint (`C:/openeye_vivado/fix67_impl/reports/OpenEye_FPGA_synth.dcp`),
Vivado 2024.2 in batch mode (synthesis only), Yosys 0.69, Icarus with the Vivado UNISIM models, a scratch cocotb probe around the
unmodified `OpenEye_FPGA_tb`, and a scratch runner that swaps `psum_pipeline.v` for a synthesized netlist in the normal system
test. Scripts: `2026-10-16_bug14/` (see the end of this file).

## 1. The code

`hdl/psum_pipeline.v`, one clocked `always` block (line 255), register `reg results_ready` (line 167):

| Line | State | Assignment |
|---|---|---|
| 274 | reset | `results_ready <= 0;` |
| 429 | `WAIT_TO_SEND_READY_SIGNAL` | `results_ready = 0;` (blocking) |
| 449-457 | `CALCULATE_PSUM` | `if ((results_ready == 0) & (psum_ready_i_reg != 0)) begin results_ready = 1; for (...) results_ready = results_ready & (psum_ready_o_reg[i] \| not_chain_start); end` (blocking) |
| 460 | `CALCULATE_PSUM` | `if (results_ready & (psum_ready_i_reg != 0))` reads the value computed above **in the same cycle** |
| 485 | `CALCULATE_PSUM`, exit | `results_ready <= 1;` |
| 507 | `PSUM_GET_RESULTS` | `results_ready <= 1;` (non-blocking, written first) |
| 522 | `PSUM_GET_RESULTS` | `results_ready = results_ready & (psum_enable_o[i] \| not_chain_start);` (blocking, written second) |
| 536 | `PSUM_GET_RESULTS` | `if (results_ready)` reads the blocking value |
| 900 | `status_reg_enable_reg` | `results_ready <= 0;` |

`not_chain_start = (router_mode_psum[... + 2] == 0) & (CLUSTER_ROWS != 1)`: only the PEs at the start of a psum chain count.

## 2. What the code means in simulation (the reference behaviour)

Blocking assignments update the variable immediately; non-blocking ones are applied at the end of the time step, after all
blocking ones, so **a non-blocking assignment wins even when it is written earlier**. With `ready_all` / `enable_all` = the AND
over the chain-start PEs:

| State | Decision used in this cycle | Register value for the next cycle |
|---|---|---|
| `WAIT_TO_SEND_READY_SIGNAL` | - | 0 |
| `CALCULATE_PSUM` | `rr_now = results_ready \| (psum_ready_i_reg != 0 & ready_all)`; the round starts when `rr_now & (psum_ready_i_reg != 0)` | `rr_now` (sticky: once all PEs were ready together it stays 1), 1 on exit |
| `PSUM_GET_RESULTS` | count a result cycle when `results_ready & enable_all` (`results_ready` is always 1 here) | **1** (the earlier `<= 1` wins) |

So the variable is two things at once: a sticky flag (register) in `CALCULATE_PSUM` and a purely combinational "all PEs stream
now" signal in `PSUM_GET_RESULTS`, whose register value is forced back to 1 every cycle.

## 3. How each tool reads it

| Tool | Behaviour | Evidence |
|---|---|---|
| Icarus (all tests) | Language semantics of section 2 | reference |
| **Vivado 2024.2** (the hardware) | **Same as simulation.** Warning Synth 8-6090 "entire logic could be removed" (10 times), but nothing is removed | E1, E2, E4 |
| **Yosys 0.69** | **Program order: the later blocking assignment overrides the earlier non-blocking one.** In `PSUM_GET_RESULTS` the register gets `enable_all` instead of 1 | E3, E5 |
| Verilator 5.020 | `%Error-BLKANDNBLK ... Unsupported` (4 errors) plus 3 `BLKSEQ` warnings at lines 429/454/522: cannot build the design | lint baseline |

## 4. Experiments

**E1 - fix67 checkpoint (the synthesized hardware).** `psum_pipeline_inst/results_ready_reg` exists (FDCE, INIT 0) with 4 LUTs
(`results_ready_i_1..5`). Its D input depends on the 8 even `psum_ready_o_reg` bits, the 8 `delay_cluster` enable registers that
drive `psum_enable_o` of GLB 0/2, the 8 `router_mode_psum` bit-2 registers, the psum FSM state, `fsm_psum_cycle`,
`psum_ready_i_reg[15]`, `status_reg_enable_reg` and itself; Q drives 147 enables (`fsm_psum_cycle`, `psum_buffer_addr_array`, ...).
The logic was not removed.

**E2 - the pattern alone.** `mix_test.v` copies the assignments of section 1 (4 terms instead of 8). Vivado netlist
(`write_verilog -mode funcsim`) against RTL, 200,000 random cycles: **0 mismatches**. Control: the same netlist against a model in
which every assignment is non-blocking: 24,585 mismatches (that model never sets the flag: it hangs), so the comparison does
discriminate.

**E3 - two lines.** `r <= 1; r = r & a;` in a clocked block: Icarus gives `r = 1` after a cycle with `a = 0`; Yosys
(`proc; opt`) generates `r <= r & a`. The `mix_test` Yosys netlist differs from RTL in 13,820 of 200,000 random cycles.

**E4 - Vivado netlist in the system.** `psum_pipeline` synthesized out of context with the generics of the fix67 hardware
(`CLUSTER_ROWS=2, CLUSTER_COLUMNS=2, NUM_GLB_PSUM=4, TRANS_BITWIDTH_PSUM=20, BUFFER_WIDTH=14, DMA_BITWIDTH=64, QUANT_AMOUNT=32`,
...), functional netlist (5,600 cells: FDCE, LUT1-6, CARRY8, 5 DSP48E2) compiled with the UNISIM models in place of
`psum_pipeline.v` + `quantization_unit.v`, everything else RTL, normal `OpenEye_FPGA_tb`:

| Case | Test | Cycles (gate) | Baseline 2026-10-15 | All phases identical | `verify_conv_output` |
|---|---|---:|---:|---|---|
| 8x1, 4 f | PASS | 568 | 568 | yes | all values = numpy |
| 16x3, 4 f | PASS | 984 | 984 | yes | all values = numpy |
| 32x3, 4 f | PASS | 1,672 | 1,672 | yes | all values = numpy |
| 32x3, 16 f | PASS | 3,556 | 3,556 | yes | all values = numpy |
| mnist1 28x28x4 -> 32 | PASS | 55,048 | 55,048 | yes | 25,088/25,088 = numpy |
| mnist2 14x14x32 -> 32 | PASS | 65,528 | 65,528 | yes | 6,272/6,272 = numpy |
| mnist3 8x8x32 -> 32 | PASS | 20,584 | 20,584 | yes | 2,048/2,048 = numpy |
| random 8x4x32 -> 32 | PASS | 12,200 (RTL 12,200) | - | - | 1,024/1,024 = numpy |
| random 14x14x32 -> 32 | PASS | 65,528 (= mnist2, same shape) | - | - | 6,272/6,272 = numpy (448 padding-only lines, as on RTL) |

(The q1024 and DMA-32 baseline cases need other generics and were not run. Random data is not seeded, so random cases are
checked by PASS + numpy, not by comparing output files.)

**E5 - Yosys netlist in the system.** Same swap with `synth -flatten` of Yosys: the smallest case (8x1, 4 filters) **hangs**. The
stall detector reports the main FSM stuck in `WAIT_FOR_RESULTS` (10) for 20,000 cycles with the psum FSM in `PSUM_GET_RESULTS` (3)
and `fsm_psum_cycle = 0`.

**E6 - why (RTL probe).** Every visit of `PSUM_GET_RESULTS` starts with cycles in which `enable_all = 0`: the results need 28
(8x1) or 16 (32x3, 16 f) cycles to come out of the PE delay chain. In simulation and in Vivado the register is 1 again in every
cycle, so the FSM simply waits. With the Yosys reading the register takes `enable_all = 0` in the first cycle and then
`results_ready & enable_all` stays 0 for ever: the FSM never counts a result. In `CALCULATE_PSUM` the flag is set after 24-90
cycles and is used in the same cycle (sticky, 0 extra latency).

## 5. Conclusion

- **The current FPGA hardware is not affected.** Vivado 2024.2 builds exactly the simulated behaviour (E1, E2, E4); the
  Synth 8-6090 text "entire logic could be removed" is a generic warning, nothing was removed.
- **The code is not portable.** The meaning depends on the tool: Yosys builds hardware that hangs on every layer (E5), Verilator
  refuses it. This blocks the Yosys flows of the repository (`yosys/`, `nextpnr/`, GateMate), any Yosys-based ASIC flow, and
  Verilator simulation (much faster than Icarus). A different Vivado version could legally change its reading too.
- **Two "obvious" fixes are wrong:** turning every assignment into `<=` never sets the flag (hang, control model of E2); keeping
  the mix but reordering it changes the Yosys result but not the portability problem.

## 6. Proposed fix (not applied)

Separate the combinational part from the register; keep the expressions and the cycle timing exactly:

```verilog
// Chain-start PEs (router_mode_psum bit 2, or every PE when CLUSTER_ROWS == 1) that have not
// reported yet. Same terms as before; computed outside the FSM block (bug #14).
wire [CLUSTERS*((NUM_GLB_PSUM+1)/2)-1:0] chain_ready_terms, chain_enable_terms;
genvar rr_cc, rr_cr, rr_g;
generate
  for (rr_cc = 0; rr_cc < CLUSTER_COLUMNS; rr_cc = rr_cc + 1) begin : g_rr_cc
    for (rr_cr = 0; rr_cr < CLUSTER_ROWS; rr_cr = rr_cr + 1) begin : g_rr_cr
      for (rr_g = 0; rr_g < (NUM_GLB_PSUM+1)/2; rr_g = rr_g + 1) begin : g_rr_g
        localparam integer K    = (rr_cc*CLUSTER_ROWS + rr_cr)*((NUM_GLB_PSUM+1)/2) + rr_g;
        localparam integer IDX  = rr_cc*NUM_GLB_PSUM + rr_cr*CLUSTER_COLUMNS*NUM_GLB_PSUM + rr_g*2;
        localparam integer MODE = rr_cc*NUM_GLB_PSUM*ROUTER_MODES_PSUM + rr_cr*CLUSTER_COLUMNS*NUM_GLB_PSUM*ROUTER_MODES_PSUM
                                + rr_g*ROUTER_MODES_PSUM*2 + 2;
        wire not_chain_start = (router_mode_psum[MODE] == 0) & (CLUSTER_ROWS != 1);
        assign chain_ready_terms[K]  = psum_ready_o_reg[IDX] | not_chain_start;
        assign chain_enable_terms[K] = psum_enable_o[IDX]    | not_chain_start;
      end
    end
  end
endgenerate
wire all_psum_ready     = &chain_ready_terms;    // CALCULATE_PSUM: every chain start reported ready
wire all_psum_enable    = &chain_enable_terms;   // PSUM_GET_RESULTS: every chain start streams a result
wire results_ready_calc = results_ready | ((psum_ready_i_reg != 0) & all_psum_ready);   // sticky, used in the same cycle
```

FSM block, only non-blocking assignments to the register:

| State | Before | After |
|---|---|---|
| `WAIT_TO_SEND_READY_SIGNAL` | `results_ready = 0;` | `results_ready <= 0;` |
| `CALCULATE_PSUM` | blocking `if ... results_ready = ...` block; `if (results_ready & (psum_ready_i_reg != 0))` | `results_ready <= results_ready_calc;` `if (results_ready_calc & (psum_ready_i_reg != 0))` |
| `PSUM_GET_RESULTS` | blocking `results_ready = results_ready & ...` in the loop; `if (results_ready)` | line removed; `if (results_ready & all_psum_enable)` |

Reset, line 485 (`<= 1` on exit), 507 (`<= 1`) and 900 stay. Same flip-flop, same function, no extra cycle.

Rejected alternatives:
- All `<=`: never sets the flag (hang).
- All `=`: works in every tool (program order = simulation semantics when nothing is non-blocking) but keeps a register written
  with blocking assignments (`BLKSEQ`, race-prone if another block ever reads it).
- A separate blocking temporary inside the FSM block: smaller diff, but still mixes combinational and sequential code in the
  900-line block.
- Replace the flag by `fsm_psum_cycle != 0`: saves one flip-flop but relies on invariants (`psum_ready_i_reg` all ones,
  `fsm_psum_cycle` cleared on entry) that a later change could break.

## 7. Verification plan after approval

1. Lock-step check: the old and the new `psum_pipeline` side by side in the system test (same inputs, every output compared every
   cycle) for the 9 baseline cases, plus 1M random-input cycles at module level.
2. Vivado netlist of the new module in the system (E4 again) and **Yosys netlist in the system: must PASS** (hangs today).
3. Regression: 34 Conv, 63 GEMM/Dense (same verdict per test), 19 MNIST/random, 9 baseline cases (0 cycle change).
4. Lint: 4 `BLKANDNBLK` errors and 3 `BLKSEQ` warnings of `psum_pipeline.v` disappear (lower the baseline); Yosys resources;
   Vivado: the 10 Synth 8-6090 warnings disappear, resources and fmax unchanged within noise.

## Scripts (`2026-10-16_bug14/`)

- `inspect.tcl`: opens the fix67 checkpoint, reports `results_ready` (E1).
- `mix_test.v`, `synth_check.tcl`: pattern module and out-of-context synthesis of `mix_test` and `psum_pipeline` (E2, E4).
- `two_line.v`: E3.
- `run_gate.py <case> [gate|yosys|rtl|probe]`: runs a layer with the RTL, the Vivado netlist or the Yosys netlist of
  `psum_pipeline`, or with `probe14.py` (E4-E6). Needs `glbl.v`, the UNISIM models and the netlists next to it (paths at the top).
