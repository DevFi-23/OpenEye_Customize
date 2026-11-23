#!/bin/bash
# verify.sh: checks of the second round of 2026-11-22 (#50 clamp + guard, #7 odd-channel padding, #9 padding-slot mask;
# current_x widening reverted), one after another, from the repository root (about 4.5 hours): lint, Python unit tests,
# the full RTL regression (254 tests, regression.sh), the 12 profiler cases against baseline_2026-11-18, the 16 Table 3
# configurations against paper_table3_2026-11-18. The RTL is the one of 2026-11-22_route4ns_fix51_zu7ev (no Vivado run).
D=doc/experiments/2026-11-22_bug50_51/round2
export PATH=$PWD/venv/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
venv/bin/python tools/lint_check.py --verilator ~/tools/verilator-5.020/bin/verilator > $D/lint.txt 2>&1; echo "lint exit $?" >> $D/lint.txt
venv/bin/python -m pytest -q -p no:cacheprovider test/test_*.py 2>&1 | tail -1 > $D/unit.txt
mkdir -p $D/regression
doc/experiments/2026-11-07_bug41_stride/regression.sh $D/regression > $D/regression/summary.txt 2>&1
venv/bin/python tools/run_profile.py --jobs 4 --compare doc/perf/baseline_2026-11-18 --clock-mhz 250 \
    --report $D/profile_compare.md > $D/profile_compare.log 2>&1; echo "run_profile exit $?" >> $D/profile_compare.log
venv/bin/python tools/paper_table3.py --run --jobs 6 --save $D/paper_table3 --report $D/paper_table3.md > $D/paper_table3.log 2>&1
echo "paper_table3 exit $?" >> $D/paper_table3.log
venv/bin/python doc/experiments/2026-11-22_bug50_51/compare_profiles.py doc/perf/paper_table3_2026-11-18 $D/paper_table3 \
    > $D/paper_table3_compare.txt 2>&1
