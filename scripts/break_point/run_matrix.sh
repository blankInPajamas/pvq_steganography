#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# shellcheck source=/dev/null
source "$ROOT/config.env"

SWEEP="python3 scripts/break_point/sweep.py"

run() {
    local clip="$1" br="$2" fms="$3" mode="$4"
    echo "==========================================================="
    echo "=== $clip  ${br}bps  ${fms}ms  $mode"
    echo "==========================================================="
    CLIP="$clip" BITRATE="$br" FRAME_MS="$fms" MODE="$mode" \
        MIN_V=2 PER_BUCKET=20 "$SWEEP"
}

# Bitrate sweep
run cv_001 16000 20 audio
run cv_001 32000 20 audio
run cv_001 64000 20 audio
run cv_001 96000 20 audio

# Frame size sweep
run cv_001 64000 10 audio
run cv_001 64000 40 audio

# Mode sweep
run cv_001 64000 20 voip

# Extreme corners
run cv_001 16000 40 voip
run cv_001 96000 10 audio

# Cross-clip
for i in 002 003 004 005 006; do
    run "cv_$i" 64000 20 audio
done

echo
echo "=== all runs complete; writing summary ==="
python3 scripts/break_point/summarize.py
