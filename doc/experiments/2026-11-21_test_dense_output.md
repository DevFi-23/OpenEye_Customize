# The 11 failures of `test/test_dense_output.py`, and what they hide (bug #21) (2026-11-21)

Investigation only: no RTL or Python change. Scripts in `2026-11-21_test_dense_output/`.

## 1. The 11 failures

`venv/bin/python -m pytest -q test/test_dense_output.py`: 11 failed, 0 passed. The test drives two Python functions with
hand-built `SimpleNamespace` fixtures (no simulator):

| Tests | Function under test | Error |
|---|---|---|
| `test_dense_capture_wire_order` ×4, `test_dense_capture_rejects_wrong_length` ×2, `test_dense_capture_rejects_unknown_data`, `test_dense_capture_output_tile_offset` (8) | `rtl_test_utils.compare_stream_Dense` (decodes the Dense DMA output stream) | `AttributeError: ... no attribute 'output_cycles'` (`rtl_test_utils.py:3497`) |
| `test_dense_serial_reference_words` ×3 | `test_utils_main.make_ref` (writes the reference DMA stream `dma_stream_ref.txt`) | `AttributeError: ... no attribute 'needed_psum_transmissions'` (`test_utils_main.py:316`) |

README_FI said "`SimpleNamespace` without `output_cycles`"; that is 8 of them, the other 3 miss `needed_psum_transmissions`.

## 2. Origin: upstream `23be043`, inherited by the fork

| Tree | Result |
|---|---|
| `08c90ae` (2026-09-23, Hendrik Woehrle, "debugged fc layer": adds the test) | 11 PASS |
| `23be043^` | 11 PASS |
| `23be043` (2026-10-01, DenLeb, "Fixed many bugs for Dense Layer") | 11 FAIL (the same two errors) |
| `c4bd562` (2026-10-02, base of `dev`) | 11 FAIL |
| `dev` today | 11 FAIL |
| `upstream/main` `3e2e027` | 11 FAIL, other errors (`compare_stream_Dense()` now needs `rel_layers`; reference file not written) |

Each tree was run from `git archive` into a scratch directory with `PYTHONPATH=<tree>/src`. `23be043` made Dense layers
with more than `16 x Clusters_X` outputs use several psum passes (`needed_psum_transmissions = output_cycles =
ceil(filters / (16 * Clusters_X))`, `layer_parameters.py:1967-1970`) and changed the two functions:
`compare_stream_Dense` expects `columns * per_column * output_cycles` beats, `make_ref` writes one block per pass. The
test fixtures were not updated. Upstream touched the test once since (`36395dd`, `dram.fmap[1][0]` for its DAG), never
the fixtures.

**Adding the two fields to the fixtures (`output_cycles=1`, `needed_psum_transmissions=1`, i.e. one psum pass, the only
case that existed when the test was written) makes 11/11 pass on today's `dev`** (`fixture.diff`). The test only
covers one pass.

## 3. What the test does not cover: the decoder is wrong for more than one pass = bug #21

`make_ref` (and the psum buffer, doc/experiments/2026-10-24_bug26_dense_writeback.md section 8) order the outputs as
pass r, address a, column c: beat `b = r*CX*P + a*CX + c` carries filter `f = r*CX*P + c*P + a` (P = `used_psum_per_PE`,
CX = `Clusters_X`). `compare_stream_Dense` decodes `f = offset + (b % CX)*P + b // CX`, which is right only when
r = 0 or CX = 1: for r ≥ 1 it gives `c*P + r*P + a` instead of `r*CX*P + c*P + a`.

**Round trip** (`roundtrip.py`: reference stream of `make_ref` fed into `compare_stream_Dense`, pure Python):

