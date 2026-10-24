"""Candidate conv weight encoder for the serial path that stays inside what data_pipeline_wght.v decodes correctly.

Per column (the filters_per_calculation weights of one iact position, F of them) it emits entries (value, overhead):
  1. a non-zero weight -> (w, zeros since the previous entry of this column); runs of more than 15 zeros are cut by
     explicit zero entries (0, 15) (each covers 16 positions; the overhead field has 4 bits);
  2. the column must end at position F-1: if the last weight is zero, either the padding slot covers it (odd entry
     count and exactly one trailing zero: the RTL counts the padding slot as one position), or an explicit zero entry
     (0, trailing zeros - 1) ends the column; an all-zero column becomes a single (0, F-1) (+ runs of (0, 15));
  3. an explicit (0, 0) entry may never sit in sub-word 0 with the padding slot after it (that word would be all
     zero, and the RTL skips all-zero words): in that case an earlier gap (v, g >= 1) is split into (0, g-1), (v, 0),
     which makes the entry count odd so that the padding slot covers the trailing zero instead;
  4. no zeros are carried into the next column; every column starts at a word boundary (padding slot (0, 0) in
     sub-word 1 when the entry count is odd), as the RTL expects;
  5. the PE's block (words_total words, the count the RTL transfers per PE) has no all-zero word: the RTL resets the
     data SPad write address at every zero word, and the PE captures one word beyond its block; after a zero tail that
     word would overwrite address 0 and set second_spad_words to 2 (the PE then hangs). The rest of the block is
     filled with [(0, 0), (0, 1)]: value 0, three positions per word, so it only forms columns the PE never reads.
Returns the SPad list the mapper produces ([[value, overhead], [value, overhead]] per word, zero-filled)."""


def column_entries(col):
    F = len(col)
    nz = [(p, v) for p, v in enumerate(col) if v != 0]
    ent, pos = [], 0                       # pos: first position not yet covered
    for p, v in nz:
        gap = p - pos
        while gap > 15:
            ent.append([0, 15])
            gap -= 16
        ent.append([v, gap])
        pos = p + 1
    t = F - pos                            # trailing zeros
    if t > 0:
        if len(ent) % 2 == 1 and t == 1:
            pass                           # the padding slot covers position F-1
        else:
            while t > 16:
                ent.append([0, 15])
                t -= 16
            if t - 1 == 0 and len(ent) % 2 == 0:
                # (0, 0) would land in sub-word 0 next to the padding slot: split an earlier gap instead
                for i, (v, g) in enumerate(ent):
                    if g >= 1 and v != 0:
                        ent[i:i + 1] = [[0, g - 1], [v, 0]]
                        break
                else:
                    raise ValueError("column needs an all-zero word: %r" % (col,))
                # now the count is odd and exactly one trailing zero is left: the padding slot covers it
            else:
                ent.append([0, t - 1])
    return ent


FILLER = [[0, 0], [0, 1]]


def encode(cols, params, words_total=None):
    """words_total: words the RTL takes per PE (ceil(used_wght_per_PE / PARALLEL_MACS)); the block is filled up to it."""
    spad = []
    for col in cols:
        ent = column_entries(col)
        if len(ent) % 2:
            ent.append([0, 0])             # padding slot
        for i in range(0, len(ent), 2):
            spad.append([ent[i], ent[i + 1]])
    if words_total is not None:
        if len(spad) > words_total:
            raise ValueError("encoded columns need %d words, the block has %d" % (len(spad), words_total))
        spad += [[list(e) for e in FILLER] for _ in range(words_total - len(spad))]
    n = int(params.Wghts_per_PE / params.PARALLEL_MACS)
    spad += [[[0, 0], [0, 0]] for _ in range(n - len(spad))]
    return spad
