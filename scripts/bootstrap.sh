#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=/dev/null
source "$ROOT/config.env"

echo "=== step 1: build libopus and apply patches ==="
./scripts/01_build_opus.sh

echo "=== step 2: build tools ==="
make tools

echo "=== step 3: verify clip exists and hash matches ==="
CLIP_PATH="data/pcm/${CLIP}.raw"
if [ ! -f "$CLIP_PATH" ]; then
    echo "missing $CLIP_PATH" >&2
    echo "convert one with scripts/02_convert_pcm.sh and retry" >&2
    exit 1
fi
if [ "$CLIP_SHA256" != "0000000000000000000000000000000000000000000000000000000000000000" ]; then
    actual=$(sha256sum "$CLIP_PATH" | awk '{print $1}')
    if [ "$actual" != "$CLIP_SHA256" ]; then
        echo "clip hash mismatch" >&2
        echo "  expected: $CLIP_SHA256" >&2
        echo "  actual:   $actual" >&2
        exit 1
    fi
fi

echo "=== step 4: reference encode (no substitution) ==="
PVQ_LOG="logs/pvq_${CLIP}_${BITRATE}_${FRAME_MS}ms_${MODE}.log" \
    ./build/encode_raw \
        "$CLIP_PATH" \
        "data/bitstreams/encoded/${CLIP}_base.opusraw" \
        --bitrate "$BITRATE" --frame-ms "$FRAME_MS" --mode "$MODE"

echo "=== step 5: reference decode ==="
./build/decode_raw \
    "data/bitstreams/encoded/${CLIP}_base.opusraw" \
    "data/output/${CLIP}_base.raw"

echo "=== step 6: verify against reference hashes ==="
python3 scripts/verify.py