| N | CX | passes | P | outputs right |
|---:|---:|---:|---:|---:|
| 32 | 2 | 1 | 16 | 32/32 |
| 40 | 2 | 2 | 10 | **10/40** |
| 48 | 2 | 2 | 12 | **12/48** |
| 64 | 2 | 2 | 16 | **16/64** |
| 34 | 2 | 2 | 10 | **10/34** |
| 20, 40 | 1 | 2, 3 | 10, 14 | all right |
| 64 | 4 | 1 | 16 | 64/64 |
| 100 | 4 | 2 | 14 | **14/100** |

This is exactly the #21 pattern recorded since 2026-10-21 (N = 40: only the first 10 right, N = 48: the first 12, Dense
16 → 64: 48/64 wrong, "only the first P outputs right").

**On the RTL** (`dense_run.py <K> <N> 1` with `OPENEYE_ALLOW_UNSUPPORTED=1 DUMP_PSUM_BUFFERS=1`, which logs every output
beat; then `rtl_vs_ref.py <run dir> <N> 2`):

| Layer | Testbench verdict | RTL beats == `dma_stream_ref.txt` | Beats decoded with the make_ref layout |
|---|---|---|---|
| Dense 64 → 40 (CR 2, CX 2, 2 passes, P 10) | FAIL, 30 of 40 outputs differ | **40/40** | **40/40 right** |
| Dense 64 → 34 (2 passes, P 10, 6 padding slots) | FAIL, 24 of 34 outputs differ | **40/40** | **34/34 right**, the 6 padding slots (f 34–39) are 0 |

Each run takes about 3.5 minutes. `roundtrip_fixed.py roundtrip.py` applies the proposed decoder line in
memory only (`inspect` + `exec`): every case of the table above comes out right, and the 11 tests with the fixture fields
still pass.

**Conclusion: #21 is not a hardware bug.** The RTL sends every pass in the right order; the testbench's Dense decoder
(`compare_stream_Dense`, written for one pass before `23be043`) puts the outputs of pass ≥ 1 in the wrong place. The
guard `check_dense_readout` (2026-11-07) refuses layers that the hardware computes and sends correctly.

## 4. Proposal (2026-11-21, approved the same day)

1. `test/test_dense_output.py`: the two fixture fields (`fixture.diff`) → 11 PASS. Test-only.
2. `rtl_test_utils.compare_stream_Dense`: decode with the make_ref layout. Add multi-pass cases and a round trip
   `make_ref` → `compare_stream_Dense`, so the two functions cannot drift apart again.
3. Check on the RTL, then the full regression.
4. Remove `check_dense_readout`, update `test_model_guards.py`, README 8b row 21 and 8e.

## 5. The fix (Python only, no RTL)

