# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Checks of the external-memory model against hand-computed cycle counts."""
import math

import pytest

from open_eye.memory_model import MemoryConfig, ReadChannel, WriteChannel, bursts_needed


def stream(config, n, consumer_ready=lambda cycle: True, limit=100000):
    """Drive a ReadChannel like the testbench does; return (cycles, stall_cycles)."""
    ch = ReadChannel(config, n)
    sent = cycle = 0
    while sent < n:
        accepted = ch.word_available() and consumer_ready(cycle)
        ch.end_cycle(accepted)
        sent += accepted
        cycle += 1
        assert cycle < limit
    return cycle, ch.stall_cycles


def test_ideal_is_one_word_per_cycle():
    cycles, stalls = stream(MemoryConfig(), 1000)
    assert (cycles, stalls) == (1000, 0)


@pytest.mark.parametrize("n,burst,latency", [(64, 16, 20), (100, 16, 7), (10, 16, 5)])
def test_one_outstanding_burst_pays_latency_per_burst(n, burst, latency):
    cfg = MemoryConfig(latency=latency, burst_beats=burst, outstanding=1)
    cycles, stalls = stream(cfg, n)
    assert cycles == n + math.ceil(n / burst) * latency
    assert stalls == math.ceil(n / burst) * latency


def test_enough_outstanding_bursts_hide_the_latency():
    cfg = MemoryConfig(latency=20, burst_beats=16, outstanding=4)
    cycles, _ = stream(cfg, 256)
    assert cycles == 256 + 20          # only the first request waits


def test_half_bandwidth_doubles_the_time():
    cycles, _ = stream(MemoryConfig(bandwidth=0.5), 100)
    assert cycles == pytest.approx(200, abs=2)


def test_setup_is_paid_once():
    cycles, _ = stream(MemoryConfig(setup=50), 100)
    assert cycles == 150


def test_fifo_limits_requests_while_consumer_stalls():
    cfg = MemoryConfig(latency=0, burst_beats=8, outstanding=8, fifo_beats=8)
    ch = ReadChannel(cfg, 64)
    for _ in range(20):               # consumer refuses for 20 cycles
        ch.end_cycle(False)
    assert ch.fifo == 8 and ch.reserved == 0   # one burst fits, the next is not requested


@pytest.mark.parametrize("n,burst,boundary,expected", [
    (1000, 256, 4096, 4),             # 512 words per 4 KB: 256, 256, 256, 232
    (1000, 256, 1024, 8),             # 128 words per 1 KB boundary
    (17, 16, 4096, 2),
])
def test_bursts_respect_boundaries(n, burst, boundary, expected):
    assert bursts_needed(n, MemoryConfig(burst_beats=burst, boundary=boundary)) == expected


def test_jitter_is_reproducible():
    cfg = MemoryConfig(latency=10, burst_beats=8, outstanding=1, jitter=10, seed=3)
    assert stream(cfg, 200) == stream(cfg, 200)
    other = MemoryConfig(latency=10, burst_beats=8, outstanding=1, jitter=10, seed=4)
    assert stream(cfg, 200)[0] >= 200 + 25 * 10 and stream(other, 200)[0] >= 200 + 25 * 10


def test_write_channel_ideal_never_stalls():
    ch = WriteChannel(MemoryConfig())
    for _ in range(500):
        assert ch.ready()
        ch.end_cycle(True)
    assert ch.stall_cycles == 0


def test_write_channel_backpressure():
    # 4-word FIFO, one 4-word burst in flight, 20 cycles until its response:
    # the producer is held back while the burst is outstanding.
    ch = WriteChannel(MemoryConfig(latency=20, burst_beats=4, outstanding=1, fifo_beats=4))
    taken = 0
    for _ in range(200):
        take = ch.ready()
        ch.end_cycle(take)
        taken += take
    assert ch.stall_cycles > 0
    assert taken < 200


def test_from_env():
    assert MemoryConfig.from_env(environ={}) is None
    cfg = MemoryConfig.from_env(environ={"OPENEYE_MEM": "typical"})
    assert (cfg.latency, cfg.burst_beats, cfg.outstanding) == (30, 16, 2)
    cfg = MemoryConfig.from_env(environ={"OPENEYE_MEM": "typical", "OPENEYE_MEM_LATENCY": "50"})
    assert cfg.latency == 50 and cfg.name == "typical+latency"
    cfg = MemoryConfig.from_env(environ={"OPENEYE_MEM_BURST": "8"})
    assert cfg.burst_beats == 8 and cfg.latency == 0 and cfg.name == "custom+burst_beats"
    with pytest.raises(ValueError):
        MemoryConfig.from_env(environ={"OPENEYE_MEM": "nonsense"})
