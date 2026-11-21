"""Scratch: the proposed one-line decoder, applied in memory only (inspect + exec), then the round trip again."""
import inspect, runpy, sys
from open_eye import rtl_test_utils as rtl
src = inspect.getsource(rtl.compare_stream_Dense)
old = "f = offset + (beat % columns) * per_column + beat // columns"
new = ("f = (offset + (beat // (columns * per_column)) * columns * per_column\n"
       "             + (beat % columns) * per_column + (beat // columns) % per_column)")
assert src.count(old) == 1
exec(src.replace(old, new), rtl.__dict__)
runpy.run_path(sys.argv[1], run_name="__main__")
