#!/usr/bin/env python3
"""
Phase 3a analysis: compute the fraction of bit-neutral substitutions
as a function of (log2(V), delta/V).

Reads logs/phase3a_sweep.tsv and writes a table to stdout.
"""
import math
import os
from collections import defaultdict

def find_project_root(start):
    p = os.path.abspath(start)
    while p != "/":
        if os.path.exists(os.path.join(p, "Makefile")):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("project root not found")

ROOT = find_project_root(os.path.dirname(__file__))
TSV  = os.path.join(ROOT, "logs", "phase3a_sweep.tsv")

def vbucket(V):
    """Bucket codebook sizes. Use finer granularity at the small end."""
    if V <= 1:      return "0"
    if V <= 4:      return "1-4"
    if V <= 16:     return "5-16"
    if V <= 64:     return "17-64"
    if V <= 256:    return "65-256"
    if V <= 1024:   return "257-1024"
    # For larger V, use log2.
    return f"2^{int(math.log2(V))}"

def rbucket(delta, V):
    """Bucket delta/V ratio with a bucket at the top end."""
    r = delta / V
    if r < 1e-3:   return "<1e-3"
    if r < 1e-2:   return "1e-3..1e-2"
    if r < 5e-2:   return "1e-2..5e-2"
    if r < 1e-1:   return "5e-2..1e-1"
    if r < 2.5e-1: return "1e-1..2.5e-1"
    if r < 5e-1:   return "2.5e-1..5e-1"
    if r < 9e-1:   return "5e-1..9e-1"
    return ">=9e-1"

def main():
    rows = []
    with open(TSV) as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 6:
                continue
            frame, band, part, V, delta, sd = (int(p) for p in parts)
            rows.append((frame, band, part, V, delta, sd))

    if not rows:
        print("no rows in", TSV)
        return

    # Overall stats.
    total       = len(rows)
    neutral     = sum(1 for r in rows if r[5] == 0)
    print(f"total substitutions : {total}")
    print(f"bit-neutral         : {neutral} ({neutral/total:.3f})")
    print(f"non-neutral         : {total - neutral}")
    if total - neutral > 0:
        szmin = min(r[5] for r in rows if r[5] != 0)
        szmax = max(r[5] for r in rows if r[5] != 0)
        print(f"size_delta range    : {szmin} .. {szmax}")
    print()

    # Bucketed table.
    buckets = defaultdict(lambda: [0, 0])   # key -> [neutral, total]
    for _, _, _, V, delta, sd in rows:
        key = (vbucket(V), rbucket(delta, V))
        buckets[key][1] += 1
        if sd == 0:
            buckets[key][0] += 1

    # Order vbuckets logically, not lexically.
    vbuckets = ["0", "1-4", "5-16", "17-64", "65-256", "257-1024"]
    vbuckets += [f"2^{k}" for k in range(10, 33)]

    rbuckets = ["<1e-3", "1e-3..1e-2", "1e-2..5e-2", "5e-2..1e-1",
                "1e-1..2.5e-1", "2.5e-1..5e-1", "5e-1..9e-1", ">=9e-1"]

    print(f"{'V bucket':>10} {'delta/V':>12} {'neutral':>9} {'total':>7} {'frac':>6}")
    for vb in vbuckets:
        for rb in rbuckets:
            key = (vb, rb)
            if key not in buckets:
                continue
            n, t = buckets[key]
            print(f"{vb:>10} {rb:>12} {n:>9} {t:>7} {n/t:>6.2f}")
    print()

    # Compact view: is there any (V bucket, delta bucket) where frac < 1?
    print("Cells with frac < 1.00 (boundary candidates):")
    any_fail = False
    for vb in vbuckets:
        for rb in rbuckets:
            key = (vb, rb)
            if key not in buckets:
                continue
            n, t = buckets[key]
            if n < t:
                print(f"  V={vb:>10}  delta/V={rb:>12}  "
                      f"{n}/{t} neutral  frac={n/t:.3f}")
                any_fail = True
    if not any_fail:
        print("  (none — every tested substitution was bit-neutral)")

if __name__ == "__main__":
    main()