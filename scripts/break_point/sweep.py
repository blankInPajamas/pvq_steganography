#!/usr/bin/env python3
"""
Phase 3a: bit-neutrality break-point sweep.

For each (frame, band, partition) with a codebook size V >= MIN_V,
and for each delta in a geometric + boundary series, run the encoder
with the substitution enabled and record whether the container size
changed.

Output: logs/phase3a_sweep.tsv with columns
    frame  band  part  V  delta  size_delta
"""
import math
import os
import subprocess
import sys
from collections import defaultdict

# ---- project root discovery ---------------------------------------------

def find_project_root(start):
    p = os.path.abspath(start)
    while p != "/":
        if os.path.exists(os.path.join(p, "Makefile")):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("project root (with Makefile) not found")

ROOT     = find_project_root(os.path.dirname(__file__))
ENCODER  = os.path.join(ROOT, "build", "encode_raw")
PCM      = os.path.join(ROOT, "data", "pcm", "cv_001.raw")
LOG      = os.path.join(ROOT, "logs", "pvq_indices", "cv_001.log")
OUT_TSV  = os.path.join(ROOT, "logs", "phase3a_sweep.tsv")
TMP      = "/tmp/p3a_tmp.opusraw"

BITRATE  = "64000"
FRAME_MS = "20"
MODE     = "audio"

MIN_V          = 10     # include small codebooks
PER_BUCKET     = 30     # stratified sample size per log2(V) bucket
MAX_DELTAS     = 24     # cap the per-target delta list

# ---- encoder invocation --------------------------------------------------

def run_encode(out_path, frame=None, band=None, part=None, delta=None):
    """Run the encoder with the given substitution targets.

    Any argument left as None means the corresponding PVQ_MOD_* env var
    is not set, which disables that dimension of the substitution.
    """
    env = os.environ.copy()
    for k in ("PVQ_MOD_TARGET_FRAME",
              "PVQ_MOD_TARGET_BAND",
              "PVQ_MOD_TARGET_PARTITION",
              "PVQ_MOD_DELTA",
              "PVQ_MOD_LOG"):
        env.pop(k, None)

    if frame is not None: env["PVQ_MOD_TARGET_FRAME"]     = str(frame)
    if band  is not None: env["PVQ_MOD_TARGET_BAND"]      = str(band)
    if part  is not None: env["PVQ_MOD_TARGET_PARTITION"] = str(part)
    if delta is not None: env["PVQ_MOD_DELTA"]            = str(delta)

    subprocess.run(
        [ENCODER, PCM, out_path,
         "--bitrate", BITRATE, "--frame-ms", FRAME_MS, "--mode", MODE],
        env=env, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

def container_size(path):
    return os.path.getsize(path)

# ---- target extraction ---------------------------------------------------

def load_partitions(log_path):
    """Return list of (frame, band, part_index, V) for every partition.

    part_index is the 0-based index of this partition within its
    (frame, band) group, in log order. This matches the partition
    counter maintained in cwrs.c, which increments on every call to
    encode_pulses for the same band within one frame.
    """
    rows = []
    with open(log_path) as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 6:
                continue
            frame, band, N, K, V, idx = (int(p) for p in parts)
            rows.append((frame, band, V))

    counts = defaultdict(int)
    out = []
    for frame, band, V in rows:
        key = (frame, band)
        idx = counts[key]
        counts[key] += 1
        if V >= MIN_V:
            out.append((frame, band, idx, V))
    return out

def stratified_sample(targets, per_bucket=PER_BUCKET):
    """Take up to per_bucket entries from each log2(V) bucket."""
    buckets = defaultdict(list)
    for t in targets:
        b = int(math.log2(t[3]))
        buckets[b].append(t)
    out = []
    for b in sorted(buckets):
        out.extend(buckets[b][:per_bucket])
    return out, buckets

# ---- delta generation ----------------------------------------------------

def geometric_deltas(v, max_deltas=MAX_DELTAS):
    """Powers of two up to v//2, plus explicit boundary values."""
    out = []
    d = 1
    while d <= v // 2 and len(out) < max_deltas:
        out.append(d)
        d *= 2
    for cand in (v // 4, v // 2, (3 * v) // 4, v - 2, v - 1):
        if cand >= 1 and cand not in out:
            out.append(cand)
    return out

# ---- main ----------------------------------------------------------------

def main():
    baseline = "/tmp/p3a_base.opusraw"
    run_encode(baseline)                     # no substitution
    base_size = container_size(baseline)
    print(f"baseline container size: {base_size}")

    targets = load_partitions(LOG)
    print(f"total partitions with V >= {MIN_V}: {len(targets)}")

    sample, buckets = stratified_sample(targets)
    print(f"targets after stratified sample: {len(sample)}")
    print("bucket distribution (log2(V) -> count sampled):")
    sampled_by_bucket = defaultdict(int)
    for _, _, _, V in sample:
        sampled_by_bucket[int(math.log2(V))] += 1
    for b in sorted(sampled_by_bucket):
        print(f"  {b:>2}: {sampled_by_bucket[b]}")

    out_rows = []
    total_encodes = sum(len(geometric_deltas(V)) for _, _, _, V in sample)
    print(f"total encodes to run: {total_encodes}")
    done = 0

    for i, (frame, band, part, V) in enumerate(sample):
        for delta in geometric_deltas(V):
            run_encode(TMP,
                       frame=frame, band=band, part=part, delta=delta)
            sz = container_size(TMP)
            out_rows.append((frame, band, part, V, delta, sz - base_size))
            done += 1
        if (i + 1) % 25 == 0:
            print(f"  progress: {i+1}/{len(sample)} targets "
                  f"({done}/{total_encodes} encodes)")

    with open(OUT_TSV, "w") as f:
        f.write("frame\tband\tpart\tV\tdelta\tsize_delta\n")
        for row in out_rows:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"wrote {len(out_rows)} rows to {OUT_TSV}")

if __name__ == "__main__":
    main()