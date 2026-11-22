"""compare_ns.py <ids.txt> <tree A> <tree B>: for every pytest id, the simulated time of the last PASS / FAIL line of
test/.temp/<node id>/cocotb_sim.log in both trees (node id as test_conv_const._run_conv_const builds it), and whether
they are equal. Used for dev (A, the regression of 2026-11-21) against dev_p1 (B, dev + the converter change of upstream
12340ab): equal times mean the removed branch never acted in that test."""
import os, re, sys
ids, a, b = sys.argv[1:4]
def ns(tree, tid):
    node = tid.replace("::", "_").replace("/", "_").replace("[", "_").replace("]", "_")
    p = os.path.join(tree, "test", ".temp", node, "cocotb_sim.log")
    if not os.path.exists(p):
        return None
    m = re.findall(r"(PASS|FAIL)\s+([0-9.]+)", open(p, errors="replace").read())
    return float(m[-1][1]) if m else "?"
same = diff = missing = 0
for tid in open(ids).read().split():
    x, y = ns(a, tid), ns(b, tid)
    if x is None or y is None:
        missing += 1; print("MISSING", tid, x, y); continue
    if x == y:
        same += 1
    else:
        diff += 1; print("DIFF", tid, x, y)
print(f"equal {same}, different {diff}, missing {missing}")
