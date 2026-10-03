#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=/dev/null
source "$ROOT/config.env"

OPUS_DIR="$ROOT/opus"
PREFIX="$ROOT/build/opus"

if [ ! -d "$OPUS_DIR/.git" ]; then
    git clone "$OPUS_REPO" "$OPUS_DIR"
fi

cd "$OPUS_DIR"
git fetch --tags --quiet
git checkout --quiet "$OPUS_REF"

if [ ! -x ./configure ]; then
    ./autogen.sh
fi

./configure \
    --prefix="$PREFIX" \
    --disable-shared \
    --enable-static \
    ${OPUS_ARITH:-}

make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
make install

# Apply the PVQ instrumentation patches, then rebuild.
cd "$ROOT/opus"
for p in "$ROOT"/patches/*.patch; do
    [ -e "$p" ] || continue
    if git apply --check "$p" 2>/dev/null; then
        git apply "$p"
        echo "applied $p"
    elif git apply --reverse --check "$p" 2>/dev/null; then
        echo "$p already applied"
    else
        echo "warning: cannot apply $p cleanly" >&2
    fi
done

make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
make install

grep -q "^#define FIXED_POINT 1" "$ROOT/opus/config.h" \
    && echo "opus: fixed-point OK" \
    || { echo "opus: NOT fixed-point" >&2; exit 1; }
