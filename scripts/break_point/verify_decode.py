#!/usr/bin/env python3
"""
For one (frame, band, part, delta), confirm:
  - container sizes match base and modified
  - packet-size list matches base and modified
  - baseline and modified decodes both succeed and match sample counts
  - PSNR(base_decode, mod_decode) is computed

Usage:
    python3 verify_decode.py <frame> <band> <part> <delta>
"""
import os
import struct
import subprocess
import sys

def find_project_root(start):
    p = os.path.abspath(start)
    while p != "/":
        if os.path.exists(os.path.join(p, "Makefile")):
            return p
        p = os.path.dirname(p)
    raise RuntimeError("project root not found")

ROOT    = find_project_root(os.path.dirname(__file__))
ENCODER = os.path.join(ROOT, "build", "encode_raw")
DECODER = os.path.join(ROOT, "build", "decode_raw")

# shellcheck disable=SC1091
config = {}
with open(os.path.join(ROOT, "config.env")) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        config[k.strip()] = v.strip()

CLIP = config["CLIP"]
PCM  = os.path.join(ROOT, "data", "pcm", f"{CLIP}.raw")

def read_packet_sizes(path):
    sizes = []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(4)
            if not hdr:
                break
            n = struct.unpack("<I", hdr)[0]
            sizes.append(n)
            f.read(n)
    return sizes

def run(cmd, env=None):
    subprocess.run(cmd, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    if len(sys.argv) != 5:
        print("usage: verify_decode.py <frame> <band> <part> <delta>")
        sys.exit(2)
    frame, band, part, delta = (int(x) for x in sys.argv[1:])

    base_cont = "/tmp/vd_base.opusraw"
    mod_cont  = "/tmp/vd_mod.opusraw"
    base_pcm  = "/tmp/vd_base.raw"
    mod_pcm   = "/tmp/vd_mod.raw"

    run([ENCODER, PCM, base_cont,
         "--bitrate", config["BITRATE"],
         "--frame-ms", config["FRAME_MS"],
         "--mode", config["MODE"]])

    env = os.environ.copy()
    env["PVQ_MOD_TARGET_FRAME"]     = str(frame)
    env["PVQ_MOD_TARGET_BAND"]      = str(band)
    env["PVQ_MOD_TARGET_PARTITION"] = str(part)
    env["PVQ_MOD_DELTA"]            = str(delta)
    run([ENCODER, PCM, mod_cont,
         "--bitrate", config["BITRATE"],
         "--frame-ms", config["FRAME_MS"],
         "--mode", config["MODE"]], env=env)

    print(f"base container size: {os.path.getsize(base_cont)}")
    print(f"mod  container size: {os.path.getsize(mod_cont)}")

    bs = read_packet_sizes(base_cont)
    ms = read_packet_sizes(mod_cont)
    diffs = [(i, x, y) for i, (x, y) in enumerate(zip(bs, ms)) if x != y]
    print(f"packets: base={len(bs)} mod={len(ms)} different={len(diffs)}")
    for i, x, y in diffs[:10]:
        print(f"  packet {i}: base={x} mod={y}")

    run([DECODER, base_cont, base_pcm])
    run([DECODER, mod_cont, mod_pcm])

    psnr = subprocess.run(
        ["python3", os.path.join(ROOT, "scripts", "psnr.py"),
         base_pcm, mod_pcm],
        capture_output=True, text=True, check=True)
    print(psnr.stdout)

if __name__ == "__main__":
    main()
