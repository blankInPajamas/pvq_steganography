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
# Apply the PVQ instrumentation patches, then rebuild.
cd "$ROOT/opus"

shopt -s nullglob
patch_files=("$ROOT"/patches/*.patch)
shopt -u nullglob

if [ ${#patch_files[@]} -eq 0 ]; then
    echo "error: no patches found in $ROOT/patches" >&2
    exit 1
fi

for p in "${patch_files[@]}"; do
    if git apply --check "$p" 2>/dev/null; then
        git apply "$p"
        echo "applied $p"
    elif git apply --reverse --check "$p" 2>/dev/null; then
        echo "$p already applied"
    else
        echo "error: cannot apply $p" >&2
        exit 1
    fi
done

# Post-condition: the instrumentation must be in the source tree.
grep -q "g_pvq_target_partition" "$ROOT/opus/celt/cwrs.c" \
    || { echo "error: PVQ instrumentation missing from cwrs.c" >&2; exit 1; }
make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
make install

grep -q "^#define FIXED_POINT 1" "$ROOT/opus/config.h" \
    && echo "opus: fixed-point OK" \
    || { echo "opus: NOT fixed-point" >&2; exit 1; }
