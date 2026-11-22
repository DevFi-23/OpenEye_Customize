#!/bin/bash
# all.sh: the whole 2026-11-21 review run, from the repository root (about 2 hours): the comparison matrix
# (jobs_run.txt, 8 at a time) into matrix.txt, then dev_p1_subset.sh into dev_p1/.
R=doc/experiments/2026-11-21_upstream_12340ab_review
xargs -P 8 -L 1 $R/run1.sh < $R/jobs_run.txt > $R/matrix.txt 2>&1
echo "matrix done $(date)"
$R/dev_p1_subset.sh "$(head -1 $R/jobs_run.txt | sed 's#/up_old .*#/dev_p1#')" $R/dev_p1
echo "subset done $(date)"
