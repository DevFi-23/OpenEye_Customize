"""2026-11-23: check of the test_dense_output / #21 fix (6a7a323) against upstream. Writes
doc/experiments/2026-11-23_dense_output_check.json. From the repository root:
  venv/bin/python doc/experiments/2026-11-23_dense_output_check.py
1. test/test_dense_output.py on dev and upstream/main's own copy on an archive of upstream/main (PYTHONPATH=its src).
2. Round trip on dev: make_ref writes the Dense reference stream, compare_stream_Dense decodes it, every N 1..200 at
   Clusters_X 1, 2, 4 (the 11-21 roundtrip.py driver).
3. The same layouts decoded with upstream's formula f = (beat % CX) * P + beat // CX (rtl_test_utils.py of 12340ab,
   line 3187), computed directly: how many layer sizes upstream's decoder gets wrong."""
import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))
PY = os.path.join(REPO, "venv", "bin", "python")
ENV = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")


def pytest_counts(cwd, path, env):
    out = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", path], cwd=cwd, env=env,
                         capture_output=True, text=True).stdout
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    errors = {}
    for line in out.splitlines():
        m = re.match(r"E\s+(\w+(?:Error|Exception)): (.*)", line)
        if m:
            key = m.group(1) + ": " + re.sub(r"'/tmp/[^']*'", "'<tmp>/.../dma_stream_ref.txt'", m.group(2))[:110]
            errors[key] = errors.get(key, 0) + 1
    passed = int(re.search(r"(\d+) passed", tail).group(1)) if "passed" in tail else 0
    failed = int(re.search(r"(\d+) failed", tail).group(1)) if "failed" in tail else 0
    return {"passed": passed, "failed": failed, "summary": tail, "errors": errors}


def upstream_tree():
    d = tempfile.mkdtemp(prefix="up_")
    data = subprocess.run(["git", "-C", REPO, "archive", "upstream/main"], capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(d)
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "upstream/main"], capture_output=True,
                            text=True).stdout.strip()
    return d, commit


def roundtrip_dev():
    src = open(os.path.join(REPO, "doc", "experiments", "2026-11-21_test_dense_output", "roundtrip.py")).read()
    src = src.split("logging.disable")[0]
    g = {"__name__": "rt"}
    exec(compile(src, "roundtrip.py", "exec"), g)
    import logging
    logging.disable(logging.CRITICAL)
    cwd = os.getcwd()
    total, wrong = 0, []
    for cx in (1, 2, 4):
        for n in range(1, 201):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                g["run"](n, cx)
            line = buf.getvalue().strip()
            total += 1
            a, b = line.split(": ")[1].split(" right")[0].split("/")
            if a != b or "assert" in line:
                wrong.append(line)
    os.chdir(cwd)
    return {"cases": total, "wrong": len(wrong), "examples": wrong[:5]}


def upstream_formula():
    """Layout of make_ref / the psum buffer: beat b = r*CX*P + a*CX + c carries f = r*CX*P + c*P + a."""
    total, wrong, examples = 0, 0, []
    for cx in (1, 2, 4):
        for n in range(1, 201):
            passes = math.ceil(n / (16 * cx))
            p = math.ceil(n / cx / 2 / passes) * 2
            bad = 0
            for beat in range(p * cx * passes):
                r, within = divmod(beat, cx * p)
                a, c = divmod(within, cx)
                true_f = r * cx * p + c * p + a
                up_f = (beat % cx) * p + beat // cx
                if true_f < n and up_f != true_f:
                    bad += 1
            total += 1
            if bad:
                wrong += 1
                if len(examples) < 6:
                    examples.append(f"N={n} CX={cx} passes={passes}: {bad} of {n} outputs misplaced")
    return {"cases": total, "wrong": wrong, "examples": examples,
            "rule": "wrong exactly when passes > 1 and CX > 1, i.e. N > 16 * CX with CX >= 2"}


def main():
    result = {"dev_commit": subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True,
                                           text=True).stdout.strip()}
    result["dev_test"] = pytest_counts(REPO, "test/test_dense_output.py", ENV)
    up, commit = upstream_tree()
    result["upstream_commit"] = commit
    result["upstream_test"] = pytest_counts(up, "test/test_dense_output.py", dict(ENV, PYTHONPATH=os.path.join(up, "src")))
    up_src = open(os.path.join(up, "src", "open_eye", "rtl_test_utils.py")).read()
    m = re.search(r"\n(\s*f = offset \+ \(beat % columns\) \* per_column \+ beat // columns)", up_src)
    result["upstream_decoder_line"] = m.group(1).strip() if m else None
    result["dev_roundtrip"] = roundtrip_dev()
    result["upstream_formula"] = upstream_formula()
    path = os.path.join(HERE, "2026-11-23_dense_output_check.json")
    json.dump(result, open(path, "w"), indent=1, ensure_ascii=False)
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
