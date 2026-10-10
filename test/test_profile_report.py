# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Checks for the payload and bus-efficiency arithmetic of open_eye.profile_report."""
import json

import pytest

from open_eye import profile_report


def make_profile(layer="Convolution_Single"):
    config = {"LAYER": layer, "NUM_FILTERS": "4", "KERNEL_SIZE_X": "3", "KERNEL_SIZE_Y": "3",
              "INPUT_SIZE_X": "8", "INPUT_SIZE_Y": "1", "INPUT_CHANNELS": "4", "STRIDE": "1",
              "DMA_BITWIDTH": 64, "DATA_PSUM_BITWIDTH": 20, "CLUSTER_ROWS": 2,
              "CLUSTER_COLUMNS": 2, "NUM_GLB_IACT": 1, "NUM_GLB_WGHT": 3, "NUM_GLB_PSUM": 4,
              "QUANT_AMOUNT": "32", "CLOCK_NS": 10}
    phases = {
        "load_wght": {"cycles": 20, "in_offered": 20, "in_accepted": 18, "out_words": 0},
        "compute": {"cycles": 60, "in_offered": 0, "in_accepted": 0, "out_words": 0},
        "readout": {"cycles": 20, "in_offered": 0, "in_accepted": 0, "out_words": 16},
    }
    return {"config": config, "total_cycles": 100, "layer_starts": [0], "phases": phases}


def test_payload_of_single_conv_layer():
    payload = profile_report.payload_bytes(make_profile()["config"])
    assert payload == {
        "load_iact": 8 * 1 * 4,
        "load_wght": 4 * 4 * 3 * 3,
        "load_bias": 4 * 3,          # 20-bit psum -> 3 bytes per filter
        "load_quant": 20,            # 4 entries x 40 bits
        "readout": 8 * 1 * 4 * 3,
    }


def test_payload_unknown_for_other_layers():
    assert profile_report.payload_bytes(make_profile("Convolution_Stack")["config"]) == {}


def test_summary_rows():
    rows = {r["phase"]: r for r in profile_report.summarise(make_profile())}
    assert list(rows) == ["load_wght", "compute", "readout"]  # PHASE_ORDER, absent phases skipped
    assert rows["compute"]["share"] == pytest.approx(0.6)
    assert rows["load_wght"]["refused_words"] == 2
    assert rows["load_wght"]["efficiency"] == pytest.approx(144 / (18 * 8))
    assert rows["readout"]["efficiency"] == pytest.approx(96 / (16 * 8))
    assert rows["compute"]["efficiency"] is None


def test_main_writes_csv(tmp_path, capsys):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(make_profile()))
    out_csv = tmp_path / "out.csv"
    assert profile_report.main([str(path), "--csv", str(out_csv)]) == 0
    assert "| compute | 60 | 60.0% |" in capsys.readouterr().out
    assert len(out_csv.read_text().strip().splitlines()) == 1 + 3


@pytest.mark.parametrize("path,case", [
    ("doc/perf/baseline/8x1_f4_q32_dma64.json", "8x1_f4_q32_dma64"),
    ("test/.temp/test_cocotb_fpga_test_profile.py_test_profile_conv_8x1_f4_q32_dma64_/profile.json",
     "8x1_f4_q32_dma64"),
    ("test/.temp/some_other_sim/profile.json", "some_other_sim"),
])
def test_case_name(path, case):
    assert profile_report.case_name(path) == case


def test_load_profiles_from_snapshot_and_sim_dirs(tmp_path):
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "a.json").write_text(json.dumps(make_profile()))
    sim = tmp_path / "sims" / "x_test_profile_conv_b_"
    sim.mkdir(parents=True)
    (sim / "profile.json").write_text(json.dumps(make_profile()))
    profiles = profile_report.load_profiles([str(snap), str(tmp_path / "sims")])
    assert sorted(profiles) == ["a", "b"]


def test_compare_rows_deltas():
    base = make_profile()
    new = make_profile()
    new["phases"]["load_wght"] = {"cycles": 5, "in_offered": 5, "in_accepted": 5, "out_words": 0}
    new["total_cycles"] = 85
    rows = {r["phase"]: r for r in profile_report.compare_rows(base, new)}
    assert (rows["load_wght"]["cycles_base"], rows["load_wght"]["cycles_new"]) == (20, 5)
    assert (rows["load_wght"]["words_base"], rows["load_wght"]["words_new"]) == (18, 5)
    assert rows["TOTAL"]["cycles_new"] == 85
    assert rows["TOTAL"]["words_base"] == 18 + 16 and rows["TOTAL"]["words_new"] == 5 + 16


def test_print_comparison(capsys):
    base = {"c": ("b.json", make_profile()), "old_only": ("o.json", make_profile())}
    changed = make_profile()
    changed["total_cycles"] = 80
    changed["config"]["QUANT_AMOUNT"] = "1024"
    profile_report.print_comparison(base, {"c": ("n.json", changed)})
    out = capsys.readouterr().out
    assert "| **TOTAL** | 100 | 80 | -20 (-20.0%) |" in out
    assert "WARNING: configuration differs in QUANT_AMOUNT (32 -> 1024)" in out
    assert "| old_only | 100 | (not run) |" in out
