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

## Getting Started

Run the following command to clone opus from the official repo and build:

```text
make build
```


