# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Cycle model of external memory (DDR) behind an AXI DMA, for the testbench.

On the FPGA the accelerator's DMA stream is fed by an AXI DMA engine that
reads DDR in bursts (MM2S) and writes results back in bursts (S2MM). The
cocotb testbench used to feed one word every cycle and accept every result
word at once, i.e. an ideal memory. These classes decide, cycle by cycle,
whether a word is available (read side) or can be accepted (write side) for
a configurable memory:

  latency      cycles from a burst request (read) or the end of a write
               burst's data until the data arrives / the write is
               acknowledged
  burst_beats  DMA words per burst (AXI: at most 256)
  outstanding  bursts the DMA may have in flight at once; more outstanding
               bursts hide the latency
  bandwidth    average words per cycle the memory delivers or accepts (<= 1)
  fifo_beats   size of the DMA's stream FIFO in words
  setup        cycles before the first request of a transfer (software and
               DMA programming, once per transfer)
  jitter       random extra latency 0..jitter per burst (seeded, so a run
               is reproducible)
  boundary     bytes; a burst never crosses a multiple of it (AXI: 4 KB)

The defaults (latency 0, one word per cycle, no setup) are the ideal memory
the testbench assumed before. Configuration comes from environment variables
(see from_env), so profile runs can sweep it without code changes.
"""

import os
import random

PRESETS = {
    # No memory effects; must reproduce the ideal-memory measurements.
    "ideal": dict(latency=0, burst_beats=256, outstanding=64, bandwidth=1.0,
                  fifo_beats=1 << 20, setup=0, jitter=0),
    # Illustrative values, NOT calibrated against a board: a burst of 16
    # words, 2 bursts in flight, ~30 cycles of DDR latency.
    "typical": dict(latency=30, burst_beats=16, outstanding=2, bandwidth=1.0,
                    fifo_beats=64, setup=0, jitter=0),
    # Pessimistic: one burst at a time, long latency, shared bandwidth.
    "slow": dict(latency=80, burst_beats=16, outstanding=1, bandwidth=0.5,
                 fifo_beats=32, setup=0, jitter=10),
}

ENV_KEYS = {
    "latency": "OPENEYE_MEM_LATENCY",
    "burst_beats": "OPENEYE_MEM_BURST",
    "outstanding": "OPENEYE_MEM_OUTSTANDING",
    "bandwidth": "OPENEYE_MEM_BANDWIDTH",
    "fifo_beats": "OPENEYE_MEM_FIFO",
    "setup": "OPENEYE_MEM_SETUP",
    "jitter": "OPENEYE_MEM_JITTER",
    "seed": "OPENEYE_MEM_SEED",
}


class MemoryConfig:
    def __init__(self, latency=0, burst_beats=256, outstanding=64, bandwidth=1.0,
                 fifo_beats=1 << 20, setup=0, jitter=0, seed=0, boundary=4096,
                 beat_bytes=8, name="custom"):
        if burst_beats < 1 or outstanding < 1 or fifo_beats < 1:
            raise ValueError("burst_beats, outstanding and fifo_beats must be >= 1")
        if not 0 < bandwidth <= 1:
            raise ValueError("bandwidth must be in (0, 1] words per cycle")
        self.latency = int(latency)
        self.burst_beats = int(burst_beats)
        self.outstanding = int(outstanding)
        self.bandwidth = float(bandwidth)
        self.fifo_beats = int(fifo_beats)
        self.setup = int(setup)
        self.jitter = int(jitter)
        self.seed = int(seed)
        self.boundary = int(boundary)
        self.beat_bytes = int(beat_bytes)
        self.name = name

    def as_dict(self):
        return {k: getattr(self, k) for k in ("name", "latency", "burst_beats", "outstanding",
                                              "bandwidth", "fifo_beats", "setup", "jitter", "seed")}

    @classmethod
    def from_env(cls, beat_bytes=8, environ=None):
        """Config from OPENEYE_MEM (preset name) plus OPENEYE_MEM_* overrides.

        Returns None if neither OPENEYE_MEM nor any override is set: the
        testbench then keeps its original (ideal) stream driver.
        """
        env = os.environ if environ is None else environ
        preset = env.get("OPENEYE_MEM")
        overrides = {k: env[v] for k, v in ENV_KEYS.items() if env.get(v)}
        if not preset and not overrides:
            return None
        if preset and preset not in PRESETS:
            raise ValueError(f"OPENEYE_MEM={preset!r}; known presets: {sorted(PRESETS)}")
        params = dict(PRESETS[preset or "ideal"])
        for key, value in overrides.items():
            params[key] = float(value) if key == "bandwidth" else int(value)
        name = (preset or "custom") + ("+" + ",".join(sorted(overrides)) if overrides else "")
        return cls(beat_bytes=beat_bytes, name=name, **params)


def _split_bursts(n_beats, config):
    """Burst sizes for a transfer of n_beats starting at address 0."""
    per_boundary = max(1, config.boundary // config.beat_bytes)
    bursts, addr = [], 0
    while addr < n_beats:
        size = min(config.burst_beats, n_beats - addr, per_boundary - addr % per_boundary)
        bursts.append(size)
        addr += size
    return bursts


class ReadChannel:
    """MM2S: memory -> accelerator. Call once per clock cycle, in order:

        available = ch.word_available()   # may the host drive valid this cycle?
        ...                               # host drives the word, DUT accepts or not
        ch.end_cycle(accepted)            # accepted: a word left the FIFO this cycle

    A burst request is issued only if the FIFO has room for the whole burst
    and fewer than `outstanding` bursts are in flight. Data of a burst
    starts arriving `latency` (+ jitter) cycles after the request, at most
    `bandwidth` words per cycle overall.
    """

    def __init__(self, config, n_beats):
        self.cfg = config
        self.rng = random.Random(config.seed)
        self.pending = _split_bursts(n_beats, config)   # bursts not yet requested
        self.inflight = []        # [arrival_cycle, words still to arrive]
        self.fifo = 0             # words in the FIFO
        self.reserved = 0         # FIFO space reserved by requested bursts
        self.tokens = 0.0
        self.cycle = 0
        self.stall_cycles = 0     # cycles where the host had no word to drive
        self._deliver()

    def _deliver(self):
        """Issue requests and move arriving data into the FIFO for this cycle."""
        cfg = self.cfg
        if self.cycle >= cfg.setup:
            while (self.pending and len(self.inflight) < cfg.outstanding
                   and self.fifo + self.reserved + self.pending[0] <= cfg.fifo_beats):
                size = self.pending.pop(0)
                delay = cfg.latency + (self.rng.randint(0, cfg.jitter) if cfg.jitter else 0)
                self.inflight.append([self.cycle + delay, size])
                self.reserved += size
        self.tokens = min(self.tokens + cfg.bandwidth, 1.0)
        if self.inflight and self.inflight[0][0] <= self.cycle and self.tokens >= 1.0:
            self.tokens -= 1.0
            self.inflight[0][1] -= 1
            self.reserved -= 1
            self.fifo += 1
            if self.inflight[0][1] == 0:
                self.inflight.pop(0)

    def word_available(self):
        return self.fifo > 0

    def end_cycle(self, accepted):
        if accepted:
            if self.fifo <= 0:
                raise RuntimeError("word accepted while the read FIFO was empty")
            self.fifo -= 1
        elif self.fifo == 0:
            self.stall_cycles += 1
        self.cycle += 1
        self._deliver()


class WriteChannel:
    """S2MM: accelerator -> memory. Call once per clock cycle:

        ready = ch.ready()            # may the host assert ready_dma_i this cycle?
        ...
        ch.end_cycle(word_taken)      # a result word entered the FIFO this cycle

    Words leave the FIFO towards memory at `bandwidth` words per cycle in
    bursts of `burst_beats` (a partial burst is flushed after `burst_beats`
    idle cycles). A burst occupies one of `outstanding` slots until its
    write response arrives `latency` cycles after its last word; with all
    slots busy no new burst starts and the FIFO fills up.
    """

    def __init__(self, config):
        self.cfg = config
        self.rng = random.Random(config.seed + 1)
        self.fifo = 0
        self.burst_left = 0       # words of the burst being sent
        self.responses = []       # cycle at which each outstanding burst completes
        self.tokens = 0.0
        self.idle = 0
        self.cycle = 0
        self.stall_cycles = 0     # cycles where ready was low

    def ready(self):
        return self.fifo < self.cfg.fifo_beats

    def end_cycle(self, word_taken):
        cfg = self.cfg
        if not self.ready():
            self.stall_cycles += 1
        if word_taken:
            self.fifo += 1
            self.idle = 0
        else:
            self.idle += 1
        self.responses = [c for c in self.responses if c > self.cycle]
        if self.burst_left == 0 and self.fifo and len(self.responses) < cfg.outstanding \
                and (self.fifo >= cfg.burst_beats or self.idle >= cfg.burst_beats):
            self.burst_left = min(self.fifo, cfg.burst_beats)
        self.tokens = min(self.tokens + cfg.bandwidth, 1.0)
        if self.burst_left and self.tokens >= 1.0:
            self.tokens -= 1.0
            self.fifo -= 1
            self.burst_left -= 1
            if self.burst_left == 0:
                delay = cfg.latency + (self.rng.randint(0, cfg.jitter) if cfg.jitter else 0)
                self.responses.append(self.cycle + delay)
        self.cycle += 1


def bursts_needed(n_beats, config):
    """Number of bursts the DMA issues for a transfer of n_beats words."""
    return len(_split_bursts(n_beats, config))
