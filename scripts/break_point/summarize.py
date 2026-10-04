#!/usr/bin/env python3
"""
Summarize all Phase 3a runs into a single table.
"""
import glob
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

ROOT   = find_project_root(os.path.dirname(__file__))
OUT    = os.path.join(ROOT, "logs", "phase3a", "summary.txt")
SWEEPS = sorted(glob.glob(os.path.join(ROOT, "logs", "phase3a", "sweep_*.tsv")))

def vbucket(V):
    if V <= 1:      return "0-1"
    if V <= 4:      return "2-4"
    if V <= 16:     return "5-16"
    if V <= 64:     return "17-64"
    if V <= 256:    return "65-256"
    if V <= 1024:   return "257-1024"
    return f"2^{int(math.log2(V))}"

def rbucket(delta, V):
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
    per_run = []
    global_cells = defaultdict(lambda: [0, 0])
    non_neutral = []

    for tsv in SWEEPS:
        n = neutral = worst = 0
        with open(tsv) as f:
            next(f)
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) != 6:
                    continue
                frame, band, part, V, delta, sd = (int(p) for p in parts)
                n += 1
                if sd == 0:
                    neutral += 1
                else:
                    non_neutral.append((os.path.basename(tsv), frame, band,
                                        part, V, delta, sd))
                    if abs(sd) > abs(worst):
                        worst = sd
                key = (vbucket(V), rbucket(delta, V))
                global_cells[key][1] += 1
                if sd == 0:
                    global_cells[key][0] += 1
        per_run.append((os.path.basename(tsv), n, neutral, n - neutral, worst))

    with open(OUT, "w") as f:
        f.write("=== per-run summary ===\n")
        f.write(f"{'run':<60} {'n':>8} {'neutral':>8} {'nn':>5} {'worst':>8}\n")
        for name, n, neut, nn, worst in per_run:
            f.write(f"{name:<60} {n:>8} {neut:>8} {nn:>5} {worst:>8}\n")

        total_n = sum(r[1] for r in per_run)
        total_neut = sum(r[2] for r in per_run)
        f.write(f"\nglobal: {total_neut}/{total_n} neutral "
                f"({total_neut/total_n:.4f})\n")

        f.write("\n=== global (V, delta/V) grid ===\n")
        vbuckets = ["0-1", "2-4", "5-16", "17-64", "65-256", "257-1024"]
        vbuckets += [f"2^{k}" for k in range(10, 33)]
        rbuckets = ["<1e-3", "1e-3..1e-2", "1e-2..5e-2", "5e-2..1e-1",
                    "1e-1..2.5e-1", "2.5e-1..5e-1", "5e-1..9e-1", ">=9e-1"]
        for vb in vbuckets:
            for rb in rbuckets:
                key = (vb, rb)
                if key not in global_cells:
                    continue
                n, t = global_cells[key]
                f.write(f"  V={vb:>10}  delta/V={rb:>12}  "
                        f"{n:>6}/{t:<6}  {n/t:.3f}\n")

        if non_neutral:
            f.write(f"\n=== {len(non_neutral)} non-neutral substitutions ===\n")
            for row in non_neutral[:100]:
                f.write("  " + str(row) + "\n")
        else:
            f.write("\nno non-neutral substitutions across all runs\n")

    print(f"wrote {OUT}")

if __name__ == "__main__":
    main()
