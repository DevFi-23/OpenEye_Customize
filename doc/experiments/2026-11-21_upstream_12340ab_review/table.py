"""table.py: markdown table of matrix*.txt (one line per run: tag mode case | ns | RESULT ...). PASS cells show the
simulated ns; FAIL cells a short reason. From the repository root."""
import glob, re
R = "doc/experiments/2026-11-21_upstream_12340ab_review"
cells = {}
for f in sorted(glob.glob(f"{R}/matrix*.txt")):
    for line in open(f):
        m = re.match(r"(\S+) (\S+) (\S+) \| (\S+) ns \| (.*)", line.strip())
        if not m:
            continue
        tag, mode, case, ns, rest = m.groups()
        if "PASS" in rest.split(":")[-1][:8]:
            v = f"PASS {float(ns):,.0f}"
        else:
            r = rest
            if "outputs differ" in r: v = "FAIL (" + re.search(r"(\d+ of \d+) outputs differ", r).group(1) + ")"
            elif "feature maps differ" in r: v = "FAIL (" + re.search(r"(\d+ of \d+) feature maps", r).group(1) + " maps)"
            elif "Iact storage" in r: v = "FAIL (iact buffer)"
            elif "No FSM progress" in r: v = "hang"
            elif "values differ" in r: v = "FAIL (values)"
            elif "expected 3 layers" in r or float(ns) == 0: v = "n/a"
            else: v = "FAIL"
        cells[(case, f"{tag} {mode}")] = v
cols = ["up_old dense", "up_new dense", "up_old sparse", "up_new sparse", "dev_fc dense", "dev_fc sparse", "dev_p1 dense", "dev_p1 sparse"]
cases = []
for line in open(f"{R}/cases.txt"):
    if line.strip(): cases.append(line.split()[0])
cases += sorted({c for c, _ in cells if c not in cases})
print("| Case | " + " | ".join(cols) + " |")
print("|---|" + "---|" * len(cols))
for c in cases:
    print(f"| {c} | " + " | ".join(cells.get((c, k), "") for k in cols) + " |")
for k in cols:
    vals = [cells[(c, k)] for c in cases if (c, k) in cells and not cells[(c, k)] == "n/a"]
    print(k, sum(v.startswith("PASS") for v in vals), "/", len(vals))
