#!/bin/bash
# seeded.sh <dev copy> <out dir>: the six dev_p1_subset tests whose times differed only because their data is unseeded,
# again with OPENEYE_SEED=1 on dev (this repository) and on the dev copy, plus the two trained-MNIST tests the subset
# skipped (checkpoints are untracked; copy doc/demo_notebooks/*.pth into the copy first). One line per run in
# <out dir>/results.txt: <tree> <test id> <last pytest line>. From the repository root.
T=$(cd "$1" && pwd); mkdir -p "$2"; out=$(cd "$2" && pwd); R=$PWD
export PATH=$R/venv/bin:$PATH PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENEYE_SKIP_FC_WRITE_CHECK=1
S="test/cocotb_fpga/test_conv_const.py::test_conv_bias_order[2_kernels]
test/cocotb_fpga/test_mnist_layers.py::test_random_data[8x4_c32_f32]
test/cocotb_fpga/test_mnist_layers.py::test_random_data[8x4_c8_f64]
test/cocotb_fpga/test_mnist_layers.py::test_random_data[8x4_c64_f64]
test/cocotb_fpga/test_mnist_layers.py::test_random_data[14x14_c32_f32]
test/cocotb_fpga/test_mnist_layers.py::test_random_data[mnist_conv2_14x14_c32_f64]"
{ for t in $S; do echo "$R $t seed"; echo "$T $t seed"; done
  echo "$T test/cocotb_fpga/test_bias_per_filter.py::test_bias_per_filter_trained_mnist -"
  echo "$T test/cocotb_fpga/test_real_model.py::test_real_model[0] -"; } > "$out/jobs.txt"
xargs -P 7 -L 1 sh -c 'cd "$0" && if [ "$2" = seed ]; then export OPENEYE_SEED=1; fi; r=$(PYTHONPATH="$0/src" timeout 7200 '$R'/venv/bin/python -m pytest -q -p no:cacheprovider "$1" 2>&1 | tail -1); echo "$0 $1 $r"' \
    < "$out/jobs.txt" > "$out/results.txt"