| File | Change |
|---|---|
| `src/open_eye/rtl_test_utils.py` (`compare_stream_Dense`) | `psum_pass, within_pass = divmod(beat, CX*P)`, `address, column = divmod(within_pass, CX)`, `f = offset + psum_pass*CX*P + column*P + address` (was `offset + (beat % CX)*P + beat // CX`). Identical for every one-pass layer (beat < CX*P), so nothing else changes |
| `src/open_eye/layer_parameters.py`, `dense_mapper.py` | `check_dense_readout` (the #21 refusal of 2026-11-07) removed with its call |
| `test/test_dense_output.py` | 11 → 31 tests: the fixture fields; `test_dense_capture_passes` (6 wire orders: 2 / 3 passes, CX 1 / 2 / 4, padding, extreme values); wrong length and nonzero padding with 2 passes; `make_ref` words for 2 and 3 passes; `test_dense_round_trip`: 9 real Dense layers (`LayerParameters` of Keras `Dense`: 64 → 10 / 32 / 34 / 40 / 100, 16 → 64, 3136 → 40, CR 1 / 2 / 4, CX 1 / 2) through `make_ref` and back |
| `test/test_model_guards.py` | the 5 tests of the refusal → `test_dense_readout_accepted` (4) |
| `test/cocotb_fpga/test_dense_readout.py` (new, in `regression.sh`) | 15 RTL tests of a last Dense layer with several passes (below) |
| `doc/experiments/2026-11-07_bug41_stride/regression.sh` | + `test_dense_readout` (240 tests) |

`doc/experiments/2026-11-07_bug41_stride/scan_guards.py` (a record of 2026-11-07) still calls `check_dense_readout` and
no longer runs as is.

**Negative control:** the new `test_dense_output.py` against the old decoder (`git show HEAD:src/open_eye/rtl_test_utils.py`
in a copy of `src/`): 12 failed, 19 passed. Every multi-pass case with CX > 1 fails (5 wire orders, the nonzero padding
check, 6 round trips); the one-pass cases and the CX = 1 cases pass, as the analysis of section 3 says.

## 6. Verification

| Check | Result |
|---|---|
| Python unit tests `test/test_*.py` | **616 passed, 0 failed** (before: 578 + 8 of `test_wght_zero_fraction.py` passed, 11 failed) |
| `test_dense_readout.py` (15 RTL tests, `rtl_readout/results.txt`) | **15/15 PASS**; in every run `output.txt` (the beats the RTL sent) is byte for byte `dma_stream_ref.txt`; the two chains also pass the iact buffer check after the write-back layer |
| Full RTL regression (`regression/`) | **240 = 236 PASS + 4 known xfail** (3 channels ×2 #7, Conv3 ×2 #9), 0 FAIL; about 2 h 45 min at 6 processes |
| 12 profiler cases vs `baseline_2026-11-18` (`profile_compare.md`) | **12/12 PASS, identical** to `baseline_2026-11-18` in every cycle and every DMA word |

The 15 RTL tests, all with seed 1 (2 cluster columns unless noted):

| Case | Layer | Configuration | Passes × P | Time |
|---|---|---|---|---:|
| `k64_n40` | 64 → 40 | CR 2, `NUM_GLB_IACT` 1, `NUM_GLB_PSUM` 4 | 2 × 10 | 29 s |
| `k64_n34` | 64 → 34 | same, 6 padding slots | 2 × 10 | 28 s |
| `k16_n64` | 16 → 64 | same | 2 × 16 | 26 s |
| `k64_n100` | 64 → 100 | same, `QUANT_AMOUNT` 128 | 4 × 14 | 42 s |
| `k1568_n40` | 1568 → 40 | same | 2 × 10 | 96 s |
| `k64_n40_cr1`, `_cr4` | 64 → 40 | CR 1, CR 4 | 2 × 10 | 24 s, 34 s |
| `k64_n40_iact3`, `_psum2` | 64 → 40 | `NUM_GLB_IACT` 3, `NUM_GLB_PSUM` 2 | 2 × 10 | 29 s, 22 s |
| `k64_n40_dense` | 64 → 40 | dense hardware (`SPARSITY_EN` 0) | 2 × 10 | 23 s |
| `k64_n32_n40` | 64 → 32 → 40 | write-back, then 2-pass read-out | 2 × 10 | 26 s |
| `k64_n64_n40` | 64 → 64 → 40 | 2-pass write-back, 2-pass read-out | 2 × 10 | 28 s |
| `gemm_cx1_k64_n40` | 64 → 40 | `test_gemm_layer`, 1 cluster column | 3 × 14 | 223 s |
| `gemm_pm1_k64_n40` | 64 → 40 | `test_gemm_layer`, `PARALLEL_MACS` 1 | 2 × 10 | 224 s |
| `gemm_os_k64_n40` | 64 → 40 | `test_gemm_layer`, output stationary | 2 × 10 | 222 s |

Commands: `venv/bin/python -m pytest -q test/test_dense_output.py test/test_model_guards.py`;
`venv/bin/python -m pytest -q test/cocotb_fpga/test_dense_readout.py`; everything at once: `verify.sh` (about 1.5 hours).

Host software that reads Dense results (e.g. `fpga/sw`) must use the same order (pass, address, column).
