"""model_pm.py: clocks a sparse PE spends on one weight column per non-zero activation, PARALLEL_MACS 2 (today) against 1
(not supported by the RTL / Python today), as a function of the zero-weight share. PARALLEL_MACS 2: the entries of
conv_wght_encoding.column_entries (the encoder the RTL decodes, bug #22), two per word, one word per clock. PARALLEL_MACS
1: one entry per word and clock; the same entries without the padding slot of an odd column (a non-zero weight per
entry, an explicit zero entry for every run of more than 15 zeros and one for trailing zeros). Random columns of M0
weights (the filters of one PE column), zeros at independent positions. Prints the mean clocks and the ratio PM1 / PM2,
and the equal-multiplier comparison (two PM1 PEs sharing the column, each M0 / 2 filters, the slower one counts).
From the repository root:  venv/bin/python doc/experiments/2026-11-27_parallel_macs/model_pm.py"""
import math
import random

from open_eye.conv_wght_encoding import OVERHEAD_MAX, column_entries


def pm2_words(col):
    try:
        return math.ceil(len(column_entries(col)) / 2)
    except ValueError:                       # a column the encoder cannot express (no gap to split): one word more
        return math.ceil((sum(1 for v in col if v) + 1) / 2) + 1


def pm1_entries(col):
    n, k, run, cut = len(col), 0, 0, 0
    last = -1
    for p, v in enumerate(col):
        if v:
            gap = p - last - 1
            cut += gap // (OVERHEAD_MAX + 1)
            k += 1
            last = p
    trailing = n - 1 - last
    tail = 0 if trailing == 0 else 1 + (trailing - 1) // (OVERHEAD_MAX + 1)
    return max(1, k + cut + tail)


def main():
    rnd = random.Random(1)
    print("M0 | zero weights | PM2 words | PM1 entries | PM1 / PM2 | 2 x PM1 (M0/2 each, slower) / PM2")
    for m0 in (16, 8, 4):
        for z in (0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 1.0):
            a = b = c = 0
            trials = 4000
            for _ in range(trials):
                col = [0 if rnd.random() < z else rnd.choice([-3, -2, -1, 1, 2, 3]) for _ in range(m0)]
                a += pm2_words(col)
                b += pm1_entries(col)
                h = m0 // 2
                c += max(pm1_entries(col[:h]), pm1_entries(col[h:]))
            print(f"{m0:2d} | {z:4.2f} | {a / trials:6.2f} | {b / trials:6.2f} | {b / a:5.2f} | {c / a:5.2f}")


if __name__ == "__main__":
    main()
