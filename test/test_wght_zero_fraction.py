# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Unit tests of the test hook OPENEYE_WGHT_ZERO_FRACTION (DRAMContents.apply_wght_zero_fraction): exact share per
layer, a larger share zeroes a superset of the positions, no zero left outside the chosen set, Conv2D only unless
OPENEYE_WGHT_ZERO_DENSE=1 (then the Dense layers too), and the Conv2D result does not depend on that switch."""
import copy
import types

import numpy as np
import pytest

from open_eye.DRAM import DRAMContents


def _layers():
    rng = np.random.RandomState(3)
    conv = rng.randint(-3, 4, size=(4, 6, 3, 3)).tolist()       # [c][f][y][x], with natural zeros
    dense = rng.randint(-3, 4, size=(10, 40)).tolist()          # [out][in]
    params = [types.SimpleNamespace(layer_name="Convolution2D"), types.SimpleNamespace(layer_name="Pooling"),
              types.SimpleNamespace(layer_name="Dense")]
    return params, [conv, [], dense]


def _apply(monkeypatch, fraction, dense=False):
    params, weights = _layers()
    monkeypatch.setenv("OPENEYE_WGHT_ZERO_FRACTION", str(fraction))
    monkeypatch.setenv("OPENEYE_SEED", "1")
    if dense:
        monkeypatch.setenv("OPENEYE_WGHT_ZERO_DENSE", "1")
    else:
        monkeypatch.delenv("OPENEYE_WGHT_ZERO_DENSE", raising=False)
    holder = types.SimpleNamespace(weights=copy.deepcopy(weights))
    DRAMContents.apply_wght_zero_fraction(holder, params)
    return weights, holder.weights


def _zeros(w):
    return {i for i, v in np.ndenumerate(np.asarray(w)) if v == 0}


@pytest.mark.parametrize("fraction", [0, 0.2, 0.4, 0.6, 0.8])
def test_exact_share_conv_and_dense(monkeypatch, fraction):
    _, w = _apply(monkeypatch, fraction, dense=True)
    for layer in (w[0], w[2]):
        n = np.asarray(layer).size
        assert len(_zeros(layer)) == int(round(fraction * n))


def test_dense_untouched_without_switch(monkeypatch):
    before, w = _apply(monkeypatch, 0.6, dense=False)
    assert w[2] == before[2]
    assert len(_zeros(w[0])) == int(round(0.6 * np.asarray(w[0]).size))


def test_conv_same_with_and_without_switch(monkeypatch):
    _, a = _apply(monkeypatch, 0.4, dense=False)
    _, b = _apply(monkeypatch, 0.4, dense=True)
    assert a[0] == b[0]


def test_superset_and_values_kept(monkeypatch):
    before, low = _apply(monkeypatch, 0.2, dense=True)
    _, high = _apply(monkeypatch, 0.8, dense=True)
    for k in (0, 2):
        assert _zeros(low[k]) <= _zeros(high[k])
        b, lo = np.asarray(before[k]), np.asarray(low[k])
        keep = (lo != 0) & (b != 0)
        assert (lo[keep] == b[keep]).all()          # nonzero weights outside the chosen set are unchanged
