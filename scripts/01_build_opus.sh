#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root regardless of where the script is invoked from.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OPUS_DIR="$ROOT/opus"
PREFIX="$ROOT/build/opus"
OPUS_REPO="https://gitlab.xiph.org/xiph/opus.git"
OPUS_REF="${OPUS_REF:-v1.5.2}"   # pin for reproducibility

if [ ! -d "$OPUS_DIR/.git" ]; then
  git clone "$OPUS_REPO" "$OPUS_DIR"
fi

cd "$OPUS_DIR"
git fetch --tags --quiet
git checkout --quiet "$OPUS_REF"

./autogen.sh
./configure --prefix="$PREFIX" --disable-shared --enable-static --enable-fixed-point
make -j"$(nproc)"
make install
