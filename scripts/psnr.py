#!/usr/bin/env python3
import sys
import numpy as np

def load(path):
    return np.fromfile(path, dtype=np.int16)

def find_lag(a, b, max_lag=2000, probe_offset=10000, probe_len=48000):
    """Search +/- max_lag samples for the lag minimizing MSE over a probe window."""
    if len(a) < probe_offset + probe_len or len(b) < probe_offset + probe_len:
        # Fall back to a smaller probe for short files.
        probe_offset = 0
        probe_len = min(len(a), len(b)) // 2

    a_seg = a[probe_offset:probe_offset + probe_len].astype(np.float64)

    best_lag, best_mse = 0, np.inf
    for lag in range(-max_lag, max_lag + 1):
        start = probe_offset + lag
        if start < 0 or start + probe_len > len(b):
            continue
        b_seg = b[start:start + probe_len].astype(np.float64)
        mse = np.mean((a_seg - b_seg) ** 2)
        if mse < best_mse:
            best_mse, best_lag = mse, lag
    return best_lag

def psnr_int16(a, b, lag=0):
    if lag >= 0:
        a2, b2 = a, b[lag:]
    else:
        a2, b2 = a[-lag:], b
    n = min(len(a2), len(b2))
    a2 = a2[:n].astype(np.float64)
    b2 = b2[:n].astype(np.float64)
    mse = np.mean((a2 - b2) ** 2)
    if mse == 0.0:
        return float("inf")
    peak = 32767.0
    return 10.0 * np.log10((peak * peak) / mse)

def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <ref.raw> <test.raw>", file=sys.stderr)
        sys.exit(2)

    a = load(sys.argv[1])
    b = load(sys.argv[2])
    print(f"len_ref={len(a)} len_test={len(b)}")

    lag = find_lag(a, b)
    psnr_raw = psnr_int16(a, b, lag=0)
    psnr_aligned = psnr_int16(a, b, lag=lag)

    print(f"lag = {lag} samples ({lag/48.0:.4f} ms)")
    print(f"PSNR (no align) = {psnr_raw:.2f} dB")
    print(f"PSNR (aligned)  = {psnr_aligned:.2f} dB")

if __name__ == "__main__":
    main()