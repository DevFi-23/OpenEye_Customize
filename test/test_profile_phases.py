# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Phase rules and layer descriptions of the cycle profiler (rtl_test_utils.profile_dma_phases)."""
import types

import pytest

from open_eye import rtl_test_utils as rtu


@pytest.mark.parametrize("main,psum,out_word,phase", [
    (1, 0, 0, "load_config"),
    (4, 0, 0, "load_wght"),
    (5, 0, 0, "load_bias"),
    (8, 0, 0, "convert_iact"),
    (10, 2, 0, "compute"),        # last layer: the main FSM waits for the results
    (10, 0, 0, "compute"),
    (11, 1, 0, "compute"),        # chained layer: the array computes inside RECEIVE_PSUMS_TO_IACT ...
    (11, 2, 0, "compute"),
    (11, 3, 0, "compute"),
    (11, 6, 0, "writeback"),      # ... and writes the requantized results back (SEND_PSUM_TO_IACT)
    (11, 4, 0, "writeback"),
    (11, 0, 0, "writeback"),
    (12, 0, 0, "pooling"),
    (10, 5, 0, "readout"),        # psum FSM in PSUM_SEND_RESULTS
    (1, 0, 1, "readout"),         # last result word still on the bus
    (15, 0, 0, "state_15"),
])
def test_profile_phase(main, psum, out_word, phase):
    assert rtu.profile_phase(main, psum, out_word) == phase


def test_profile_set_layer_info():
    conv = types.SimpleNamespace(layer_name="Convolution2D", iact_size_x=28, iact_size_y=28, channels=2,
                                 filters=32, kernel_size=(3, 3), strideX=1, skipIact=0, send_values_out=0,
                                 pad_channels=1)
    dense = types.SimpleNamespace(layer_name="Dense", iact_size_x=3136, iact_size_y=1, channels=1,
                                  filters=10, kernel_size=[0], strideX=1, skipIact=1, send_values_out=1)
    rtu.profile_set_layer_info([conv, dense])
    info = rtu._PROFILE_LAYER_INFO
    assert info[0] == {"name": "Convolution2D", "iact_size_x": 28, "iact_size_y": 28, "channels": 2,
                       "filters": 32, "kernel": [3, 3], "stride": 1, "skip_iact": 0, "send_values_out": 0,
                       "pad_channels": 1}
    assert (info[1]["name"], info[1]["iact_size_x"], info[1]["skip_iact"]) == ("Dense", 3136, 1)
    assert info[1]["pad_channels"] == 0             # not padded: attribute missing
    rtu.profile_set_layer_info([])
    assert rtu._PROFILE_LAYER_INFO == []
