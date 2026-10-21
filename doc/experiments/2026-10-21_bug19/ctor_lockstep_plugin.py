"""pytest plugin (-p ctor_lockstep_plugin): compile iact_stream_constructor_lockstep.v (+ _orig) instead of
hdl/iact_stream_constructor.v, and an extra root module fc_guard_monitor."""
import os

import cocotb_test.simulator

HERE = os.path.dirname(os.path.abspath(__file__))
_orig_run = cocotb_test.simulator.run


def _run(**kw):
    src = kw["verilog_sources"]
    keep = [s for s in src if os.path.basename(s) != "iact_stream_constructor.v"]
    assert len(keep) == len(src) - 1, "iact_stream_constructor.v not found in the sources"
    kw["verilog_sources"] = keep + [os.path.join(HERE, f) for f in
                                    ("iact_stream_constructor_lockstep.v", "iact_stream_constructor_orig.v")]
    if os.path.exists(os.path.join(HERE, "fc_guard_monitor.v")):
        kw["verilog_sources"].append(os.path.join(HERE, "fc_guard_monitor.v"))
        kw["compile_args"] = list(kw.get("compile_args", [])) + ["-s", "fc_guard_monitor"]
    return _orig_run(**kw)


cocotb_test.simulator.run = _run
