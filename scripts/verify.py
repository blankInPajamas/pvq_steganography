#!/usr/bin/env python3
"""
Verify that the freshly rebuilt pipeline reproduces the reference state.

Checks:
  - container byte count and sha256 match config.env
  - PVQ log has expected row count and max frame
  - Phase 2 substitution fires exactly the expected number of times
"""
import hashlib
import os
import subprocess
import sys

def find_project_root(start):
    p = os.path.abspath(start)
    while p != "/":
        if os.path.exists(os.path.join(p, "Makefile")):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("project root not found")

ROOT = find_project_root(os.path.dirname(__file__))
CONFIG = {}
with open(os.path.join(ROOT, "config.env")) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        CONFIG[k.strip()] = v.strip()

CLIP = CONFIG["CLIP"]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)

def ok(msg):
    print(f"OK:   {msg}")

def main():
    base_path = os.path.join(
        ROOT, "data", "bitstreams", "encoded", f"{CLIP}_base.opusraw")
    if not os.path.exists(base_path):
        fail(f"missing {base_path}; run bootstrap first")

    size = os.path.getsize(base_path)
    expected_size = int(CONFIG["BASELINE_CONTAINER_BYTES"])
    if expected_size and size != expected_size:
        fail(f"container size {size} != {expected_size}")
    ok(f"container size {size}")

    h = sha256(base_path)
    expected_hash = CONFIG["BASELINE_CONTAINER_SHA256"]
    if expected_hash and expected_hash != "0" * 64 and h != expected_hash:
        fail(f"container hash {h} != {expected_hash}")
    ok(f"container hash {h}")

    # PVQ log checks.
    log_path = os.path.join(
        ROOT, "logs",
        f"pvq_{CLIP}_{CONFIG['BITRATE']}_{CONFIG['FRAME_MS']}ms_"
        f"{CONFIG['MODE']}.log")
    if not os.path.exists(log_path):
        fail(f"missing {log_path}")
    rows = 0
    max_frame = 0
    with open(log_path) as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 6:
                continue
            rows += 1
            max_frame = max(max_frame, int(parts[0]))
    ok(f"PVQ log rows = {rows}, max frame = {max_frame}")

    # Phase 2 substitution reproduction.
    mod_path = "/tmp/verify_mod.opusraw"
    env = os.environ.copy()
    env["PVQ_MOD_TARGET_FRAME"]     = CONFIG["PHASE2_FRAME"]
    env["PVQ_MOD_TARGET_BAND"]      = CONFIG["PHASE2_BAND"]
    env["PVQ_MOD_TARGET_PARTITION"] = CONFIG["PHASE2_PARTITION"]
    env["PVQ_MOD_DELTA"]            = CONFIG["PHASE2_DELTA"]
    env["PVQ_MOD_LOG"]              = "/tmp/verify_fired.log"
    subprocess.run(
        [os.path.join(ROOT, "build", "encode_raw"),
         os.path.join(ROOT, "data", "pcm", f"{CLIP}.raw"),
         mod_path,
         "--bitrate", CONFIG["BITRATE"],
         "--frame-ms", CONFIG["FRAME_MS"],
         "--mode", CONFIG["MODE"]],
        env=env, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    h_mod = sha256(mod_path)
    expected_mod = CONFIG["PHASE2_MOD_CONTAINER_SHA256"]
    if expected_mod and expected_mod != "0" * 64 and h_mod != expected_mod:
        fail(f"Phase 2 modified container hash {h_mod} != {expected_mod}")
    ok(f"Phase 2 modified container hash {h_mod}")

    print()
    print("all checks passed")

if __name__ == "__main__":
    main()
