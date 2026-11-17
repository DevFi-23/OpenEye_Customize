# 2026-11-17: upstream commits `c536234` ... `3e2e027` (2026-11-10 to 13), take or not

`git fetch upstream`: `upstream/main` moved from `9a742fb` to `3e2e027`, nine commits by DenLeb. Other branches: only
`dev_asic_sg13g2` moved (ASIC flow logs, not related to the FPGA fork); the rest are old. Nothing was taken; this note
is the evidence. Method as in `2026-11-09_upstream_9a742fb_review.md`: a worktree of `3e2e027`, the same 13 cases
through its own Python, RTL and testbench (`2026-11-09_upstream_9a742fb_review/upcmp.sh`, Icarus, CR 2 x CC 2) in sparse
and dense, `dev` (`c749144`, dense fixed) with the same runner, upstream's own Makefile test (Verilator 5.044,
`2026-11-06_upstream_dw_review/mkv.sh`), and the dense cases of bugs #46 / #47.

## 1. The commits

| Commit | Files | Change |
|---|---|---|
| `c536234` "Fixed bugs in the Inter-Layeroperability flow" | `OpenEye_FPGA.v`, `iact_stream_constructor.v`, `psum_pipeline.v`, `delay_cluster.v`, `layer_parameters.py` | Write-back of the 2-channel iact layout of `9594bec` / `9a742fb` (converter loop limits / 2, quantizer input zeroed in the last 8 cycles of `SEND_PSUM_TO_IACT`), `dilation_pes / NUM_GLB_IACT`; `delay_cluster` `ready_o` taken from stage 0 instead of stage 21 |
| `65bce70` | Makefile | comments |
| `86e8d56` "Fixed multiple erors for very small kernel sizes" | `PE.v` | dense FSM, `WAIT_TO_SEND_PSUM`: products still in the pipeline are accumulated (`values_valid`), `psum_select` only when not computing |
| `31ec523`, `ede6109` "better testing of PEs" | `PE.v`, `test/cocotb_PE/*` | dense FSM `CALCULATING`: psum read-after-write forwarding, same lane (the fork's #46 part (a)); **sparse FSM** BLOCK 1b: `wght_data_vec` incremented unconditionally; PE testbench rework |
| `1398987` "Corrected pooling features" | `OpenEye_FPGA.v`, `ring_buffer_pipelined.v` | max pooling over 2-channel words (`CHANNELS_PER_WORD` 4 -> 2), one pipeline stage less |
| `7af64ca` "Fixed parameters for DW Convolutions" | `layer_parameters.py` | iact read / write loop parameters of depthwise layers |
| `6c5ca66` "Removed redundant FC operations" | `iact_stream_constructor.v`, `layer_parameters.py`, a test | the fully connected branch of the iact constructor removed (about 100 lines); test configuration reduced to CR 1, `NUM_GLB_IACT` 1 |
| `3e2e027` "Fixed multiple wrong dimensions" | `OpenEye_FPGA.v`, `data_create.py`, `layer_parameters.py`, `rtl_test_utils.py`, `test_utils_main.py` | write-back x position, reference positions in 2-channel order, model `Conv_FC`, a quantization shift 6 -> 7 |

Direction: as on 2026-11-06, the dense datapath with 2-channel iact groups, 1 x 1 cluster, `PARALLEL_MACS` 1 (their
Makefile), depthwise, PE unit tests.

## 2. Results

Simulated ns; FAIL = values or iact buffer wrong, "hang" = no FSM progress for 200,000 cycles.

| Case | `dev` sparse (2026-11-09) | **`dev` dense** (now) | upstream `3e2e027` sparse | upstream `3e2e027` dense | upstream `9a742fb` dense |
|---|---|---|---|---|---|
| Conv 8x4, 4 ch -> 16 | PASS 21,750 | PASS 20,960 | hang | PASS 21,000 | PASS 21,000 |
| Conv 8x4, 2 ch | PASS 17,920 | PASS 17,430 | FAIL | PASS 17,380 | PASS 17,470 |
| Conv 8x4, 3 ch | FAIL (#7) | FAIL (#7) | FAIL | FAIL | FAIL |
| Conv 8x4, 8 ch | PASS 30,520 | PASS 28,920 | FAIL | PASS 28,960 | PASS 28,960 |
| Conv 8x4, 16 ch | PASS 48,080 | PASS 44,840 | FAIL | PASS 44,880 | PASS 44,880 |
| Conv 8x8, 4 ch, `NUM_GLB_IACT` 3 | PASS 30,740 | PASS 29,860 | FAIL | PASS 29,900 | PASS 29,900 |
| Conv 8x8, 2 ch, `NUM_GLB_IACT` 3 | PASS 26,510 | PASS 25,900 | hang | PASS 25,860 | PASS 25,940 |
| Conv 28x28x1 -> 32 | PASS 403,820 | PASS 400,090 | FAIL | PASS 376,210 | PASS 376,210 |
| Conv -> Conv 8x4x4 | PASS 35,500 | PASS 34,560 | hang | FAIL | FAIL |
| Conv -> Conv, `NUM_GLB_PSUM` 2 | PASS 29,800 | PASS 28,800 | hang | FAIL (iact buffer) | FAIL |
| Conv -> Pool -> Conv 8x4x2 | PASS 38,130 | PASS 37,040 | FAIL (iact buffer) | FAIL | FAIL |
| Conv -> Conv 8x4x8 | PASS 46,990 | PASS 45,040 | FAIL (iact buffer) | **PASS 45,190** | FAIL |
| Conv 16x4, 6 ch | FAIL (#45) | FAIL (#45) | FAIL | FAIL | FAIL |
| **PASS** | 11 / 13 | **11 / 13** | **0 / 13** | 8 / 13 | 7 / 13 |

* Upstream's own Makefile test (dense, 1 x 1 cluster, `PARALLEL_MACS` 1): default (`Convolution_Stack`), `Convolution_Single`
  8x8x4 -> 16, `Convolution_Stack`: 3 / 3 PASS.
* Bug #46 on upstream dense at 2 x 2 clusters: 8x4x4 -> 2 and 8x4x4 -> 4 still FAIL (their forwarding of `31ec523` covers
  the same lane only, the M0 <= 2 address reset is missing). Bug #47: `data_pipeline_wght.v` unchanged and the Python still
  drops all-zero weight words, so a zero weight pair still breaks a dense convolution there.
* The fork's dense FSM with 1 x 1 kernels (what `86e8d56` addresses upstream): 8x4x4 -> 16 single and stacked, 8x4x4 -> 4
  and -> 2, dense: 4 / 4 PASS; 8x4x4 -> 16 1 x 1 sparse PASS. The fork does not show that bug.
* Speed: equal within 0.2 % in every case both pass, except 28x28x1 -> 32 (upstream 6 % faster: 32 psums per PE of
  `b10db82`, not in the fork, noted before).

## 3. Decision

Not taken. The commits continue the 2-channel rewrite of `9594bec` / `9a742fb` that the fork did not take (it breaks the
sparse mode, 13 / 13 wrong, and the fork's 4-channel write-back passes every chain at 2 x 2 clusters); they remove the
FC branch of the iact constructor that the fork's Dense fixes (#26, #36) use; `31ec523` changes the weight-vector
increment of the sparse FSM, which the fork verifies on every run and upstream no longer tests. The two dense-FSM fixes
are either already in the fork in a fuller form (#46) or not needed by it (1 x 1 kernels pass). Worth keeping in view:
the `delay_cluster` ready timing (no fork case fails on it) and, as before, 32 psums per PE (6 % on large layers).

## 4. Algorithm by algorithm (added 2026-11-17, evaluation only)

| Upstream algorithm | Commits | Against the fork | Better? | Proposal |
|---|---|---|---|---|
| iact buffer, write-back and pooling in 2-channel groups | `9594bec`, `9a742fb`, `c536234`, `1398987`, `3e2e027` | equal cycles (within 0.2 %); 3 and 6 channels still wrong; write-back hard-coded to 2; sparse 0 / 13 | no | not taken; #7 / #45 are cheaper to handle by zero-channel padding on the host (the sparse PE skips the zeros) |
| interleaved iact banks (`NUM_GLB_IACT > 1`) | `9594bec` | one copy of the data instead of N, an N x narrower bus, N x the buffer capacity; equal cycles | yes (memory, wiring) | later: every configuration the fork measures has `NUM_GLB_IACT = 1` |
| FC branch of the iact constructor removed | `6c5ca66`, `3e2e027` | about 100 RTL lines fewer; the fork's Dense path (#19, #26, #36) runs MNIST and the Table 2 network, upstream's test shrank to CR 1 | no | not taken |
| dense FSM: psum forwarding, products in flight for tiny kernels | `31ec523`, `86e8d56` | the fork's #46 is the fuller fix (M0 <= PM reset too); 1 x 1 kernels pass on the fork | no | already in the fork |
| `wght_data_vec` increment in the sparse FSM | `31ec523` | upstream no longer tests sparse | risk | not taken |
| `delay_cluster` ready from stage 0 | `c536234` | no fork case fails on it | unknown | measure with a memory model that stalls |
| 32 psums per PE | `b10db82` (still in `3e2e027`) | one weight pass instead of two when a PE holds more than 16 filters: 28 x 28 x 1 -> 32 6 % faster | **yes** (measured) | port the idea, Python only: `layer_parameters.py` 16 -> `params.Psums_per_PE` (already 32), with the fork's #39 formula and the #40 / #48 guards |

Fixing the 2-channel rewrite to reach the fork's level would redo the fork's fixes (Python buffer word 96 against 64 bit in
sparse, write-back for `NUM_GLB_PSUM` 2 (#25), output-size geometry (#41c), the Dense path (#26, #36), #46 reset, #47) for the
same cycle counts: not worth it.
