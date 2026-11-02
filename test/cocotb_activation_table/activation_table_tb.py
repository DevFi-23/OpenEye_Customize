# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""cocotb testbench of activation_table: value_o = T[value_i + 128] for all 256 inputs.

A table is loaded the way GET_ACTIVATION loads it (one TABLE_WORD_WIDTH-bit word per clock, entry w * E + b in
byte b of word w, E = TABLE_WORD_WIDTH / 8), every input is read back (the banks are read without a clock), a second
table is loaded over the first, and words offered with we_i = 0 must not change the table.
"""
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def words(table, entries):
    return [sum((table[w * entries + b] & 0xFF) << (8 * b) for b in range(entries)) for w in range(256 // entries)]


async def load(dut, table, entries, we=1):
    for w, word in enumerate(words(table, entries)):
        await FallingEdge(dut.clk_i)
        dut.we_i.value = we
        dut.waddr_i.value = w
        dut.wdata_i.value = word
    await FallingEdge(dut.clk_i)
    dut.we_i.value = 0


async def check(dut, table):
    for value in range(-128, 128):
        dut.value_i.value = value & 0xFF
        await Timer(1, unit="ns")
        got = dut.value_o.value.to_signed()
        assert got == table[value + 128], "input %d: DUT %d, table %d" % (value, got, table[value + 128])


@cocotb.test()
async def test_activation_table(dut):
    width = int(os.environ["TABLE_WORD_WIDTH"])
    entries = width // 8
    rng = random.Random(int(os.environ.get("SEED", "1")))
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())
    dut.we_i.value = 0
    dut.value_i.value = 0
    await RisingEdge(dut.clk_i)
    first = [rng.randrange(-128, 128) for _ in range(256)]
    await load(dut, first, entries)
    await check(dut, first)
    second = [rng.randrange(-128, 128) for _ in range(256)]
    await load(dut, second, entries)
    await check(dut, second)
    await load(dut, first, entries, we=0)                   # offered but not written
    await check(dut, second)
    dut._log.info("table word width %d: 3 x 256 entries checked", width)
