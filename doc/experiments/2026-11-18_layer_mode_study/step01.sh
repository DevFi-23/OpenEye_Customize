#!/bin/bash
# step01.sh <out dir>: steps 0 and 1 of the per-layer mode plan (README_FI section 2), one after the other, 6 jobs at a
# time: unit tests, the regression, new baselines (12 cases, Table 3 sparse / dense / ReLU sparse, trained MNIST with
# 4 activations x 2 modes), then the zero-share sweep in both modes. Progress in <out dir>/progress.txt. About 5 hours.
# Vivado is run separately afterwards (alone). From the repository root.
set -u
OUT=${1:?out dir}; mkdir -p "$OUT"
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
D=doc/experiments/2026-11-18_layer_mode_study
log() { echo "$(date '+%m-%d %H:%M') $*" >> "$OUT/progress.txt"; }
log "start at $(git log --oneline -1)"
venv/bin/python -m pytest -q -p no:cacheprovider -o log_cli=false test/test_*.py > "$OUT/unit.log" 2>&1
log "unit tests: $(tail -n 1 "$OUT/unit.log")"
bash doc/experiments/2026-11-07_bug41_stride/regression.sh "$OUT/reg" > "$OUT/reg.log" 2>&1
log "regression (ids, passed, xfailed, others): $(tr '\n' ' ' < "$OUT/reg.log")"
venv/bin/python tools/run_profile.py --jobs 6 --compare doc/perf/bias_2026-11-17_on --save doc/perf/baseline_2026-11-18 \
    --report doc/perf/baseline_2026-11-18.md > "$OUT/baseline.log" 2>&1
log "baseline 12 cases: done"
venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_2026-11-18 \
    --report doc/perf/paper_table3_2026-11-18.md > "$OUT/t3_sparse.log" 2>&1
log "Table 3 sparse: $(grep -c PASS doc/perf/paper_table3_2026-11-18/status.json) PASS"
SPARSITY_EN=0 venv/bin/python tools/paper_table3.py --run --jobs 6 --save doc/perf/paper_table3_2026-11-18_dense \
    --report doc/perf/paper_table3_2026-11-18_dense.md > "$OUT/t3_dense.log" 2>&1
log "Table 3 dense: $(grep -c PASS doc/perf/paper_table3_2026-11-18_dense/status.json) PASS"
venv/bin/python doc/experiments/2026-11-17_paper_dense_sparse/run_relu.py doc/perf/paper_table3_2026-11-18_relu_sparse 6 \
    > "$OUT/t3_relu.log" 2>&1
venv/bin/python tools/paper_table3.py doc/perf/paper_table3_2026-11-18_relu_sparse \
    --report doc/perf/paper_table3_2026-11-18_relu_sparse.md > /dev/null 2>&1
log "Table 3 ReLU sparse: $(grep -c PASS doc/perf/paper_table3_2026-11-18_relu_sparse/status.json) PASS"
mkdir -p doc/perf/activation_2026-11-18
for a in "relu 0" "leaky_relu 1" "silu 1" "hardswish 1"; do for m in 1 0; do echo "$a $m"; done; done | \
    xargs -P 6 -L 1 sh -c 'tag=1118_${0}_$([ $2 = 1 ] && echo sparse || echo dense); SPARSITY_EN=$2 venv/bin/python \
    doc/experiments/2026-11-12_rounding_modes/run_round.py $0 $1 $tag 2>&1 | grep RESULT; \
    cp test/.temp/round_$tag/profile.json doc/perf/activation_2026-11-18/trained_${0}_img0_$([ $2 = 1 ] && echo sparse || echo dense).json' \
    > "$OUT/mnist.log" 2>&1
log "MNIST: $(grep -c ': PASS' "$OUT/mnist.log") PASS of 8"
venv/bin/python $D/run_sweep.py doc/perf/layer_sweep_2026-11-18_sparse 6 > "$OUT/sweep_sparse.log" 2>&1
log "sweep sparse: $(grep -c PASS doc/perf/layer_sweep_2026-11-18_sparse/status.json) PASS of 60"
SPARSITY_EN=0 venv/bin/python $D/run_sweep.py doc/perf/layer_sweep_2026-11-18_dense 6 > "$OUT/sweep_dense.log" 2>&1
log "sweep dense: $(grep -c PASS doc/perf/layer_sweep_2026-11-18_dense/status.json) PASS of 60"
log "done"
