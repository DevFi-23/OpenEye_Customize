"""pytest plugin (-p spad_plugin): run the test through probe_spad.probe_test."""
import os

import cocotb_test.simulator

HERE = os.path.dirname(os.path.abspath(__file__))
_orig_run = cocotb_test.simulator.run


def _run(**kw):
    kw["module"] = "probe_spad"
    kw["testcase"] = "probe_test"
    kw["python_search"] = list(kw.get("python_search", [])) + [HERE]
    kw.setdefault("extra_env", {})["SPAD_PROBE_OUT"] = os.environ["SPAD_PROBE_OUT"]
    return _orig_run(**kw)


cocotb_test.simulator.run = _run
