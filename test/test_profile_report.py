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
