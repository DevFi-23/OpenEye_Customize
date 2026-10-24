# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""tools/paper_table3.py: Table 3 of the OpenEye paper from saved profiles, per layer and per phase."""
import json
import os
import sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "tools")
sys.path.insert(0, TOOLS)
import paper_table3 as t3  # noqa: E402


def counters(cycles, accepted=0):
    return {"cycles": cycles, "in_offered": accepted, "in_accepted": accepted, "out_words": 0,
            "in_stall": 0, "out_stall": 0}


def profile(scale, layers=2):
    conv = {"name": "Convolution2D", "iact_size_x": 28, "iact_size_y": 28, "channels": 2, "filters": 16,
            "kernel": [3, 3], "stride": 1, "skip_iact": 0, "send_values_out": 0, "pad_channels": 1}
    dense = {"name": "Dense", "iact_size_x": 1568, "iact_size_y": 1, "channels": 1, "filters": 10,
             "kernel": [0], "stride": 1, "skip_iact": 1, "send_values_out": 1, "pad_channels": 0}
    all_layers = [
        {"index": 0, "start_cycle": 0, "info": conv, "total_cycles": 100 * scale,
         "phases": {"load_wght": counters(40 * scale, 40 * scale), "compute": counters(60 * scale)}},
        {"index": 1, "start_cycle": 100 * scale, "info": dense, "total_cycles": 50 * scale,
         "phases": {"load_wght": counters(20 * scale, 20 * scale), "readout": counters(30 * scale)}},
    ][:layers]
    phases = {}
    for layer in all_layers:
        for name, c in layer["phases"].items():
            total = phases.setdefault(name, counters(0))
            for key in total:
                total[key] += c[key]
    return {"config": {}, "total_cycles": sum(l["total_cycles"] for l in all_layers), "phases": phases,
            "layers": all_layers}


def test_config_of():
    assert t3.config_of("paper_cr4_x2_y3") == (4, 2, 3)
    assert t3.config_of("model_mnist16_c2") is None


def test_tables(tmp_path):
    json.dump(profile(1), open(tmp_path / "paper_cr2_x4_y3.json", "w"))
    json.dump(profile(2, layers=1), open(tmp_path / "paper_cr1_x2_y3.json", "w"))
    json.dump({"paper_cr2_x4_y3": "PASS", "paper_cr1_x2_y3": "FAIL (hang)"}, open(tmp_path / "status.json", "w"))
    runs = t3.load_dir(str(tmp_path))
    assert set(runs) == {(2, 4, 3), (1, 2, 3)}
    text = t3.tables(runs, 200.0)
    assert "## Layer 0: Conv 28x28x1->16 k3x3" in text                       # label without the padding channel
    assert "| 2 | 4 | 3 | PASS pad | 200 | 300 | **500** | 40% |" in text    # 40 + 60 cycles x 5 ns
    assert "| 1 | 2 | 3 | FAIL (hang) | - |" in text                          # layer 1 missing in the hung run
    assert "| 2 | 4 | 3 | PASS | 0 | 0 | 300 | 0 | 0 | 0 | 300 | 0 | 0 | 150 | **750** | 83.680 | 70.325 | 154.005 | 0.00 |" in text
    assert t3.tables(runs, 250.0).count("| **600** |") == 1                   # 150 cycles x 4 ns


def test_status_of(tmp_path, monkeypatch):
    monkeypatch.setattr(t3.rp, "LOG_DIR", str(tmp_path))
    (tmp_path / "a.log").write_text("Iact buffer check failed after layer 1 (OPENEYE_KEEP_GOING: the model runs on)\n"
                                    "Iact buffer check failed after layer 5 (OPENEYE_KEEP_GOING: the model runs on)\n"
                                    "result check failed: values differ\n")
    (tmp_path / "b.log").write_text("AssertionError: No FSM progress for 100000 cycles\n")
    assert t3.status_of("a", 1) == "FAIL (iact after L1,5; result)"
    assert t3.status_of("b", 1) == "FAIL (hang)"
    assert t3.status_of("c", 0) == "PASS"
