# This file is part of the OpenEye project.
# SPDX-License-Identifier: SHL-2.1
"""Zero-compressed weight encoding of the serial convolution path, as hdl/data_pipeline_wght.v decodes it (bug #22).

A PE holds its weights as columns: one column per iact position (kernel x, channel) with the weights of M0 filters.
On the stream every 24-bit word carries two entries {overhead[3:0], value[7:0]}; zero weights are left out and the
overhead of an entry counts the zeros before it. data_pipeline_wght counts positions (overhead + 1 per entry, 1 for
the padding slot of an odd column), steps to the next column after M0 positions (at most once per word, an overshoot of
exactly one is corrected), resets its data SPad write address at every all-zero word, and the PE captures one word
beyond its block. The earlier mapper carried trailing zeros into the next column, wrote nothing for an all-zero
column, allowed runs of more than 15 zeros and left all-zero words in the block, so any zero weight could corrupt the
layer or hang it (doc/experiments/2026-10-24_bug22_weight_encoding.md).

encode_columns writes only what the RTL decodes correctly:
  1. non-zero weight -> (w, zeros since the previous entry of the column); a run of more than 15 zeros is cut by
     explicit zero entries (0, 15), 16 positions each;
  2. a column ends at filter M0-1: a trailing zero is covered by the padding slot when the entry count is odd and
     exactly one zero trails, otherwise an explicit zero (0, trailing - 1) ends the column; an all-zero column is
     (0, M0-1). An explicit (0, 0) in entry 0 followed by the padding slot would be an all-zero word, so an earlier
     gap (v, g) is split into (0, g-1), (v, 0) instead, which makes the count odd;
  3. no zeros are carried into the next column; every column starts at a word boundary;
  4. the rest of the PE block is filled with FILLER (value 0, three positions per word): it only forms columns the PE
     never reads and leaves no all-zero word in the block.
Without zero weights the result is the dense layout, i.e. the stream is the same as before.
"""

OVERHEAD_MAX = 15                       # 4-bit overhead field
FILLER = ((0, 0), (0, 1))               # block filler: non-zero word, value 0


def column_entries(column):
    """Entries [value, overhead] of one column (the weights of its filters in order)."""
    entries, pos = [], 0                # pos: first position not covered yet
    for p, value in enumerate(column):
        if value == 0:
            continue
        gap = p - pos
        while gap > OVERHEAD_MAX:
            entries.append([0, OVERHEAD_MAX])
            gap -= OVERHEAD_MAX + 1
        entries.append([value, gap])
        pos = p + 1
    trailing = len(column) - pos
    if trailing == 0 or (len(entries) % 2 == 1 and trailing == 1):
        return entries                  # ends at the last filter, or the padding slot covers it
    while trailing > OVERHEAD_MAX + 1:
        entries.append([0, OVERHEAD_MAX])
        trailing -= OVERHEAD_MAX + 1
    if trailing == 1 and len(entries) % 2 == 0:
        # (0, 0) would be entry 0 of a word whose entry 1 is the padding slot: split an earlier gap instead,
        # the count becomes odd and the padding slot covers the trailing zero
        for i, (value, gap) in enumerate(entries):
            if value != 0 and gap >= 1:
                entries[i:i + 1] = [[0, gap - 1], [value, 0]]
                return entries
        raise ValueError("column cannot be encoded without an all-zero word: %r" % (column,))
    entries.append([0, trailing - 1])
    return entries


def encode_columns(columns, parallel_macs, block_words, spad_words):
    """SPad list [[value, overhead], [value, overhead]] per word for one PE.

    columns: the weights of each column; block_words: words the RTL takes per PE (ceil(used_wght_per_PE / 2));
    spad_words: length of the returned list (the rest is zero, beyond the block)."""
    if parallel_macs != 2:
        raise ValueError("data_pipeline_wght decodes two entries per word")
    spad = []
    for column in columns:
        entries = column_entries(column)
        if len(entries) % 2:
            entries.append([0, 0])      # padding slot
        spad.extend([entries[i], entries[i + 1]] for i in range(0, len(entries), 2))
    if len(spad) > block_words:
        raise ValueError("encoded columns need %d words, the PE block has %d" % (len(spad), block_words))
    spad.extend([list(e) for e in FILLER] for _ in range(block_words - len(spad)))
    spad.extend([[0, 0], [0, 0]] for _ in range(spad_words - len(spad)))
    return spad
