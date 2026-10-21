"""pytest plugin (-p pe_lockstep_plugin): compile PE_lockstep.v + PE_orig.v instead of hdl/PE.v."""
import os

import cocotb_test.simulator

HERE = os.path.dirname(os.path.abspath(__file__))
_orig_run = cocotb_test.simulator.run


def _run(**kw):
    src = kw["verilog_sources"]
    keep = [s for s in src if os.path.basename(s) != "PE.v"]
    assert len(keep) == len(src) - 1, "PE.v not found in the sources"
    kw["verilog_sources"] = keep + [os.path.join(HERE, "PE_lockstep.v"), os.path.join(HERE, "PE_orig.v")]
    return _orig_run(**kw)


cocotb_test.simulator.run = _run
