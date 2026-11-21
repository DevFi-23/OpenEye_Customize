"""Round trip: make_ref writes the reference Dense DMA stream, compare_stream_Dense decodes it.
Scratch experiment only; the project code is not changed."""
import asyncio, logging, math, os, sys, tempfile
from types import SimpleNamespace as NS
from open_eye import rtl_test_utils as rtl, test_utils_main as tum

def run(n, cx, pm=2):
    passes = math.ceil(n / (16 * cx))                       # layer_parameters.py:1967
    per_col = math.ceil(n / cx / pm / passes) * pm          # used_psum_per_PE (used_iact_per_PE cancels)
    values = [(i + 1) * (1 if i % 2 == 0 else -1) for i in range(n)]
    d = tempfile.mkdtemp(); os.chdir(d)
    for name in ("write_weight_file", "write_iact_file", "write_psum_file"):
        setattr(tum, name, lambda *a: None)
    params = NS(SERIAL=1, Clusters_X=cx, Clusters_Y=2, DMA_BITWIDTH=64, DATA_PSUM_BITWIDTH=20, PSUM_Trans_Bitwidth=40)
    layer = NS(layer_name="Dense", used_psum_per_PE=per_col, needed_total_transmissions=1,
               iact_transmissions_pe=1, psum_transmissions_pe=1, needed_psum_transmissions=passes,
               output_cycles=passes, used_Y_cluster=2, psum_output_words=per_col * cx * passes)
    tum.make_ref(params, layer, 0, None, dict(enumerate(values)))
    words = [int(l, 2) for l in open("demo/layer_0_0/dma_stream_ref.txt").read().split()]
    pos = [0]
    class Word(int): pass
    class Sig:
        @property
        def value(self): return Word(words[pos[0]])
    class En:
        @property
        def value(self): return int(pos[0] < len(words))
    async def timer(*a, **k): pos[0] += 1
    rtl.Timer = timer
    rtl.cocotb.start_soon = lambda coro: coro.close()
    dut = NS(data_dma_o=Sig(), enable_dma_o=En(), ready_dma_i=NS(), _log=logging.getLogger("rt"))
    dram = NS(fmap=[None, [None] * n])
    try:
        asyncio.run(rtl.compare_stream_Dense(NS(clk_cycle=20, clk_cycle_unit="ns"), dut, 0, 0,
                                             layer, params, NS(), dram, logging.INFO))
        err = ""
    except AssertionError as e:
        err = f" (assert: {e})"
    got = dram.fmap[1]
    right = [i for i in range(n) if got[i] == values[i]]
    print(f"N={n:3d} CX={cx} passes={passes} P={per_col:2d} words={len(words):3d}: "
          f"{len(right)}/{n} right, first wrong f={next((i for i in range(n) if got[i] != values[i]), '-')}{err}")

logging.disable(logging.CRITICAL)
for n, cx in [(32, 2), (40, 2), (48, 2), (64, 2), (34, 2), (40, 1), (20, 1), (64, 4), (100, 4)]:
    run(n, cx)
