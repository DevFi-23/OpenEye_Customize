#!/bin/bash
# verify.sh: checks of the #50 / #51 fixes (2026-11-22), one after another, from the repository root (about 4.5 hours):
# Python unit tests, the full RTL regression (246 tests, regression.sh), the 12 profiler cases against baseline_2026-11-18,
# the 16 Table 3 configurations against paper_table3_2026-11-18. Vivado runs separately (export_vivado.py).
D=doc/experiments/2026-11-22_bug50_51
export PATH=$PWD/venv/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
venv/bin/python -m pytest -q -p no:cacheprovider test/test_*.py 2>&1 | tail -1 > $D/unit.txt
mkdir -p $D/regression
doc/experiments/2026-11-07_bug41_stride/regression.sh $D/regression > $D/regression/summary.txt 2>&1
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-18 --clock-mhz 250 \
    --report $D/profile_compare.md > $D/profile_compare.log 2>&1; echo "run_profile exit $?" >> $D/profile_compare.log
venv/bin/python tools/paper_table3.py --run --jobs 6 --save $D/paper_table3 --report $D/paper_table3.md > $D/paper_table3.log 2>&1
echo "paper_table3 exit $?" >> $D/paper_table3.log
venv/bin/python $D/compare_profiles.py doc/perf/paper_table3_2026-11-18 $D/paper_table3 > $D/paper_table3_compare.txt 2>&1
