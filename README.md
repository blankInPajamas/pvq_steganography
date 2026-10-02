# PVQ Steganography in the Opus CELT Layer

Research project: modify PVQ indices in Opus CELT frames without changing their bit cost,
so the decoder's implicit bit allocation remains synchronized.

Key invariant: any PVQ modification must preserve the exact number of bits consumed.
Most promising surface: raw bits for large PVQ codebooks (>8 bits).

## File Structure

```text
pvq_steganography/
├── opus/
├── build/
│   └── opus/
├── data/
│   ├── pcm/
│   ├── bitstreams/
│   │   ├── encoded/
│   │   └── modified/
│   └── output/
├── scripts/
├── logs/
│   └── pvq_indices/
├── Makefile
└── README.md
```

## Build Configuration

- libopus: <pinned ref, e.g. v1.5.2>, built from source in `opus/`
- Arithmetic: **fixed-point** (`--enable-fixed-point` in `./configure`)
- Rationale: deterministic encoder search, bit-exact across machines,
  matches the normative RFC arithmetic model. Ensures PVQ index logs and
  modified-packet decode results are reproducible.
- Prefix: `build/opus/` (local, static linking only — never link against
  system libopus)
- Do not switch to floating-point mid-experiment; it changes encoder
  search output and invalidates comparisons.

## Dataset

- Common Voice Spontaneous Speech 5.0 — English
- Source format: MP3
- Converted to: 48 kHz mono s16le raw PCM via ffmpeg
- Converted files: data/pcm/cv_001.raw ... cv_NNN.raw
- Full file manifest: data/pcm/manifest.txt


## Phase 1 findings — cv_001 @ 64 kbps, 20 ms, audio, fixed-point build

- 805 encoded frames, 802 with at least one PVQ band
- 38,732 PVQ band records total
- Per-band codebook size V ranges from ~2^4 to ~2^32
- Distribution of log2(V):
     V <  2^16: ~14,500 bands  (37%)
     V >= 2^16: ~24,200 bands  (63%)
     V >= 2^24: ~15,700 bands  (41%)
     V >= 2^28: ~ 7,000 bands  (18%)
     V >= 2^31: ~ 1,600 bands  ( 4%)
- Largest observed V: 4,196,289,420 ≈ 2^31.97
- PVQ indices are coded via ec_enc_uint (range coder). No raw-bit
  path exists for PVQ in this libopus revision.
- Encoded bitstream is byte-identical with and without logging.