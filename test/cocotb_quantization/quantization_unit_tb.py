# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""cocotb testbench of quantization_unit: every output against a Python model of the arithmetic.

quantized_value = clamp(floor(quant_mant * (psum_data + quant_offset) / 2^current_shift), act_min, 127),
three clock cycles after the inputs. A new input set is applied every cycle (the unit is fully pipelined);
act_min only changes between blocks, as the per-layer register does in the design. The activation options
(doc/experiments/2026-11-02_activation_rtl_design.md) are per-layer settings as well, one block per combination:
leaky_en (a negative sum uses neg_mant / neg_shift) and round_en (round half up: + 2^(shift-1) before the shift;
shifts <= ROUND_SHIFT_MAX there, the toolchain's limit).
"""
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

LATENCY = 3
ROUND_SHIFT_MAX = 45


def model(psum, mant, offset, shift, act_min, leaky=False, neg=(0, 0), rounding=False):
    total = psum + offset
    if leaky and total < 0:
        mant, shift = neg
    product = mant * total + ((1 << (shift - 1)) if rounding and shift > 0 else 0)
    return max(act_min, min(127, product >> shift))


def wrap(value, bits):
    return value & ((1 << bits) - 1)


def directed(psum_bits, mant_bits):
    """Values around both bounds and the extremes of every input."""
    cases = []
    for target in (126, 127, 128, 129, 300, -127, -128, -129, -130, -300, -1, 0, 1):
        cases.append((target, 1, 0, 0))                     # mant 1, shift 0: output = psum
        cases.append((target * 8, 1, 0, 3))                  # same after a shift
        cases.append((target * 8 + 7, 1, 0, 3))              # floor of a positive / negative fraction
    top = (1 << (psum_bits - 1)) - 1
    cases += [(top, 1, 0, 0), (-top - 1, 1, 0, 0), (top, (1 << (mant_bits - 1)) - 1, 127, 0),
              (-top - 1, (1 << (mant_bits - 1)) - 1, -128, 0), (top, 3, 127, 40), (-top - 1, 3, -128, 40),
              (1000, 0, 5, 0), (-1000, 255, 0, 127)]
    return cases


@cocotb.test()
async def test_quantization_unit(dut):
    psum_bits = int(os.environ["PSUM_WIDTH"])
    mant_bits = int(os.environ["MANT_WIDTH"])
    shift_bits = int(os.environ["SHIFT_WIDTH"])
    n_random = int(os.environ.get("N_RANDOM", "3000"))
    rng = random.Random(int(os.environ.get("SEED", "1")))
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())
    dut.rst_n.value = 0
    for name in ("quant_mant", "psum_data", "quant_offset", "current_shift", "act_min", "leaky_en", "neg_mant",
                 "neg_shift", "round_en"):
        getattr(dut, name).value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    dut.rst_n.value = 1

    checked = clamped_high = clamped_low = negative_slope = 0
    blocks = [(act_min, False, False, (0, 0)) for act_min in (-128, 0, -17, 5)]   # int8, ReLU, other zero points
    blocks += [(-128, True, False, (13, 7)), (-128, True, True, (164, 17)), (0, True, False, (200, 3)),
               (-128, False, True, (0, 0)), (0, False, True, (0, 0)), (-128, True, True, (1, 0))]
    for act_min, leaky, rounding, neg in blocks:
        max_shift = ROUND_SHIFT_MAX if rounding else (1 << shift_bits) - 1
        stimuli = [(p, m, o, min(sh, max_shift)) for p, m, o, sh in directed(psum_bits, mant_bits)]
        for _ in range(n_random):
            shift = rng.choice([rng.randrange(0, 12), rng.randrange(0, max_shift + 1)])
            mant = rng.choice([1, rng.randrange(0, 256), rng.randrange(0, 1 << (mant_bits - 1))])
            stimuli.append((rng.randrange(-(1 << (psum_bits - 1)), 1 << (psum_bits - 1)), mant,
                            rng.randrange(-128, 128), shift))
        dut.act_min.value = wrap(act_min, 8)
        dut.leaky_en.value = int(leaky)
        dut.round_en.value = int(rounding)
        dut.neg_mant.value = neg[0]
        dut.neg_shift.value = neg[1]
        expected = []
        for cycle in range(len(stimuli) + LATENCY):
            await FallingEdge(dut.clk_i)
            if cycle >= LATENCY:                           # result of the input applied LATENCY cycles ago
                want = expected[cycle - LATENCY]
                got = dut.quantized_value.value.to_signed()
                assert got == want, ("act_min %d, leaky %d %s, round %d, inputs (psum, mant, offset, shift) %s: "
                                     "DUT %d, model %d" % (act_min, leaky, neg, rounding, stimuli[cycle - LATENCY],
                                                           got, want))
                checked += 1
            if cycle < len(stimuli):
                psum, mant, offset, shift = stimuli[cycle]
                dut.psum_data.value = wrap(psum, psum_bits)
                dut.quant_mant.value = wrap(mant, mant_bits)
                dut.quant_offset.value = wrap(offset, 8)
                dut.current_shift.value = shift
                raw = (mant * (psum + offset)) >> shift
                expected.append(model(psum, mant, offset, shift, act_min, leaky, neg, rounding))
                clamped_high += raw > 127
                clamped_low += raw < act_min
                negative_slope += leaky and psum + offset < 0
    dut._log.info("checked %d outputs: %d clamped to 127, %d clamped to act_min, %d on the negative slope",
                  checked, clamped_high, clamped_low, negative_slope)
    assert clamped_high > 100 and clamped_low > 100 and negative_slope > 1000
