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


def counters(cycles, accepted=0, out=0):
    return {"cycles": cycles, "in_offered": accepted, "in_accepted": accepted, "out_words": out,
            "in_stall": 0, "out_stall": 0}


def make_model_profile():
    """Three chained layers: Conv (loads the input), Pooling, Dense (reads the result out)."""
    config = dict(make_profile("MNIST")["config"])
    conv = {"name": "Convolution2D", "iact_size_x": 8, "iact_size_y": 4, "channels": 2, "filters": 4,
            "kernel": [3, 3], "stride": 1, "skip_iact": 0, "send_values_out": 0}
    pool = {"name": "Pooling", "iact_size_x": 8, "iact_size_y": 4, "channels": 4, "filters": 1,
            "kernel": [2, 2], "stride": 2, "skip_iact": 1, "send_values_out": 0}
    dense = {"name": "Dense", "iact_size_x": 32, "iact_size_y": 1, "channels": 1, "filters": 10,
             "kernel": [0], "stride": 1, "skip_iact": 1, "send_values_out": 1}
    layers = [
        {"index": 0, "start_cycle": 0, "info": conv, "phases": {
            "load_iact": counters(8, 8), "load_wght": counters(12, 12), "load_bias": counters(16, 16),
            "compute": counters(50), "writeback": counters(14)}},
        {"index": 1, "start_cycle": 100, "info": pool, "phases": {"pooling": counters(20)}},
        {"index": 2, "start_cycle": 120, "info": dense, "phases": {
            "load_wght": counters(40, 40), "compute": counters(30), "readout": counters(10, 0, 2)}},
    ]
    phases = {}
    for layer in layers:
        for name, c in layer["phases"].items():
            total = phases.setdefault(name, counters(0))
            for key in total:
                total[key] += c[key]
    return {"config": config, "total_cycles": sum(p["cycles"] for p in phases.values()),
            "layer_starts": [0, 100, 120], "phases": phases, "layers": layers}


def test_layer_labels():
    labels = [r["label"] for r in profile_report.summarise_layers(make_model_profile())]
    assert labels == ["Conv 8x4x2->4 k3x3", "Pool 8x4x4", "Dense 32->10"]
    padded = dict(make_model_profile()["layers"][0]["info"], pad_channels=1)    # bug #17 workaround
    assert profile_report.layer_label(padded, 0) == "Conv 8x4x1+1pad->4 k3x3"


def test_layer_payload():
    config = make_profile()["config"]                       # 20-bit psum -> 3 bytes
    conv, pool, dense = (layer["info"] for layer in make_model_profile()["layers"])
    assert profile_report.layer_payload_bytes(conv, config, last=False) == {
        "load_iact": 8 * 4 * 2, "load_wght": 4 * 2 * 3 * 3, "load_bias": 4 * 3, "load_quant": 20}
    assert profile_report.layer_payload_bytes(pool, config, last=False) == {}
    assert profile_report.layer_payload_bytes(dense, config, last=True) == {
        "load_iact": 0, "load_wght": 32 * 10, "load_bias": 30, "load_quant": 50, "readout": 30}
    chained = dict(conv, skip_iact=1)
    assert profile_report.layer_payload_bytes(chained, config, last=False)["load_iact"] == 0
    padded = dict(conv, pad_channels=1)         # the zero channel is overhead, not payload
    assert profile_report.layer_payload_bytes(padded, config, last=False) == {
        "load_iact": 8 * 4, "load_wght": 4 * 3 * 3, "load_bias": 4 * 3, "load_quant": 20}


def test_summarise_layers():
    rows = profile_report.summarise_layers(make_model_profile())
    assert [r["cycles"] for r in rows] == [100, 20, 80]
    assert rows[0]["share"] == pytest.approx(0.5)
    assert (rows[0]["in_words"], rows[0]["out_words"]) == (36, 0)
    assert (rows[2]["in_words"], rows[2]["out_words"]) == (40, 2)
    # conv: 64 + 72 + 12 + 20 bytes needed, 36 words of 8 bytes moved in the phases with a payload
    assert rows[0]["efficiency"] == pytest.approx((64 + 72 + 12 + 20) / (36 * 8))
    assert rows[1]["efficiency"] is None
    assert profile_report.summarise_layers(make_profile()) == []   # no per-layer counters


def test_report_prints_layer_table(capsys):
    profile = make_model_profile()
    profile_report.print_report("m", profile, profile_report.summarise(profile))
    out = capsys.readouterr().out
    assert "MNIST (3 layers)" in out
    assert "| us (sim clock 10 ns) |" in out
    assert "| 0 | Conv 8x4x2->4 k3x3 | 100 | 50.0% | 1.0 | 8 | 12 | 16 | 0 | 50 | 14 | 0 | 0 | 36 | 0 |" in out
    assert "| 2 | Dense 32->10 | 80 |" in out


def test_report_clock_option(tmp_path, capsys):
    path = tmp_path / "model.json"
    path.write_text(json.dumps(make_model_profile()))
    try:
        assert profile_report.main([str(path), "--clock-mhz", "250"]) == 0
    finally:
        profile_report.CLOCK_MHZ = None
    out = capsys.readouterr().out
    assert "| us (250 MHz) |" in out
    assert "| 0 | Conv 8x4x2->4 k3x3 | 100 | 50.0% | 0.4 |" in out      # 100 cycles x 4 ns


def test_compare_layer_rows():
    base = make_model_profile()
    new = make_model_profile()
    new["layers"][0]["phases"]["load_bias"] = counters(1, 1)
    rows = profile_report.compare_layer_rows(base, new)
    assert (rows[0]["cycles_base"], rows[0]["cycles_new"]) == (100, 85)
    assert (rows[0]["words_base"], rows[0]["words_new"]) == (36, 21)
    assert rows[1]["cycles_base"] == rows[1]["cycles_new"] == 20
    new["layers"].pop()
    assert profile_report.compare_layer_rows(base, new) == []      # layer counts differ


def test_comparison_reports_new_case(capsys):
    profile_report.print_comparison({"c": ("b.json", make_profile())},
                                    {"c": ("n.json", make_profile()), "m": ("m.json", make_model_profile())})
    out = capsys.readouterr().out
    assert "\n## m\nMNIST (3 layers)" in out
    assert "| 0 | Conv 8x4x2->4 k3x3 | 100 |" in out
    assert "| m | (not in baseline) | 200 |" in out


def test_case_name_of_model_sim_dir():
    path = "test/.temp/test_cocotb_fpga_test_profile.py_test_profile_model_model_mnist16_c2_/profile.json"
    assert profile_report.case_name(path) == "model_mnist16_c2"
