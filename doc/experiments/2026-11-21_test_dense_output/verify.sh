#!/bin/bash
# verify.sh: checks of the #21 testbench fix (2026-11-21), one after another, from the repository root (about 1.5 hours):
# Python unit tests, the full RTL regression (240 tests, regression.sh) and the 12 profiler cases against baseline_2026-11-18.
D=doc/experiments/2026-11-21_test_dense_output
export PATH=$PWD/venv/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
venv/bin/python -m pytest -q -p no:cacheprovider test/test_*.py 2>&1 | tail -1 > $D/unit.txt
doc/experiments/2026-11-07_bug41_stride/regression.sh $D/regression > $D/regression/summary.txt 2>&1
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-18 --clock-mhz 250 \
    --report $D/profile_compare.md > $D/profile_compare.log 2>&1; echo "run_profile exit $?" >> $D/profile_compare.log
