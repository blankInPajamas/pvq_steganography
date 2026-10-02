#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

NAME="${1:-cv_001}"
BITRATE="${2:-64000}"
FRAME_MS="${3:-20}"
MODE="${4:-audio}"

IN="data/pcm/${NAME}.raw"
ENC="data/bitstreams/encoded/${NAME}.opusraw"
DEC="data/output/${NAME}_decoded.raw"

[ -f "$IN" ] || { echo "missing $IN" >&2; exit 1; }

mkdir -p data/bitstreams/encoded data/output

./build/encode_raw "$IN" "$ENC" --bitrate "$BITRATE" --frame-ms "$FRAME_MS" --mode "$MODE"
./build/decode_raw "$ENC" "$DEC"

echo
echo "=== sizes ==="
ls -l "$IN" "$ENC" "$DEC"

echo
echo "=== PSNR ==="
python3 scripts/psnr.py "$IN" "$DEC"

if python3 -c "import pesq" 2>/dev/null; then
  echo
  echo "=== PESQ ==="
  python3 - "$IN" "$DEC" <<'PY'
import sys, numpy as np
from pesq import pesq
a = np.fromfile(sys.argv[1], dtype=np.int16)
b = np.fromfile(sys.argv[2], dtype=np.int16)[:len(a)]
print(f"PESQ(wb) = {pesq(48000, a, b, 'wb'):.4f}")
PY
fi