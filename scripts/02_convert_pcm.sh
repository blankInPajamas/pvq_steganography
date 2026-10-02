#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:-$ROOT/data/source/}"
DST="$ROOT/data/pcm"
N="${2:-20}"

mkdir -p "$DST"

mapfile -t files < <(find "$SRC" -type f -name '*.mp3' | sort | head -n "$N")

if [ "${#files[@]}" -eq 0 ]; then
  echo "No MP3s found in $SRC" >&2
  exit 1
fi

: > "$DST/manifest.txt"

i=0
for f in "${files[@]}"; do
  i=$((i+1))
  name=$(printf "cv_%03d" "$i")
  out="$DST/${name}.raw"

  ffmpeg -hide_banner -loglevel error -y -i "$f" \
    -ar 48000 -ac 1 -sample_fmt s16 \
    -f s16le -acodec pcm_s16le \
    "$out"

  size=$(stat -c%s "$out" 2>/dev/null || stat -f%z "$out")
  dur=$(awk -v s="$size" 'BEGIN{printf "%.3f", s/96000}')
  sha=$(sha256sum "$out" | awk '{print $1}')

  printf "%s\t%s\t%s\t%s\n" "$name.raw" "$dur" "$sha" "$(basename "$f")" >> "$DST/manifest.txt"
done

echo "Converted $i files into $DST"