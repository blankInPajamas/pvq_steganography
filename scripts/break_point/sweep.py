#!/usr/bin/env python3
"""
Phase 3a: parallel bit-neutrality sweep.

Environment variables (all optional):
  BITRATE      default 64000
  FRAME_MS     default 20
  MODE         default audio
  MIN_V        default 2
  PER_BUCKET   default 20
  CLIP         default cv_001
  WORKERS      default = os.cpu_count()
  OUT_TSV      default logs/phase3a/sweep_<clip>_<bitrate>_<frame>ms_<mode>.tsv
  PVQ_LOG      default logs/phase3a/pvq_<clip>_<bitrate>_<frame>ms_<mode>.log
"""
import math
import os
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

# ---- config ---------------------------------------------------------------

def find_project_root(start):
    p = os.path.abspath(start)
    while p != "/":
        if os.path.exists(os.path.join(p, "Makefile")):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("project root not found")

ROOT     = find_project_root(os.path.dirname(__file__))
ENCODER  = os.path.join(ROOT, "build", "encode_raw")

BITRATE    = os.environ.get("BITRATE",    "64000")
FRAME_MS   = os.environ.get("FRAME_MS",   "20")
MODE       = os.environ.get("MODE",       "audio")
MIN_V      = int(os.environ.get("MIN_V",      "2"))
PER_BUCKET = int(os.environ.get("PER_BUCKET", "20"))
CLIP       = os.environ.get("CLIP", "cv_001")
WORKERS    = int(os.environ.get("WORKERS", str(os.cpu_count() or 4)))

PCM = os.path.join(ROOT, "data", "pcm", f"{CLIP}.raw")

OUT_DIR = os.path.join(ROOT, "logs", "phase3a")
os.makedirs(OUT_DIR, exist_ok=True)

DEFAULT_TSV = os.path.join(
    OUT_DIR, f"sweep_{CLIP}_{BITRATE}_{FRAME_MS}ms_{MODE}.tsv")
DEFAULT_LOG = os.path.join(
    OUT_DIR, f"pvq_{CLIP}_{BITRATE}_{FRAME_MS}ms_{MODE}.log")
OUT_TSV  = os.environ.get("OUT_TSV", DEFAULT_TSV)
META_OUT = OUT_TSV.replace(".tsv", ".meta")
PVQ_LOG  = os.environ.get("PVQ_LOG", DEFAULT_LOG)

TMP_DIR = "/tmp/p3a"
os.makedirs(TMP_DIR, exist_ok=True)

# ---- encoder invocation ---------------------------------------------------

def _base_env():
    env = os.environ.copy()
    for k in ("PVQ_LOG",
              "PVQ_MOD_TARGET_FRAME",
              "PVQ_MOD_TARGET_BAND",
              "PVQ_MOD_TARGET_PARTITION",
              "PVQ_MOD_DELTA",
              "PVQ_MOD_LOG"):
        env.pop(k, None)
    return env

def run_encode(out_path, frame=None, band=None, part=None, delta=None,
               pvq_log=None):
    env = _base_env()
    if pvq_log: env["PVQ_LOG"] = pvq_log
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

def run_one(task):
    """Worker entry point. task = (frame, band, part, V, delta)."""
    frame, band, part, V, delta = task
    out = os.path.join(TMP_DIR, f"{os.getpid()}_{frame}_{band}_{part}_{delta}.opusraw")
    try:
        run_encode(out, frame=frame, band=band, part=part, delta=delta)
        return (frame, band, part, V, delta, os.path.getsize(out))
    finally:
        if os.path.exists(out):
            os.unlink(out)

# ---- targets --------------------------------------------------------------

def ensure_pvq_log():
    if os.path.exists(PVQ_LOG) and os.path.getsize(PVQ_LOG) > 0:
        return
    print(f"generating PVQ log: {PVQ_LOG}")
    run_encode(os.path.join(TMP_DIR, "pvqgen.opusraw"), pvq_log=PVQ_LOG)

def load_partitions(log_path):
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
        part = counts[key]
        counts[key] += 1
        if V >= MIN_V:
            out.append((frame, band, part, V))
    return out

def stratified_sample(targets, per_bucket=PER_BUCKET):
    buckets = defaultdict(list)
    for t in targets:
        b = int(math.log2(t[3])) if t[3] > 0 else -1
        buckets[b].append(t)
    out = []
    for b in sorted(buckets):
        out.extend(buckets[b][:per_bucket])
    return out

def geometric_deltas(v, max_deltas=24):
    out = []
    d = 1
    while d <= v // 2 and len(out) < max_deltas:
        out.append(d)
        d *= 2
    for cand in (v // 4, v // 2, (3 * v) // 4, v - 2, v - 1):
        if cand >= 1 and cand not in out:
            out.append(cand)
    return out

# ---- main -----------------------------------------------------------------

def main():
    print(f"config: clip={CLIP} bitrate={BITRATE} frame_ms={FRAME_MS} "
          f"mode={MODE} min_V={MIN_V} per_bucket={PER_BUCKET} workers={WORKERS}")

    ensure_pvq_log()

    baseline = os.path.join(TMP_DIR, "baseline.opusraw")
    run_encode(baseline)
    base_size = os.path.getsize(baseline)
    print(f"baseline container size: {base_size}")

    targets = load_partitions(PVQ_LOG)
    print(f"partitions with V >= {MIN_V}: {len(targets)}")

    sample = stratified_sample(targets)
    print(f"sampled targets: {len(sample)}")

    tasks = []
    for frame, band, part, V in sample:
        for delta in geometric_deltas(V):
            tasks.append((frame, band, part, V, delta))
    print(f"total encodes: {len(tasks)}")

    rows = []
    done = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(run_one, t): t for t in tasks}
        for fut in as_completed(futures):
            frame, band, part, V, delta, sz = fut.result()
            rows.append((frame, band, part, V, delta, sz - base_size))
            done += 1
            if done % 2000 == 0:
                print(f"  progress: {done}/{len(tasks)}")

    rows.sort()
    with open(OUT_TSV, "w") as f:
        f.write("frame\tband\tpart\tV\tdelta\tsize_delta\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"wrote {len(rows)} rows to {OUT_TSV}")

    neutral = sum(1 for r in rows if r[5] == 0)
    with open(META_OUT, "w") as f:
        for k, v in [
            ("clip", CLIP), ("bitrate", BITRATE), ("frame_ms", FRAME_MS),
            ("mode", MODE), ("min_V", MIN_V), ("per_bucket", PER_BUCKET),
            ("n_targets", len(sample)), ("n_encodes", len(rows)),
            ("neutral", neutral), ("non_neutral", len(rows) - neutral),
            ("baseline_bytes", base_size),
        ]:
            f.write(f"{k} = {v}\n")
    print(f"neutral: {neutral}/{len(rows)}")

if __name__ == "__main__":
    main()
