"""pytest plugin (-p lockstep_plugin): compile the bug #14 lock-step wrapper instead of hdl/psum_pipeline.v."""
import os

import cocotb_test.simulator

HERE = os.path.dirname(os.path.abspath(__file__))
_orig_run = cocotb_test.simulator.run


def _run(**kw):
    src = kw["verilog_sources"]
    keep = [s for s in src if os.path.basename(s) != "psum_pipeline.v"]
    assert len(keep) == len(src) - 1, "psum_pipeline.v not found in the sources"
    kw["verilog_sources"] = keep + [os.path.join(HERE, f) for f in
                                    ("psum_pipeline_lockstep.v", "psum_pipeline_orig.v", "psum_pipeline_fix.v")]
    return _orig_run(**kw)


cocotb_test.simulator.run = _run
